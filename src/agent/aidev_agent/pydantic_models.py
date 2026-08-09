from __future__ import annotations

import os
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from aidev_agent.enums import FineGrainedScoreType, IndependentQueryMode


class ExecuteKwargs(BaseModel):
    stream: bool = False
    stream_mode: Literal["start", "attach"] = Field(
        default="start",
        description="流式请求模式：start 可创建生产者，attach 仅回放/接管已有流",
    )
    stream_timeout: int = 30
    invoke_timeout: Optional[int] = None
    passthrough_input: bool = False
    run_agent: bool = False
    resume: Any | None = Field(default=None, description="interrupt后续流resume参数")
    # 新增参数
    executor: str | None = Field(default=None, description="调用人")
    session_code: str | None = Field(default=None, description="调用时的会话 ID")
    caller_bk_app_code: str | None = Field(default=None, description="调用者BK应用ID")
    caller_bk_biz_env: str | None = Field(default=None, description="调用者BK业务环境")
    caller_bk_biz_id: int | None = Field(default=None, description="调用者BK业务ID")
    caller_executor: str | None = Field(default=None, description="调用人")
    caller_order_type: str | None = Field(default=None, description="调用AI工单类型")
    caller_trace_context: Dict[str, Any] | None = Field(default=None, description="调用链ID")
    thread_id: str | None = Field(default=None, description="Thread ID，用于APIGW调用时自动管理会话")
    version: str | None = Field(default=None, description="agent 配置版本；为空则使用最新版本")
    turn_id: str = Field(default="", description="同一次 user-ai 回复的轮次 ID")
    input: str = Field(default="", description="用户本轮输入文本；为空串表示无输入")

    # 执行配置
    legacy_streaming: bool = Field(default=False, description="是否使用 legacy streaming protocol")
    persist_input: bool = Field(default=False, description="当为 True 时，后端自动创建 session 并写入 session_content")
    background_only: bool = Field(
        default=False,
        description=(
            "后台 drain 执行标志（无 SSE 下游，如 celery/flow 的 run_agent_to_completion）。"
            "为 True 时，消费者读到 EOD 不立即清理队列，保留缓存历史供前端在清理窗口内接管续流，"
            "清理交由 producer 的延迟清理线程兜底。"
        ),
    )


class SessionTool(BaseModel):
    tool_id: int
    tool_code: str
    icon: str | None = None
    tool_name: str = Field(validation_alias=AliasChoices("tool_name", "tool_cn_name"))
    description: str
    is_sensitive: bool
    status: Literal["ready", "deleted"] = "ready"
    property: dict = Field(default_factory=dict)

    @classmethod
    def get_model_fields_list_without_default_values(cls) -> list[str]:
        field_list = []
        for name, field_info in cls.model_fields.items():
            if field_info.default:
                continue
            field_list.append(name)
        return field_list


class SessionContentExtra(BaseModel):
    """会话内容的一些额外属性"""

    tools: list[SessionTool] = Field(default_factory=list)
    anchor_path_resources: dict = Field(default_factory=dict)
    context: list[dict] | None = None
    command: str | None = None
    rendered_content: str | None = None
    resources: list[dict] | None = None


class SessionContentProperty(BaseModel):
    """会话内容的一些额外属性"""

    turn_id: str = Field(default="", description="同一次 user-ai 回复的轮次 ID")
    extra: SessionContentExtra | None = None


class ChatPrompt(BaseModel):
    id: str | None = None
    role: str
    content: str | list[str] | dict | list[dict]
    extra: SessionContentExtra | None = None
    # 开放字典，透传任意协议字段
    builtin_property: Dict = Field(default_factory=dict, description="协议扩展属性，透传任意字段")

    @model_validator(mode="before")
    def validate_content_with_rendered(cls, values: Any) -> Any:
        # 将 id 转换为字符串（平台返回的可能是 int）
        if (id_val := values.get("id")) is not None:
            values["id"] = str(id_val)
        extra = values.get("extra")
        if extra:
            if isinstance(extra, dict):
                rendered_content = extra.get("rendered_content")
                if rendered_content:
                    values["content"] = rendered_content
            elif hasattr(extra, "rendered_content") and extra.rendered_content:
                values["content"] = extra.rendered_content
        return values


class ModelContextSettings(BaseModel):
    """模型上下文配置。

    整合了控制 LLM 推理行为的参数，包括 Token 限制等。
    这些参数原先散落在 KnowledgeSettings 中，实际上与知识检索无关，
    而是控制模型节点的行为。
    """

    llm_token_limit: int = Field(
        default=int(os.getenv("LLM_TOKEN_LIMIT", "36000")),
        description="LLM最大Token限制",
    )
    token_limit_margin: int = Field(
        default=int(os.getenv("TOKEN_LIMIT_MARGIN", "100")),
        description="上下文最大Token限制边界",
    )
    tool_output_compress_thrd: int = Field(
        default=int(os.getenv("TOOL_OUTPUT_COMPRESS_THRD", "5000")),
        description="工具输出压缩阈值",
    )
    llm_code_agent_type: str | None = Field(
        default=None, description="模型类型（如 openai / deepseek_r1），从 intent_recognition 获取"
    )


class KnowledgeSettings(BaseModel):
    """知识库检索配置。

    整合了与知识库检索相关的字段，包括拒答文案。
    retrievers 包内部统一使用此模型。
    """

    # --- 知识库 / 知识条目 ---
    knowledge_bases: list[dict] = Field(default_factory=list, description="关联知识库")
    knowledge_items: list[dict] = Field(default_factory=list, description="关联知识条目")

    # --- QA 响应知识库 ---
    qa_response_kb_ids: list[int] = Field(default_factory=list, description="历史反馈问答知识库id")
    qa_response_knowledge_bases: list[dict] = Field(default_factory=list, description="历史反馈问答知识库")

    # --- 召回参数 ---
    knowledge_resource_fine_grained_score_type: FineGrainedScoreType = Field(
        default=FineGrainedScoreType(os.getenv("KNOWLEDGE_FINE_GRAINED_SCORE_TYPE", "LLM")),
        description="相关性判断模型",
    )
    knowledge_resource_reject_threshold: Tuple[float, float] = Field(
        default=(
            float(os.getenv("KNOWLEDGE_REJECT_THRESHOLD_MIN", "0.001")),
            float(os.getenv("KNOWLEDGE_REJECT_THRESHOLD_MAX", "0.1")),
        ),
        description="相关性阈值",
    )
    knowledge_resource_rough_recall_topk: int = Field(
        default=int(os.getenv("KNOWLEDGE_ROUGH_RECALL_TOPK", "10")),
        description="知识类资源粗召 topk 值",
    )
    rrf_weights: dict[str, float] = Field(
        default_factory=dict,
        description="dense 与 sparse 召回通道的 RRF 融合权重",
    )
    recall_channels: list[str] | None = Field(
        default=None,
        description="向量召回通道；未传沿用平台兼容策略，空列表表示纯标量召回",
    )
    scalar_expression: str = Field(
        default="",
        description="step-1 根级标量检索表达式",
    )
    self_query_threshold_top_n: int = Field(
        default=int(os.getenv("SELF_QUERY_THRESHOLD_TOP_N", "0")),
        description="self query 判断结构化数据的 top_n 阈值",
    )
    # --- 拒答配置 ---
    rejection_message: str = Field(
        default=os.getenv("REJECTION_MESSAGE", "无法根据当前绑定的资源回答问题，请更换问题。"),
        max_length=1024,
        description="拒答文案",
    )
    is_response_when_no_knowledgebase_match: bool = Field(
        default=os.getenv("IS_RESPONSE_WHEN_NO_KNOWLEDGEBASE_MATCH", "true").lower() == "true",
        description="未命中知识库时根据通识回答",
    )
    # --- 召回策略开关 ---
    with_index_specific_search: bool = Field(
        default=os.getenv("WITH_INDEX_SPECIFIC_SEARCH", "true").lower() == "true",
        description="是否使用基于 embedding 模型的 index specific 召回",
    )
    with_index_specific_search_init: bool = Field(
        default=os.getenv("WITH_INDEX_SPECIFIC_SEARCH_INIT", "true").lower() == "true",
        description="是否使用初始查询进行 index specific 召回",
    )
    with_index_specific_search_translation: bool = Field(
        default=os.getenv("WITH_INDEX_SPECIFIC_SEARCH_TRANSLATION", "false").lower() == "true",
        description="是否使用翻译后的查询进行 index specific 召回",
    )
    with_index_specific_search_keywords: bool = Field(
        default=os.getenv("WITH_INDEX_SPECIFIC_SEARCH_KEYWORDS", "false").lower() == "true",
        description="是否使用提取的关键词进行 index specific 召回",
    )
    with_es_search_query: bool = Field(
        default=os.getenv("WITH_ES_SEARCH_QUERY", "false").lower() == "true",
        description="是否使用原始 query 在 ES 上进行召回",
    )
    with_es_search_keywords: bool = Field(
        default=os.getenv("WITH_ES_SEARCH_KEYWORDS", "false").lower() == "true",
        description="是否使用 query 提取的关键词 在 ES 上进行召回",
    )
    with_rrf: bool = Field(
        default=os.getenv("WITH_RRF", "true").lower() == "true",
        description="是否使用 weighted reciprocal rank fusion 对多路召回的结果进行融合",
    )
    with_structured_data: bool = Field(
        default=os.getenv("WITH_STRUCTURED_DATA", "false").lower() == "true",
        description="用户勾选的知识中是否带结构化数据",
    )
    with_scalar_data: bool = Field(
        default=os.getenv("WITH_SCALAR_DATA", "false").lower() == "true",
        description="是否使用标量索引进行结构化数据召回",
    )
    with_query_cls: bool = Field(
        default=os.getenv("WITH_QUERY_CLS", "true").lower() == "true",
        description="是否进行意图切换检测",
    )
    merge_query_cls_with_resp_or_rewrite: bool = Field(
        default=os.getenv("MERGE_QUERY_CLS_WITH_RESP_OR_REWRITE", "false").lower() == "true",
        description="是否将意图切换检测和 query 重写/直接答复合并在一次LLM调用中",
    )
    # --- 查询预处理 ---
    independent_query_mode: IndependentQueryMode = Field(
        default=IndependentQueryMode(os.getenv("INDEPENDENT_QUERY_MODE", "SUM_AND_CONCATE")),
        description="预处理逻辑",
    )
    use_independent_query_in_translation: bool = Field(
        default=os.getenv("USE_INDEPENDENT_QUERY_IN_TRANSLATION", "false").lower() == "true",
        description="翻译查询时是否使用独立查询",
    )
    use_translated_query_in_scores: bool = Field(
        default=os.getenv("USE_TRANSLATED_QUERY_IN_SCORES", "true").lower() == "true",
        description="计算相关性分数时是否使用翻译后的查询",
    )
    use_independent_query_in_scores: bool = Field(
        default=os.getenv("USE_INDEPENDENT_QUERY_IN_SCORES", "true").lower() == "true",
        description="计算相关性分数时是否使用独立查询",
    )

    # --- 检索查询参数 ---
    knowledge_template_id: int | None = Field(
        default=int(os.getenv("KNOWLEDGE_TEMPLATE_ID", "0")) if os.getenv("AGENT_KNOWLEDGE_TEMPLATE_ID") else None,
        description="检索内容返回模板ID",
    )
    enable_query_clarification: bool = Field(
        default=os.getenv("ENABLE_QUERY_CLARIFICATION", "true").lower() == "true",
        description="当用户查询模糊时是否启用查询澄清",
    )
    enable_knowledge_node: bool = Field(
        default=os.getenv("ENABLE_KNOWLEDGE_NODE", "true").lower() == "true",
        description="控制是否开启两步 RAG 使用 knowledge",
    )
    enable_agentic_rag_tool: bool = Field(
        default=os.getenv("ENABLE_AGENTIC_RAG_TOOL", "false").lower() == "true",
        description="控制是否开启知识库召回工具",
    )


class IntentRecognition(BaseModel):
    """旧版意图识别配置兼容模型。

    仅用于兼容历史 ``AgentOptions`` 入参；旧字段通过 ``extra`` 保留，运行时会迁移到新配置模型。
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=True)


class KnowledgebaseSettings(BaseModel):
    """旧版知识库配置兼容模型。

    除 ``rejection_message`` 兼容字段外，不再声明历史字段；旧字段通过 ``extra`` 保留并迁移。
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    rejection_message: str = Field(
        default=os.getenv("REJECTION_MESSAGE", "无法根据当前绑定的资源回答问题，请更换问题。"),
        max_length=1024,
        description="拒答文案",
        deprecated="Use KnowledgeSettings.rejection_message instead",
    )


class AgentOptions(BaseModel):
    """旧版 Agent 执行选项兼容模型。"""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    intent_recognition_options: IntentRecognition = Field(default_factory=IntentRecognition, description="意图识别选项")
    knowledge_query_options: KnowledgebaseSettings = Field(
        default_factory=KnowledgebaseSettings, description="知识库查询选项"
    )


class AgentExecutorKwargs(BaseModel):
    """Agent 执行器构建参数（标准协议）。

    该模型用于定义 `ChatCompletionAgent` 与 agent 执行器构建器（例如 `ReActAgentBuilder`）之间的参数协议。

    - 框架使用方可通过 **继承** 该模型来扩展自定义参数。
    - 该模型配置为 `extra='allow'`，因此平台通用配置字段也可直接透传（并可在 CommonQAAgent 中继续向下游 Builder 透传）。

    自定义扩展示例：
        class MyCustomKwargs(AgentExecutorKwargs):
            custom_param: str | None = None

        class MyCustomAgent(CommonQAAgent):
            @classmethod
            def get_agent_executor(cls, config: MyCustomKwargs | None = None, **kwargs):
                if config is not None:
                    custom_value = config.custom_param
                    builder_kwargs = config.model_dump(exclude_none=True, exclude={"custom_param"})
                else:
                    builder_kwargs = kwargs
                # ... custom logic

    说明：
    - 为避免模块加载时引入 langchain 依赖/循环依赖，这里对 langchain 相关类型统一使用 Any。
    - 运行时接受的实际类型包括：BaseChatModel、BaseTool、BaseMessage、ByteStore、BaseCallbackHandler、BaseCheckpointSaver 等。
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    # 核心模型配置
    llm: Optional[Any] = Field(default=None, description="用于 agent 执行的主模型（BaseChatModel）")
    knowledge_llm: Optional[Any] = Field(
        default=None, description="用于知识检索的模型（BaseChatModel；未设置时通常与 llm 相同）"
    )
    non_thinking_llm: Optional[Any] = Field(default=None, description="非深度思考模型（BaseChatModel 或 str）")
    fast_llm: Optional[Any] = Field(
        default=None,
        description="快速/轻量模型（BaseChatModel），用于 quality_gate 判断 LLM 等辅助任务；未设置时回退到 non_thinking_llm",
    )

    # 模型上下文配置（由上层从 AgentConfig 转换而来，控制 LLM 推理行为）
    model_context_options: Optional[ModelContextSettings] = Field(
        default=None, description="模型上下文配置（ModelContextSettings）"
    )
    chat_history: Optional[List[Any]] = Field(
        default=None, description="上下文聊天历史（不包含当前消息）（List[BaseMessage]）"
    )
    # 知识库检索配置（由上层从 AgentConfig 转换而来，供 retrievers 包使用）
    knowledge_query_options: Optional[KnowledgeSettings] = Field(
        default=None, description="知识库检索配置（KnowledgeSettings）"
    )
    # 工具
    extra_tools: Optional[List[Any]] = Field(default=None, description="额外可用工具（List[BaseTool]）")

    # 运行时配置
    tool_execution_interval: int = Field(default=10, description="工具执行/调用间隔（秒）")
    support_vision: bool = Field(default=False, description="是否支持视觉/图片能力")
    file_store: Optional[Any] = Field(default=None, description="文件存储后端（ByteStore）")
    callbacks: Optional[List[Any]] = Field(
        default=None, description="LangChain 回调（用于监控/trace）（List[BaseCallbackHandler]）"
    )

    # Agent 执行选项（框架已有模型）
    agent_options: Optional[AgentOptions] = Field(default=None, description="Agent 执行选项（AgentOptions）")

    # 执行上下文
    execute_kwargs: Optional[ExecuteKwargs] = Field(default=None, description="执行参数（包含 stream 等设置）")

    # Checkpoint（对话状态持久化）
    checkpointer: Optional[Any] = Field(default=None, description="对话状态检查点保存器（BaseCheckpointSaver）")

    # 关联技能配置
    skills: Optional[list] = Field(default=None, description="关联技能配置")

    # 执行用户信息
    executor_info: Optional[dict] = Field(default=None, description="执行用户信息")
    # 子 Agent 规格列表
    subagent_specs: Optional[list[Any]] = Field(
        default=None,
        description="子 Agent 配置列表",
    )

    # 资源管理器(resource_manager()是全局单例 会使用平台的app_code，这里使用per-request即每次chat_completion请求创建）
    resource_manager: Optional[Any] = Field(
        default=None,
        description="per-request 资源管理器实例（ResourceManagerProtocol）；"
        "缺省时 ReActAgentBuilder 回退到全局 resource_manager() 工厂。",
    )

    # 运行时后端解析器（RuntimeBackendResolver 实例）
    runtime_backend_resolver: Optional[Any] = Field(
        default=None,
        description="运行时后端解析器实例（RuntimeBackendResolver）；"
        "由 ChatAgentBuilder 构造并传入，用于管理沙箱资源生命周期。"
        "缺省时若 enable_runtime_tool=True，build() 将抛出异常。",
    )


class AgentConfig(BaseModel):
    """智能体配置"""

    agent_code: str = Field(..., description="智能体代码")
    agent_name: str = Field(..., description="智能体名称")
    chat_model: str = Field(..., description="LLM模型名称")
    fallback_model: str | None = Field(default=None, description="主模型请求失败时使用的备用模型")
    non_thinking_llm: str = Field(..., description="非深度思考模型")
    role_prompts: list[dict[Literal["role", "content"], str]] | None = Field(None, description="角色提示词(平台)")
    model_context_options_data: dict = Field(
        default_factory=dict, description="模型上下文配置原始数据，待 ChatAgentBuilder 构建 ModelContextSettings"
    )
    knowledgebase_ids: list = Field(default_factory=list, description="知识库ID列表")
    knowledge_ids: list = Field(default_factory=list, description="知识ID列表")
    knowledge_query_options_data: dict = Field(
        default_factory=dict, description="知识库检索配置原始数据，待 ChatAgentBuilder 构建 KnowledgeSettings"
    )
    tool_codes: list = Field(default_factory=list, description="工具列表")
    related_tools: dict | list | None = Field(None, description="关联工具原始配置")
    opening_mark: str | None = Field(None, description="智能体开场白")
    generating_keyword: str | None = Field(description="生成关键词", default="生成中")
    mcp_server_config: dict | None = Field(None, description="MCP服务器配置")
    related_skills: list | None = Field(None, description="关联技能配置")
    approval_settings: dict | None = Field(None, description="审批策略配置")
    resources: list[dict] = Field(default_factory=list, description="资源列表（含 id/code/type 映射）")
    agent_options: AgentOptions | None = Field(
        default=None,
        description="旧版智能体选项，仅用于兼容外部 resource_manager 返回的历史 AgentConfig",
        deprecated="Use model_context_options_data and knowledge_query_options_data instead",
    )
    command_agent_mapping: dict = Field(default_factory=dict, description="智能体映射关联")
    # 超参数配置
    temperature: float | None = Field(None, description="模型温度")
    max_tokens: int | None = Field(None, description="最大回复长度")
    related_agents: list[dict] = Field(
        default_factory=list,
        description="关联子智能体列表，从 API 响应顶层 related_agents 读取，每条含 agent_code/agent_name/description/api_url",
    )
    # 原始配置信息（来自 retrieve_agent_config 的完整字典，含 otel_info 等平台透传字段）
    agent_info: dict | None = Field(None, description="智能体配置信息，agent_info 接口的原始值，仅仅用于数据上报")
