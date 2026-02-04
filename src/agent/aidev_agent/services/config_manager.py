import time
from typing import Literal

from pydantic import BaseModel, Field

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.services.pydantic_models import AgentOptions, IntentRecognition, KnowledgebaseSettings


class AgentConfig(BaseModel):
    """智能体配置"""

    agent_code: str = Field(..., description="智能体代码")
    agent_name: str = Field(..., description="智能体名称")
    chat_model: str = Field(..., description="LLM模型名称")
    non_thinking_llm: str = Field(..., description="非深度思考模型")
    role_prompts: list[dict[Literal["role", "content"], str]] | None = Field(None, description="角色提示词(平台)")
    knowledgebase_ids: list = Field(default_factory=list, description="知识库ID列表")
    knowledge_ids: list = Field(default_factory=list, description="知识ID列表")
    tool_codes: list = Field(default_factory=list, description="工具列表")
    opening_mark: str | None = Field(None, description="智能体开场白")
    generating_keyword: str | None = Field(description="生成关键词", default="生成中")
    mcp_server_config: dict | None = Field(None, description="MCP服务器配置")
    agent_options: AgentOptions = Field(..., description="智能体选项")
    command_agent_mapping: dict = Field(default_factory=dict, description="智能体映射关联")
    agent_prompt: str | None = Field(None, description="智能体提示词(内嵌)")
    # 超参数配置
    temperature: float | None = Field(None, description="模型温度")
    max_tokens: int | None = Field(None, description="最大回复长度")


class CachedEntry:
    """缓存条目，包含配置和过期时间"""

    def __init__(self, config: AgentConfig, timestamp: float):
        self.config = config
        self.timestamp = timestamp

    def is_expired(self, ttl: int = 10) -> bool:
        """检查缓存是否过期，默认10秒过期时间"""
        return time.time() - self.timestamp > ttl


class AgentConfigManager:
    """智能体配置管理器"""

    _config_cache: dict[str, CachedEntry] = {}
    CACHE_TTL = 300  # 缓存过期时间（秒）

    @classmethod
    def get_config(
        cls, agent_code: str, resource_manager: AbstractBKAidevResourceManager, force_refresh: bool = False, **kwargs
    ) -> AgentConfig:
        """
        获取智能体配置
        :param agent_code: 智能体代码
        :param force_refresh: 是否强制刷新配置
        :param api_client: API客户端
        :return: AgentConfig实例
        """
        # 检查缓存中是否存在且不需要强制刷新
        if not force_refresh and agent_code in cls._config_cache:
            cached_entry = cls._config_cache[agent_code]
            # 检查缓存是否过期
            if not cached_entry.is_expired(cls.CACHE_TTL):
                return cached_entry.config
            # 如果过期，从缓存中删除
            del cls._config_cache[agent_code]

        # 实时从AIDev平台拉取配置
        try:
            res = resource_manager.retrieve_agent_config(agent_code)
        except Exception as e:
            # 添加适当的错误处理或日志记录
            raise ValueError(f"Failed to retrieve agent config: {e}")

        # 处理特殊字段,兼容特殊role
        role_prompts = res["prompt_setting"].get("content", None)

        # 创建配置实例
        prompt_setting = res.get("prompt_setting", {})
        knowledgebase_settings_data = res.get("knowledgebase_settings") or {}
        intent_recognition_data = res.get("intent_recognition") or {}

        # 将 prompt_setting 中的超参数合并到对应的配置中（SDK 期望从这些位置读取）
        # llm_token_limit 在 KnowledgebaseSettings 中使用
        knowledgebase_settings_data["llm_token_limit"] = prompt_setting.get("llm_token_limit")
        # tool_output_compress_thrd 在 IntentRecognition 中使用
        intent_recognition_data["tool_output_compress_thrd"] = prompt_setting.get("tool_output_compress_thrd")

        config = AgentConfig(
            agent_code=agent_code,
            agent_name=res["agent_name"],
            chat_model=prompt_setting.get("llm_code", ""),
            non_thinking_llm=prompt_setting.get("non_thinking_llm") or prompt_setting.get("llm_code", ""),
            role_prompts=role_prompts or None,
            knowledgebase_ids=res["knowledgebase_settings"]["knowledgebases"],
            tool_codes=res["related_tools"],
            opening_mark=res["conversation_settings"]["opening_remark"] or None,
            mcp_server_config=res.get("mcp_server_config", {}).get("mcpServers", {}),
            agent_options=AgentOptions(
                intent_recognition_options=IntentRecognition.model_validate(intent_recognition_data),
                knowledge_query_options=KnowledgebaseSettings.model_validate(knowledgebase_settings_data),
            ),
            command_agent_mapping={
                each["id"]: each["agent_code"] for each in res["conversation_settings"].get("commands", [])
            },
            # 超参数配置
            temperature=prompt_setting.get("temperature"),
            max_tokens=prompt_setting.get("max_tokens"),
        )

        # 更新缓存
        cls._config_cache[agent_code] = CachedEntry(config, time.time())
        return config
