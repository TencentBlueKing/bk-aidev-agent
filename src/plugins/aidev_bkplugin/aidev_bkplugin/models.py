# -*- coding: utf-8 -*-

from django.db import models

__all__ = ["Checkpoint", "Write"]


class Checkpoint(models.Model):
    thread_id = models.CharField(max_length=255)
    checkpoint_ns = models.CharField(max_length=255, default="")
    checkpoint_id = models.CharField(max_length=255)
    parent_checkpoint_id = models.TextField(null=True, blank=True)
    type = models.TextField(null=True, blank=True)
    checkpoint = models.BinaryField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["thread_id", "checkpoint_ns"]),
            models.Index(fields=["checkpoint_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),  # 清理任务使用此索引
        ]


class Write(models.Model):
    thread_id = models.CharField(max_length=255)
    checkpoint_ns = models.CharField(max_length=255, default="")
    checkpoint_id = models.CharField(max_length=255)
    task_id = models.CharField(max_length=255)
    task_path = models.TextField()
    idx = models.IntegerField()
    channel = models.TextField()
    type = models.TextField(null=True, blank=True)
    value = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["thread_id", "checkpoint_ns", "checkpoint_id"]),
            models.Index(fields=["task_id", "idx"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),  # 清理任务使用此索引
        ]
