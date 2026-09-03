# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from __future__ import annotations

import json
import random
import threading
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Callable, Optional, Tuple, cast

from asgiref.sync import sync_to_async
from django.db import OperationalError, close_old_connections, connections, router, transaction
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.serde.types import ChannelProtocol

RETRYABLE_DATABASE_ERROR_CODES = {1205, 1213}
CHECKPOINT_WRITE_MAX_RETRIES = 3
CHECKPOINT_WRITE_RETRY_DELAY_SECONDS = 0.05
_SQLITE_WRITE_LOCKS: dict[str, threading.RLock] = {}
_SQLITE_WRITE_LOCKS_GUARD = threading.Lock()


def _database_vendor(model) -> tuple[str, str]:
    alias = router.db_for_write(model)
    return alias, connections[alias].vendor


@contextmanager
def _database_write_lock(model):
    """Serialize only local SQLite writes across saver instances in this process."""
    alias, vendor = _database_vendor(model)
    if vendor != "sqlite":
        yield
        return

    with _SQLITE_WRITE_LOCKS_GUARD:
        lock = _SQLITE_WRITE_LOCKS.setdefault(alias, threading.RLock())
    with lock:
        yield


def _is_retryable_database_error(exc: OperationalError, model) -> bool:
    error_code = exc.args[0] if exc.args else None
    if error_code in RETRYABLE_DATABASE_ERROR_CODES:
        return True
    _, vendor = _database_vendor(model)
    return vendor == "sqlite" and "database is locked" in str(exc).lower()


def _run_database_write_with_retry(operation: Callable[[], None], model) -> None:
    for attempt in range(CHECKPOINT_WRITE_MAX_RETRIES):
        try:
            operation()
            return
        except OperationalError as exc:
            exhausted = attempt == CHECKPOINT_WRITE_MAX_RETRIES - 1
            if not _is_retryable_database_error(exc, model) or exhausted:
                raise
            close_old_connections()
            time.sleep(CHECKPOINT_WRITE_RETRY_DELAY_SECONDS * (2**attempt))


async def run_db_in_thread(func, *args, **kwargs):
    """在独立线程中执行 Django ORM 调用并返回结果。

    LangGraph 的异步执行路径（ainvoke / astream）会在事件循环里 await checkpointer 的
    a* 方法，而 Django 的数据库游标带 async_unsafe 保护，在存在运行中事件循环的线程里
    直接访问 ORM 会抛 SynchronousOnlyOperation，因此必须把 ORM 调用挪到工作线程执行。

    工作线程持有的是独立的 thread-local 连接，调用结束后需要归还，否则连接会随线程池累积。
    """

    def _call():
        try:
            return func(*args, **kwargs)
        finally:
            close_old_connections()

    return await sync_to_async(_call, thread_sensitive=False)()


def bulk_upsert(model, objs, update_fields, unique_fields):
    """
    通用 bulk upsert 函数：
    - MySQL: 使用 ON DUPLICATE KEY UPDATE
    - 其他数据库: 缺少唯一约束时按逻辑键更新最新记录
    """

    if not objs:
        return

    # 自动选择数据库
    db = router.db_for_write(model)
    connection = connections[db]
    vendor = connection.vendor

    # MySQL: 使用原生 SQL 实现 ON DUPLICATE KEY UPDATE
    if vendor == "mysql":
        table = model._meta.db_table
        fields = [f.name for f in model._meta.local_fields]
        insert_fields = [f for f in fields if f in update_fields or f in unique_fields]
        placeholders = ", ".join(["%s"] * len(insert_fields))
        columns = ", ".join(f"`{f}`" for f in insert_fields)
        update_clause = ", ".join(f"`{f}` = VALUES(`{f}`)" for f in update_fields)
        sql = f"""
        INSERT INTO `{table}` ({columns})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause};
        """
        params = [[getattr(obj, field) for field in insert_fields] for obj in objs]
        with connection.cursor() as cursor, transaction.atomic(using=db):
            cursor.executemany(sql, params)
        return

    manager = model.objects.using(db)
    ordering = ("-created_at", "-pk") if any(f.name == "created_at" for f in model._meta.get_fields()) else ("-pk",)
    with transaction.atomic(using=db):
        for obj in objs:
            lookup = {field: getattr(obj, field) for field in unique_fields}
            defaults = {field: getattr(obj, field) for field in update_fields}
            latest = manager.select_for_update().filter(**lookup).order_by(*ordering).first()
            if latest is None:
                manager.create(**lookup, **defaults)
                continue
            manager.filter(pk=latest.pk).update(**defaults)


class BKDjangoSaver(BaseCheckpointSaver[str]):
    """基于Django模型的检查点保存器

    这个类提供了使用Django ORM存储检查点的功能，仿照SqliteSaver的实现。
    开发者需要提供符合要求的Django模型来存储检查点和写入数据。

    Note:
        这个类适用于Django项目中的检查点存储，支持Django ORM的所有特性。
        需要Django环境和相应的数据库配置。
        checkpoint_id 用于标识检查点，字符类型，由 LangGraph 保证他具有顺序性。

    Args:
        checkpoint_model: Django模型类，用于存储检查点数据
        writes_model: Django模型类，用于存储写入数据
        serde: 可选的序列化协议，默认使用JsonPlusSerializer

    # models.py 示例
    from django.db import models


    class Checkpoint(models.Model):
        thread_id = models.TextField()
        checkpoint_ns = models.TextField(default="")
        checkpoint_id = models.TextField()
        parent_checkpoint_id = models.TextField(null=True, blank=True)
        type = models.TextField(null=True, blank=True)
        checkpoint = models.BinaryField()
        metadata = models.JSONField(default=dict)

    class Write(models.Model):
        thread_id = models.TextField()
        checkpoint_ns = models.TextField(default="")
        checkpoint_id = models.TextField()
        task_id = models.TextField()
        task_path = models.TextField()
        idx = models.IntegerField()
        channel = models.TextField()
        type = models.TextField(null=True, blank=True)
        value = models.BinaryField()

    # 使用示例:
    # from myapp.models import Checkpoint, Write
    # from aidev_agent.core.memory.operators.bk_django_saver import BKDjangoSaver
    #
    # saver = BKDjangoSaver(
    #     checkpoint_model=Checkpoint,
    #     writes_model=Write
    # )

    # admin.py 简单示例， 如果字段有脱敏、异常处理等需求，使用时按照项目需求修改
    import json

    from django.contrib import admin
    from django.utils.html import format_html
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    from .models import Checkpoint, Write

    def get_value_size(obj):
        if obj:
            size = len(obj)
            if size > 1024 * 1024:
                return f"{size / (1024 * 1024):.2f} MB"
            elif size > 1024:
                return f"{size / 1024:.2f} KB"
            else:
                return f"{size} bytes"
        return "0 bytes"


    @admin.register(Checkpoint)
    class CheckpointAdmin(admin.ModelAdmin):

        list_display = [
            'thread_id',
            'checkpoint_ns',
            'checkpoint_id',
            'parent_checkpoint_id',
            'type',
            'metadata_preview',
            'checkpoint_size',
        ]

        list_filter = [
            'thread_id',
            'type',
            'checkpoint_ns',
        ]

        search_fields = [
            'thread_id',
            'checkpoint_ns',
            'checkpoint_id',
            'parent_checkpoint_id',
        ]

        readonly_fields = [
            'checkpoint_size',
            'metadata_formatted',
            'deserialized_checkpoint_display',
        ]

        fieldsets = (
            ('基本信息', {
                'fields': ('thread_id', 'checkpoint_ns', 'checkpoint_id', 'parent_checkpoint_id', 'type')
            }),
            ('数据内容', {
                'fields': ('checkpoint_size', 'metadata_formatted', 'deserialized_checkpoint_display'),
                'classes': ('collapse',)
            }),
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.serde = JsonPlusSerializer()

        def checkpoint_size(self, obj):
            return get_value_size(obj.checkpoint)
        checkpoint_size.short_description = "检查点大小"

        def metadata_preview(self, obj):
            if obj.metadata:
                # 只显示前100个字符
                metadata_str = json.dumps(obj.metadata, ensure_ascii=False, indent=2)
                if len(metadata_str) > 100:
                    return metadata_str[:100] + "..."
                return metadata_str
            return "-"
        metadata_preview.short_description = "元数据预览"

        def metadata_formatted(self, obj):
            if obj.metadata:
                formatted = json.dumps(obj.metadata, ensure_ascii=False, indent=2)
                return format_html('<pre style="background: #f8f8f8; padding: 10px; border-radius: 4px;">{}</pre>', formatted)
            return "-"
        metadata_formatted.short_description = "格式化元数据"

        def _format_deserialized_data(self, data, indent=0):
            indent_str = "  " * indent
            result = []

            if isinstance(data, dict):
                for key, value in data.items():
                    result.append(f"{indent_str}{key}:")
                    result.append(self._format_deserialized_data(value, indent + 1))
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    result.append(f"{indent_str}[{i}]:")
                    result.append(self._format_deserialized_data(item, indent + 1))
            else:
                result.append(f"{indent_str}{str(data)}")

            return "\n".join(result)

        def deserialized_checkpoint_display(self, obj):
            if not obj.checkpoint or not obj.type:
                return format_html('<div style="color: #666;">无数据</div>')

            try:
                deserialized = self.serde.loads_typed((obj.type, obj.checkpoint))

                # 使用美化格式显示
                formatted_content = self._format_deserialized_data(deserialized)

                return format_html(
                    '<div style="background: #e7f3ff; padding: 10px; border-radius: 4px; border-left: 4px solid #0066cc;">'
                    '<strong>类型:</strong> {}<br>'
                    '<strong>内容:</strong><br>'
                    '<pre style="background: #ffffff; padding: 8px; border-radius: 4px; margin-top: 8px; max-height: 500px; overflow-y: auto; font-family: monospace; font-size: 12px; line-height: 1.4;">{}</pre>'
                    '</div>',
                    type(deserialized).__name__,
                    formatted_content
                )
            except Exception as e:
                return format_html(
                    '<div style="background: #fff3cd; padding: 8px; border-radius: 4px; border-left: 4px solid #ffc107;">'
                    '<strong>类型:</strong> 未知<br>'
                    '<strong>处理失败:</strong> {}'
                    '</div>',
                    str(e)
                )
        deserialized_checkpoint_display.short_description = "反序列化检查点"


    @admin.register(Write)
    class WriteAdmin(admin.ModelAdmin):

        list_display = [
            'thread_id',
            'checkpoint_ns',
            'checkpoint_id',
            'task_id',
            'task_path',
            'idx',
            'channel',
            'type',
            'value_size',
        ]

        search_fields = [
            'thread_id',
            'checkpoint_ns',
            'checkpoint_id',
            'task_id',
            'task_path',
            'channel'
        ]

        readonly_fields = [
            'value_size',
            'deserialized_value_display',
        ]

        fieldsets = (
            ('基本信息', {
                'fields': ('thread_id', 'checkpoint_ns', 'checkpoint_id', 'task_id', 'task_path', 'idx')
            }),
            ('写入信息', {
                'fields': ('channel', 'type', 'value_size', 'deserialized_value_display')
            }),
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.serde = JsonPlusSerializer()

        def deserialized_value_display(self, obj):
            if not obj.value or not obj.type:
                return format_html('<div style="color: #666;">无数据</div>')
            deserialized = self.serde.loads_typed((obj.type, obj.value))
            # 格式化显示不同类型的数据
            return format_html(
                '<div style="background: #d4edda; padding: 10px; border-radius: 4px; border-left: 4px solid #198754;">'
                '<strong>类型:</strong> {}<br>'
                '<strong>内容:</strong> {}'
                '</div>',
                type(deserialized).__name__,
                str(deserialized)
            )
        deserialized_value_display.short_description = "反序列化内容"

        def value_size(self, obj):
            return get_value_size(obj.value)
        value_size.short_description = "值大小"

        def get_queryset(self, request):
            return super().get_queryset(request).select_related()
    """

    def __init__(
        self,
        checkpoint_model,
        writes_model,
        *,
        serde: SerializerProtocol | None = None,
    ) -> None:
        super().__init__(serde=serde)
        self.jsonplus_serde = JsonPlusSerializer()
        self.checkpoint_model = checkpoint_model
        self.writes_model = writes_model
        # 使用 threading.Lock 进行进程内互斥，未使用数据库事务和隔离级别，不保证跨进程/多实例一致性
        self.lock = threading.Lock()
        # 验证模型字段
        self._validate_models()

    def _validate_models(self) -> None:
        """验证model是否包含必需的字段， 如果自定义模型需要其他字段或者约束，可重写本方法"""
        # 验证checkpoint模型字段
        checkpoint_fields = [field.name for field in self.checkpoint_model._meta.get_fields()]
        required_checkpoint_fields = [
            "thread_id",
            "checkpoint_ns",
            "checkpoint_id",
            "parent_checkpoint_id",
            "type",
            "checkpoint",
            "metadata",
        ]

        for field in required_checkpoint_fields:
            if field not in checkpoint_fields:
                raise ValueError(
                    f"Checkpoint model {self.checkpoint_model.__name__} is missing required field: {field}"
                )

        # 验证writes模型字段
        writes_fields = [field.name for field in self.writes_model._meta.get_fields()]
        required_writes_fields = [
            "thread_id",
            "checkpoint_ns",
            "checkpoint_id",
            "task_id",
            "idx",
            "channel",
            "type",
            "value",
        ]

        for field in required_writes_fields:
            if field not in writes_fields:
                raise ValueError(f"Writes model {self.writes_model.__name__} is missing required field: {field}")

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """从数据库获取检查点元组

        根据提供的配置从Django数据库中检索检查点元组。如果配置包含checkpoint_id，
        则检索特定的检查点；否则检索该线程的最新检查点。

        Args:
            config: 用于检索检查点的配置

        Returns:
            检索到的检查点元组，如果未找到匹配的检查点则返回None
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        # 构建查询条件，如果指定了checkpoint_id，则使用指定的checkpoint_id，否则使用最新的checkpoint_id
        if checkpoint_id:
            checkpoint_obj = self.checkpoint_model.objects.filter(
                thread_id=thread_id, checkpoint_ns=checkpoint_ns, checkpoint_id=checkpoint_id
            ).first()
        else:
            checkpoint_obj = (
                self.checkpoint_model.objects.filter(thread_id=thread_id, checkpoint_ns=checkpoint_ns)
                .order_by("-checkpoint_id")
                .first()
            )

        if not checkpoint_obj:
            return None

        # 更新配置以包含检查点ID
        if not get_checkpoint_id(config):
            config = {
                "configurable": {
                    "thread_id": checkpoint_obj.thread_id,
                    "checkpoint_ns": checkpoint_obj.checkpoint_ns,
                    "checkpoint_id": checkpoint_obj.checkpoint_id,
                }
            }
        # 反序列化检查点
        checkpoint = self.serde.loads_typed((checkpoint_obj.type, checkpoint_obj.checkpoint))
        # 元数据, metadata是Django JsonField，直接使用即可
        metadata = cast(
            CheckpointMetadata,
            checkpoint_obj.metadata if checkpoint_obj.metadata else {},
        )
        # 构建父配置
        parent_config = None
        if checkpoint_obj.parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": checkpoint_obj.thread_id,
                    "checkpoint_ns": checkpoint_obj.checkpoint_ns,
                    "checkpoint_id": checkpoint_obj.parent_checkpoint_id,
                }
            }

        # 查询相关的写入操作
        writes_queryset = (
            self.writes_model.objects.filter(
                thread_id=checkpoint_obj.thread_id,
                checkpoint_ns=checkpoint_obj.checkpoint_ns,
                checkpoint_id=checkpoint_obj.checkpoint_id,
            )
            .order_by("task_id", "idx")
            .values_list("task_id", "channel", "type", "value")
        )
        writes = [
            (task_id, channel, self.serde.loads_typed((type_, value)))
            for task_id, channel, type_, value in writes_queryset
        ]
        return CheckpointTuple(
            config,
            checkpoint,
            metadata,
            parent_config,
            writes,
        )

    def handle_checkpoint_filters(self, filters: dict[str, Any] | None = None):
        """
        外部可以构造 Django Q 对象对 CheckPoint 进行过滤，根据实际的 Model 进行处理，例如：添加校验、拒绝不允许的查询
        """
        return filters

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """从数据库列出检查点

        根据提供的配置从Django数据库中检索检查点列表。检查点按checkpoint_id降序排列（最新优先）。

        Args:
            config: 用于列出检查点的配置
            filter: 额外过滤条件
            before: 如果提供，只返回指定检查点ID之前的检查点
            limit: 返回的最大检查点数量

        Yields:
            检查点元组的迭代器
        """
        queryset = self.checkpoint_model.objects.order_by("-checkpoint_id")
        if config:
            thread_id = str(config["configurable"]["thread_id"])
            queryset = queryset.filter(thread_id=thread_id)

            checkpoint_ns = config["configurable"].get("checkpoint_ns")
            if checkpoint_ns is not None:
                queryset = queryset.filter(checkpoint_ns=checkpoint_ns)
            if checkpoint_id := get_checkpoint_id(config):
                queryset = queryset.filter(checkpoint_id=checkpoint_id)
        # 处理元数据过滤，外部可以构造 Django Q 对象对代码进行过滤
        if filter:
            filters = self.handle_checkpoint_filters(filter)
            queryset = queryset.filter(**filters)
        if before:
            before_checkpoint_id = get_checkpoint_id(before)
            if before_checkpoint_id:
                queryset = queryset.filter(checkpoint_id__lt=before_checkpoint_id)
        if limit:
            queryset = queryset[:limit]
        # Bulk-fetch writes to avoid N+1 queries
        checkpoint_list = list(queryset)
        if not checkpoint_list:
            return

        thread_ids = {str(cp.thread_id) for cp in checkpoint_list}
        checkpoint_ns_set = {str(cp.checkpoint_ns) for cp in checkpoint_list}
        checkpoint_ids = {str(cp.checkpoint_id) for cp in checkpoint_list}

        writes_qs = (
            self.writes_model.objects.filter(
                thread_id__in=thread_ids,
                checkpoint_ns__in=checkpoint_ns_set,
                checkpoint_id__in=checkpoint_ids,
            )
            .order_by("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx")
            .values_list("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "channel", "type", "value")
        )

        writes_map: dict[tuple[str, str, str], list[tuple[str, str, str, bytes]]] = {}
        for th_id, ns, cp_id, task_id, channel, type_, value in writes_qs:
            key = (str(th_id), str(ns), str(cp_id))
            writes_map.setdefault(key, []).append((task_id, channel, type_, value))

        for checkpoint_obj in checkpoint_list:
            key = (str(checkpoint_obj.thread_id), str(checkpoint_obj.checkpoint_ns), str(checkpoint_obj.checkpoint_id))
            grouped_writes = writes_map.get(key, [])

            yield CheckpointTuple(
                {
                    "configurable": {
                        "thread_id": checkpoint_obj.thread_id,
                        "checkpoint_ns": checkpoint_obj.checkpoint_ns,
                        "checkpoint_id": checkpoint_obj.checkpoint_id,
                    }
                },
                self.serde.loads_typed((checkpoint_obj.type, checkpoint_obj.checkpoint)),
                cast(
                    CheckpointMetadata,
                    checkpoint_obj.metadata if checkpoint_obj.metadata else {},
                ),
                (
                    {
                        "configurable": {
                            "thread_id": checkpoint_obj.thread_id,
                            "checkpoint_ns": checkpoint_obj.checkpoint_ns,
                            "checkpoint_id": checkpoint_obj.parent_checkpoint_id,
                        }
                    }
                    if checkpoint_obj.parent_checkpoint_id
                    else None
                ),
                [
                    (task_id, channel, self.serde.loads_typed((type_, value)))
                    for task_id, channel, type_, value in grouped_writes
                ],
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """将检查点保存到数据库

        将检查点保存到Django数据库中。检查点与提供的配置及其父配置（如果有）关联。

        Args:
            config: 与检查点关联的配置
            checkpoint: 要保存的检查点
            metadata: 与检查点一起保存的额外元数据
            new_versions: 此次写入的新通道版本

        Returns:
            存储检查点后的更新配置
        """
        thread_id = str(config["configurable"]["thread_id"])
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        # 序列化检查点和元数据
        type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        # 将内存中的 metadata 转为标准 json 格式，用于存到 model 的 JsonField 中
        # 直接获取 metadata dict，Django JsonField 会自动处理序列化
        raw_metadata = get_checkpoint_metadata(config, metadata)
        # 通过 json 序列化再反序列化来确保所有值都是 JSON 兼容类型
        serialized_metadata = json.loads(json.dumps(raw_metadata, default=str).replace("\\u0000", ""))

        def save_checkpoint() -> None:
            self.checkpoint_model.objects.update_or_create(
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint["id"],
                defaults={
                    "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
                    "type": type_,
                    "checkpoint": serialized_checkpoint,
                    "metadata": serialized_metadata,
                },
            )

        # SQLite 只允许单写者；跨 saver 实例串行本进程写入，MySQL 等数据库仍保持并行。
        with self.lock, _database_write_lock(self.checkpoint_model):
            _run_database_write_with_retry(save_checkpoint, self.checkpoint_model)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """存储与检查点关联的中间写入操作

        将与检查点关联的中间写入操作保存到Django数据库中。

        Args:
            config: 相关检查点的配置
            writes: 要存储的写入列表，列表含有一系列的(channel, value)对
            task_id: 创建写入的任务标识符
            task_path: 创建写入的任务路径
        """
        thread_id = str(config["configurable"]["thread_id"])
        checkpoint_ns = str(config["configurable"].get("checkpoint_ns", ""))
        checkpoint_id = str(config["configurable"]["checkpoint_id"])
        writes_objects = []

        for idx, (channel, value) in enumerate(writes):
            type_, serialized_value = self.serde.dumps_typed(value)
            writes_objects.append(
                self.writes_model(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    task_id=task_id,
                    idx=WRITES_IDX_MAP.get(channel, idx),
                    channel=channel,
                    type=type_,
                    value=serialized_value,
                )
            )

        def save_writes() -> None:
            if all(w[0] in WRITES_IDX_MAP for w in writes):
                # 如果所有写入都在WRITES_IDX_MAP中，使用bulk_create with update_conflicts
                bulk_upsert(
                    self.writes_model,
                    writes_objects,
                    update_fields=["channel", "type", "value"],
                    unique_fields=["thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"],
                )
            else:
                self.writes_model.objects.bulk_create(
                    writes_objects,
                    ignore_conflicts=True,
                )

        with self.lock, _database_write_lock(self.writes_model):
            _run_database_write_with_retry(save_writes, self.writes_model)

    def delete_thread(self, thread_id: str) -> None:
        """删除与线程ID关联的所有检查点和写入记录

        Args:
            thread_id: 要删除的线程ID
        """
        thread_id = str(thread_id)
        # 删除检查点
        self.checkpoint_model.objects.filter(thread_id=thread_id).delete()

        # 删除写入记录
        self.writes_model.objects.filter(thread_id=thread_id).delete()

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return await run_db_in_thread(self.get_tuple, config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        # list 是惰性生成器，必须在工作线程里物化，否则 QuerySet 会在事件循环所在线程求值
        items = await run_db_in_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for item in items:
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await run_db_in_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        return await run_db_in_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        return await run_db_in_thread(self.delete_thread, thread_id)

    def get_next_version(self, current: Optional[str], channel: ChannelProtocol) -> str:
        """为通道生成下一个版本ID

        基于当前版本为通道创建新的版本标识符，和 InMemorySaver 保持一致。

        Args:
            current: 通道的当前版本标识符
            channel: 通道对象（未使用）

        Returns:
            下一个版本标识符，保证单调递增
        """
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])

        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"
