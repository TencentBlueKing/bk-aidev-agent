"""
Django models for aidev_wxbot.
"""

from django.db import models
from django.utils import timezone


class AgentSession(models.Model):
    """Agent会话记录模型"""

    group_id = models.CharField(max_length=255, primary_key=True, verbose_name="群组ID")
    thread_id = models.CharField(max_length=255, verbose_name="线程ID")
    last_session_time = models.DateTimeField(verbose_name="最后会话时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "wxaibot_agent_session"
        verbose_name = "Agent会话"
        verbose_name_plural = "Agent会话"

    def __str__(self):
        return f"AgentSession(group_id={self.group_id}, thread_id={self.thread_id})"

    def is_session_valid(self, timeout_minutes: int = 30) -> bool:
        """
        检查会话是否仍然有效

        Args:
            timeout_minutes: 超时时间（分钟），默认30分钟

        Returns:
            bool: 会话是否有效
        """
        if not self.last_session_time:
            return False

        time_diff = timezone.now() - self.last_session_time
        return time_diff.total_seconds() < (timeout_minutes * 60)

    def update_session(self, thread_id: str = None):
        """
        更新会话信息

        Args:
            thread_id: 新的线程ID，如果为None则保持原值
        """
        if thread_id is not None:
            self.thread_id = thread_id
        self.last_session_time = timezone.now()
        self.save()
