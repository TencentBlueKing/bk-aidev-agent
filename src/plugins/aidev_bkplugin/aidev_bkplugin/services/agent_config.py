# -*- coding: utf-8 -*-
"""Agent 配置读取。

通过 ``resource_manager()``（``ResourceManagerProtocol`` 全局工厂）取回 agent 配置原始字典，
不直接依赖 ``aidev_agent.api.bk_aidev.BKAidevApi``。

请求级缓存：``get_info`` 在同一次 HTTP 请求内对相同 ``(app_code, version, username)`` 三元组只
触发一次远程调用；缓存挂在 ``aidev_agent.utils.local.request_local``（werkzeug ``Local``，
由 blueapps 中间件在请求结束时统一清理）。命中 / 写入均做 ``deepcopy``，确保调用方对返回
``dict`` 的 mutation（如 ``pop("otel_info", None)``）不影响后续命中结果。

应用启动时兜底（对于已经预热场景在有缓存的时候进行降级）：
1. ``retrieve_agent_config`` 故障时（启动期 ``username=None`` 且 AIDEV后端不可达），
2. Django cache 后端可用 (开发者需要手动启用该配置：修改 cache[default]指向持久化后端 或者 自行启用 cache[aidev_bkplugin])
3. 对应 app_code + version 的缓存已经由先前成功请求写入(必须需要有 otel_info， 无 otel_info 的时候不进行兜底)
cache 后端按以下优先级选择：
如果配置了 ``CACHES["aidev_bkplugin"]``，优先使用该专用后端；否则复用 ``CACHES["default"]``。
如果项目现有的 ``default`` cache 已经是适合保存 agent 配置快照的持久化后端，可以直接使用本能力，无需增加配置。
如果 ``default`` cache 不适合保存 ``agent_info``，开发者可以增加``CACHES["aidev_bkplugin"]``，为本能力提供专用后端。
若最终选中的 cache 后端不具备跨进程、重启或重新部署所需的持久化能力，
代码仍会按 Django cache 接口执行读写，但不保证 fallback 快照在这些场景下可用。
cache 写入失败不会影响正常的平台成功响应。
"""

from __future__ import annotations

import base64
import copy
import json
from logging import getLogger
from typing import Optional

from aidev_agent.packages.resource_manager import resource_manager
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.utils.local import request_local
from django.core.cache import caches
from requests.exceptions import RequestException

logger = getLogger(__name__)

_REQUEST_CACHE_ATTR = "_agent_config_fetcher_cache"

_DJANGO_CACHE_KEY_PREFIX = "agent_info"

# django cache 全局 fallback TTL：1 周。request cache 每请求重置 + 每次成功都刷新，正常情况下
# 永远读不到过期；TTL 仅作为兜底数据最坏存活上限，避免后端长期故障 + 进程未重启时读到远古快照。
_FALLBACK_CACHE_TIMEOUT = 7 * 24 * 60 * 60


def _get_django_cache_backend():
    """取 django cache：优先专用别名 'aidev_bkplugin'（主项目可配隔离），未配置回落 'default'。"""
    return caches["aidev_bkplugin"] if "aidev_bkplugin" in caches else caches["default"]


class AgentConfigFetcher:
    """Plugin 层 agent 配置读取服务（无状态）。

    两个 ``@classmethod`` 调用入口：``get_info`` 取原始字典（``otel_info`` 自动 ``base64+json`` 解码），
    ``get_role_info`` 取装配后的 role prompts。所有过滤维度（``app_code`` / ``version`` / ``username``）
    通过 keyword-only 参数显式传入；``app_code`` 缺省回落到 ``settings.APP_CODE``。

    ``get_info`` 内置请求级缓存；``get_role_info`` 内部走 ``get_info``，自然继承缓存。
    ``get_info`` 另带跨请求 django cache 兜底，用于启动期后端不可达时仍能拉起进程。
    """

    @classmethod
    def get_info(
        cls,
        *,
        app_code: Optional[str] = None,
        version: Optional[str] = None,
        username: Optional[str] = None,
    ) -> dict:
        """读取 agent 配置原始字典；``otel_info`` 自动解码。

        请求级缓存命中：直接返回缓存值的 ``deepcopy``。脱离请求上下文（如离线脚本）时降级为不缓存。

        当前请求逻辑：
        1. 按 智能体名称、版本调用人、版本 构造 cache key
        2. 如果进程缓存命中、那么直接deepcopy 返回
        3. 未命中时拉取最新配置, 未命中调用 ``retrieve_agent_config``（包在 try 内）
        4. 拉取失败时，在无用户名请求(启动等场景)下进入 fallback, 其他情况抛出异常
        5. 拉取成功并且处理后时，写入进程缓存，移除用户相关信息写入持久化缓存

        fallback 生效条件：
        1. Django cache 后端可用 且为 持久化 cache 后端
        2. 对应 app_code + version 的缓存已经由先前成功请求写入
        """
        effective_app_code = app_code or resource_manager().get_agent_code()
        cache_key = (effective_app_code, version, username)
        cache = cls._get_request_cache()
        if cache is not None and cache_key in cache:
            return copy.deepcopy(cache[cache_key])

        try:
            agent_info = resource_manager().retrieve_agent_config(
                agent_code=effective_app_code,
                version=version,
                headers={"X-BKAIDEV-USER": username},
            )
        except RequestException as platform_exc:
            # 带 username 的请求失败 re-raise（保留原始 traceback），不兜底：
            # 用户态调用不得使用无用户快照代替平台鉴权结果
            # 兜底配置无 username 上下文，给到特定用户可能越权
            if username:
                raise
            # 失败策略：无用户调用发生 ``RequestException`` 时读取快照
            # 该异常范围有意包含网络错误以及 401、403、404、5xx 等平台响应错误
            # 因为平台发布、网关路由或认证服务短暂异常也可能产生这些状态码
            # username 为空走 django cache 兜底：命中返回 deepcopy，未命中抛 ValueError。
            # 把原始平台异常透传给 ``get_info_without_user``，作为兜底失败时 ValueError 的 __cause__
            # （cache.get 自身报错时也链上原始异常），便于运维区分超时 / 鉴权 / 404 / 缓存故障。
            # 平台调用异常并命中 Django fallback 时，fallback 快照不会写入请求级缓存
            # 后续相同调用仍会重新请求平台，并在再次失败后重新读取 fallback 快照
            # 可以避免一次临时故障使后续调用在整个请求周期内持续使用旧快照，并允许平台恢复后的下一次请求取得最新配置
            return cls.get_info_without_user(effective_app_code, version, platform_exc)

        otel_env_info = agent_info.pop("otel_info", None)
        if otel_env_info:
            agent_info["otel_info"] = json.loads(base64.b64decode(otel_env_info).decode())

        if cache is not None:
            cache[cache_key] = copy.deepcopy(agent_info)

        # django cache 必须被每次成功请求刷新
        # 若只在启动场景（username 为空）写一次，启动后会停留在启动快照, 而无法感知到后续配置更新
        # 每次成功都写，但写入内容剥离用户维度相关字段（``allowed_access``）：
        cls.set_info_without_user(effective_app_code, version, agent_info)
        return agent_info

    @classmethod
    def get_role_info(
        cls,
        *,
        app_code: Optional[str] = None,
        version: Optional[str] = None,
        username: Optional[str] = None,
    ) -> list[ChatPrompt]:
        """读取 ``prompt_setting.content``；``hidden-`` 前缀剥掉、``pause`` 映射为 ``assistant``。"""
        agent_config_info = cls.get_info(app_code=app_code, version=version, username=username)
        agent_role_content = agent_config_info["prompt_setting"].get("content", [])
        if not agent_role_content:
            return []

        for each in agent_role_content:
            each["role"] = each["role"].replace("hidden-", "")
            if each["role"] == "pause":
                each["role"] = "assistant"

        return [ChatPrompt(role=each["role"], content=each["content"]) for each in agent_role_content]

    @classmethod
    def clear_request_cache(cls) -> None:
        """显式清理当前请求线程上的缓存条目；测试或长期复用线程时使用。"""
        try:
            if hasattr(request_local, _REQUEST_CACHE_ATTR):
                delattr(request_local, _REQUEST_CACHE_ATTR)
        except Exception:
            logger.debug("clear_request_cache: request_local 不可用，忽略", exc_info=True)

    @staticmethod
    def _get_request_cache() -> Optional[dict]:
        """惰性获取请求级缓存字典；脱离请求上下文时返回 ``None``，调用方自行降级为不缓存。"""
        try:
            cache = getattr(request_local, _REQUEST_CACHE_ATTR, None)
            if cache is None:
                cache = {}
                setattr(request_local, _REQUEST_CACHE_ATTR, cache)
            return cache
        except Exception:
            logger.debug("request_local 不可用，agent config 缓存降级为不缓存", exc_info=True)
            return None

    @classmethod
    def set_info_without_user(
        cls,
        app_code: str,
        version: Optional[str],
        agent_info: dict,
    ) -> None:
        """把拉取成功的 ``agent_info`` 写入 django cache 全局 fallback。

        ``otel_info`` 缺失时跳过写入

        key 为 ``agent_info:{app_code}:{version}``不含 username
        写入前剥离属性(当前用户维度有 ``allowed_access``)

        timeout 固定 1 周：request cache 每请求重置 + 每次拉取成功都会刷新 django cache，正常情况下
        永远读不到过期；TTL 仅作为兜底数据最坏存活上限，避免后端长期故障 + 进程未重启时读到远古快照。

        cache 写异常 try/except 降级跳过——拉取已成功，cache 故障不应阻断主流程返回。
        agent_info 配置一般较少更新，应用到上一版本的配置是可以接受的

        用户态和无用户态的成功平台响应都可以刷新快照，以避免快照长期停留在应用启动时的旧版本。
        该快照只会在 ``AgentConfigFetcher.get_info`` 的无用户调用失败分支中读取；
        携带非空 ``username`` 的调用不会读取该快照，因此不会使用其他用户写入的快照替代当前用户的鉴权结果。

        响应不包含有效 ``otel_info`` 时不写入快照。cache 写入异常只记录日志，不会影响本次已经成功的平台响应。
        """
        if not agent_info.get("otel_info"):
            return
        key = f"{_DJANGO_CACHE_KEY_PREFIX}:{app_code}:{version}"
        projection = {k: v for k, v in agent_info.items() if k != "allowed_access"}
        try:
            _get_django_cache_backend().set(key, copy.deepcopy(projection), timeout=_FALLBACK_CACHE_TIMEOUT)
        except Exception:
            logger.debug("django cache 写入失败，降级跳过", exc_info=True)

    @classmethod
    def get_info_without_user(
        cls,
        app_code: str,
        version: Optional[str],
        platform_exc: Optional[BaseException] = None,
    ) -> dict:
        """读 django cache 全局 fallback；命中返回 ``deepcopy``，未命中抛 ``ValueError``。

        作为 ``get_info`` 在启动场景（``username`` 为空且后端不可达）的兜底入口：
        1. 命中 log info + 返回 deepcopy；
        2. 未命中 log error + 抛 ``ValueError``，由调用方冒泡（启动无法拉起进程）。


        携带用户上下文的请求不得调用本方法，也不得使用该快照替代用户态鉴权结果。
        缓存命中时返回 ``deepcopy``；未命中或读取失败时抛出异常，并保留原始平台异常链。
        """
        key = f"{_DJANGO_CACHE_KEY_PREFIX}:{app_code}:{version}"
        try:
            agent_info = copy.deepcopy(_get_django_cache_backend().get(key))
        except Exception as cache_exc:
            # cache.get 自身报错：原始平台异常已被吞，这里用 from 链上 platform_exc 保留根因
            logger.error(
                "retrieve_agent_config 失败（username 为空）且 django cache 读异常：app_code=%s version=%s",
                app_code,
                version,
                exc_info=True,
            )
            raise RuntimeError(f"retrieve_agent_config failed and django cache read error: app_code={app_code}") from (
                platform_exc or cache_exc
            )
        if agent_info is not None:
            logger.info(
                "retrieve_agent_config 失败（username 为空），使用 django cache 兜底：app_code=%s version=%s",
                app_code,
                version,
            )
            return agent_info
        logger.error(
            "retrieve_agent_config 失败且 django cache 兜底为空，抛出 ValueError：app_code=%s version=%s",
            app_code,
            version,
        )
        raise ValueError(
            f"Failed to retrieve agent config and no django cache fallback: app_code={app_code}"
        ) from platform_exc
