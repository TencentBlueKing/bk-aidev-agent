# -*- coding: utf-8 -*-

from django.db import models

__all__ = ["Checkpoint", "Write", "EventSubscription", "EventDelivery"]


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


class EventSubscription(models.Model):
    """Durable, application/session-scoped subscription, installed by trusted code."""

    key = models.CharField(max_length=64, unique=True)
    scope_key = models.CharField(max_length=64, db_index=True)
    subscriber = models.CharField(max_length=255)
    event_name = models.CharField(max_length=128)
    app_code = models.CharField(max_length=255)
    session_code = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    property = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class EventDelivery(models.Model):
    """One immutable event per subscriber; the lease/progress belong to delivery."""

    subscription = models.ForeignKey(EventSubscription, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=64)
    envelope = models.JSONField(default=dict)
    route = models.JSONField(default=dict)
    status = models.CharField(max_length=16, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    lease_token = models.CharField(max_length=32, default="")
    lease_until = models.DateTimeField(null=True)
    progress = models.PositiveIntegerField(default=0)
    error_type = models.CharField(max_length=128, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subscription", "event_id"], name="unique_event_delivery"),
        ]
        indexes = [models.Index(fields=["status", "available_at"], name="event_delivery_ready")]
