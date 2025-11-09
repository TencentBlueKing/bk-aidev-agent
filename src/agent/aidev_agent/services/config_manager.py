import time

from pydantic import BaseModel, Field

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.services.pydantic_models import AgentOptions, IntentRecognition, KnowledgebaseSettings


class AgentConfig(BaseModel):
    """智能体配置"""

    agent_code: str = Field(..., description="智能体代码")
    agent_name: str = Field(..., description="智能体名称")
    llm_model_name: str = Field(..., description="LLM模型名称")
    non_thinking_llm_model_name: str = Field(..., description="非深度思考模型")
    role_prompt: str | None = Field(None, description="角色提示词(平台)")
    knowledgebase_ids: list = Field(default_factory=list, description="知识库ID列表")
    knowledge_ids: list = Field(default_factory=list, description="知识ID列表")
    tool_codes: list = Field(default_factory=list, description="工具列表")
    opening_mark: str | None = Field(None, description="智能体开场白")
    generating_keyword: str | None = Field(description="生成关键词", default="生成中")
    mcp_server_config: dict | None = Field(None, description="MCP服务器配置")
    agent_options: AgentOptions = Field(..., description="智能体选项")
    command_agent_mapping: dict = Field(default_factory=dict, description="智能体映射关联")
    agent_prompt: str | None = Field(None, description="智能体提示词(内嵌)")


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
        role_prompt = "\n".join(
            item["content"]
            for item in res["prompt_setting"]["content"]
            if item["role"] == "system" or item["role"] == "hidden-system"
        )

        # 创建配置实例
        config = AgentConfig(
            agent_code=agent_code,
            agent_name=res["agent_name"],
            llm_model_name=res["prompt_setting"]["llm_code"],
            non_thinking_llm_model_name=res["prompt_setting"]["non_thinking_llm"] or "",
            role_prompt=role_prompt or None,
            knowledgebase_ids=res["knowledgebase_settings"]["knowledgebases"],
            tool_codes=res["related_tools"],
            opening_mark=res["conversation_settings"]["opening_remark"] or None,
            mcp_server_config=res.get("mcp_server_config", {}).get("mcpServers", {}),
            agent_options=AgentOptions(
                intent_recognition_options=IntentRecognition.model_validate(res.get("intent_recognition") or {}),
                knowledge_query_options=KnowledgebaseSettings.model_validate(res.get("knowledgebase_settings") or {}),
            ),
            command_agent_mapping={
                each["id"]: each["agent_code"] for each in res["conversation_settings"].get("commands", [])
            },
        )

        # 更新缓存
        cls._config_cache[agent_code] = CachedEntry(config, time.time())
        return config
