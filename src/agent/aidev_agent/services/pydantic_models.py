import os
from typing import Any, List, Literal, Tuple

from pydantic import AliasChoices, BaseModel, Field, model_validator

from aidev_agent.enums import FineGrainedScoreType, IndependentQueryMode, KnowledgeBaseQueryFunction


class ExecuteKwargs(BaseModel):
    stream: bool = False
    stream_timeout: int = 30
    passthrough_input: bool = False
    run_agent: bool = False


class SessionTool(BaseModel):
    tool_id: int
    tool_code: str
    icon: str
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


class SessionContentProperty(BaseModel):
    """会话内容的一些额外属性"""

    extra: SessionContentExtra | None = None


class ChatPrompt(BaseModel):
    id: int | None = None
    role: str
    content: str
    extra: SessionContentExtra | None = None

    @model_validator(mode="before")
    def validate_content_with_rendered(cls, values: Any) -> Any:
        extra = values.get("extra")
        if extra:
            if isinstance(extra, dict):
                rendered_content = extra.get("rendered_content")
                if rendered_content:
                    values["content"] = rendered_content
            elif hasattr(extra, "rendered_content") and extra.rendered_content:
                values["content"] = extra.rendered_content
        return values


class IntentRecognition(BaseModel):
    intent_recognition_knowledge: list[dict] | None = Field(default=None, description=("意图识别知识"))
    intent_recognition_topk: float | None = Field(default=None, description=("意图识别topk值"))
    intent_recognition_llm: str | None = Field(
        default=os.getenv("INTENT_RECOGNITION_LLM"), description="意图识别使用的LLM"
    )
    intent_recognition_fine_grained_score_type: FineGrainedScoreType = Field(
        default=FineGrainedScoreType(os.getenv("INTENT_FINE_GRAINED_SCORE_TYPE", "LLM")), description=("相关性判断模型")
    )
    intent_recognition_reject_threshold: Tuple[float, float] = Field(
        default=(
            float(os.getenv("INTENT_REJECT_THRESHOLD_MIN", "0.001")),
            float(os.getenv("INTENT_REJECT_THRESHOLD_MAX", "0.6")),
        ),
        description=("相关性阈值"),
    )
    enable_logging: bool = Field(
        default=os.getenv("ENABLE_LOGGING", "true").lower() == "true", description="是否启用日志记录"
    )
    intent_recognition_llm_code: str | None = Field(
        default=os.getenv("INTENT_RECOGNITION_LLM_CODE"), description=("约定的意图识别 code，用于快速单跳")
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
    tool_output_compress_thrd: int = Field(
        default=int(os.getenv("TOOL_OUTPUT_COMPRESS_THRD", "5000")), description=("工具输出压缩阈值")
    )
    agent_type: str | None = Field(default=os.getenv("AGENT_TYPE"), description=("agent类"))
    max_tool_output_len: int = Field(
        default=int(os.getenv("MAX_TOOL_OUTPUT_LEN", "500")), description=("工具调用结果展示的最大长度")
    )


class KnowledgebaseSettings(BaseModel):
    knowledge_bases: list[dict] = Field(default_factory=list, description=("关联知识库,有可能没有关联"))
    knowledge_items: list[dict] = Field(default_factory=list, description=("关联知识,可能没有关联"))
    qa_response_kb_ids: list[int] = Field(default_factory=list, description=("历史反馈问答知识库id,可能不存在"))
    qa_response_knowledge_bases: list[dict] = Field(default_factory=list, description=("历史反馈问答知识库,可能不存在"))
    retriever_code: str | None = Field(default=os.getenv("RETRIEVER_CODE"), max_length=255, description=("检索器ID"))
    query_function: KnowledgeBaseQueryFunction = Field(
        default=KnowledgeBaseQueryFunction(os.getenv("QUERY_FUNCTION", "semantic")), description=("查询方式")
    )
    document_fragment_count: int = Field(
        default=int(os.getenv("DOCUMENT_FRAGMENT_COUNT", "0")), description=("文档片段数")
    )
    knowledge_resource_fine_grained_score_type: FineGrainedScoreType = Field(
        default=FineGrainedScoreType(os.getenv("KNOWLEDGE_FINE_GRAINED_SCORE_TYPE", "LLM")),
        description=("相关性判断模型"),
    )
    knowledge_resource_reject_threshold: Tuple[float, float] = Field(
        default=(
            float(os.getenv("KNOWLEDGE_REJECT_THRESHOLD_MIN", "0.001")),
            float(os.getenv("KNOWLEDGE_REJECT_THRESHOLD_MAX", "0.1")),
        ),
        description=("相关性阈值"),
    )
    knowledge_resource_rough_recall_topk: int = Field(
        default=int(os.getenv("KNOWLEDGE_ROUGH_RECALL_TOPK", "10")),
        description=("知识类资源粗召 topk 值"),
        alias="topk",
    )
    independent_query_mode: IndependentQueryMode = Field(
        default=IndependentQueryMode(os.getenv("INDEPENDENT_QUERY_MODE", "SUM_AND_CONCATE")), description=("预处理逻辑")
    )
    polish: bool = Field(
        default=os.getenv("POLISH", "true").lower() == "true", description=("是否返回检索原始文档内容")
    )
    raw: bool = Field(default=os.getenv("RAW", "false").lower() == "true", description=("是否返回检索大模型总结内容"))
    knowledge_template_id: int | None = Field(
        default=int(os.getenv("KNOWLEDGE_TEMPLATE_ID", "0")) if os.getenv("AGENT_KNOWLEDGE_TEMPLATE_ID") else None,
        description=("检索内容返回模板ID"),
    )
    is_response_when_no_knowledgebase_match: bool = Field(
        default=os.getenv("IS_RESPONSE_WHEN_NO_KNOWLEDGEBASE_MATCH", "true").lower() == "true",
        description=("未命中知识库时根据通识回答"),
    )
    rejection_message: str = Field(
        default=os.getenv("REJECTION_MESSAGE", "无法根据当前文档回答当前问题。请更换问题。"),
        max_length=1024,
        description=("拒答文案"),
    )
    enable_parallel_tool_calls: bool = Field(
        default=os.getenv("ENABLE_PARALLEL_TOOL_CALLS", "true").lower() == "true",
        description=("StructuredChatCommonQAAgent调用多个工具时是否使用并行调用"),
    )
    with_scalar_data: bool = Field(
        default=os.getenv("WITH_SCALAR_DATA", "false").lower() == "true",
        description="是否使用标量索引进行结构化数据召回",
    )
    use_independent_query_in_translation: bool = Field(
        default=os.getenv("USE_INDEPENDENT_QUERY_IN_TRANSLATION", "false").lower() == "true",
        description=("翻译查询时是否使用独立查询(而非原始查询)作为输入源"),
    )
    use_translated_query_in_scores: bool = Field(
        default=os.getenv("USE_TRANSLATED_QUERY_IN_SCORES", "true").lower() == "true",
        description="计算相关性分数时是否使用翻译后的查询(而非原始查询)",
    )
    use_independent_query_in_scores: bool = Field(
        default=os.getenv("USE_INDEPENDENT_QUERY_IN_SCORES", "true").lower() == "true",
        description="计算相关性分数时是否使用独立查询(而非原始查询)",
    )
    with_query_cls: bool = Field(
        default=os.getenv("WITH_QUERY_CLS", "true").lower() == "true",
        description="是否进行意图切换检测。NOTE: 目前仅在非 merge_query_cls_with_resp_or_rewrite 的情况下才生效",
    )
    force_process_by_agent: bool = Field(
        default=os.getenv("FORCE_PROCESS_BY_AGENT", "false").lower() == "true",
        description=("是否强制进入 IntentStatus.PROCESS_BY_AGENT 的 status。用于 AIDEV 产品页面召回测试"),
    )
    role_prompt: str | None = Field(
        default=os.getenv("ROLE_PROMPT"),
        description=(
            "用户在 aidev 页面上创建 agent 时填写的 prompt。旧主站逻辑会将其与 prefix 拼接后作为整体外层 agent 的 system prompt。"
        ),
    )
    assets_list: str | None = Field(default=os.getenv("ASSETS_LIST"), description=("assets_list参数"))
    with_structured_data: bool = Field(
        default=os.getenv("WITH_STRUCTURED_DATA", "false").lower() == "true",
        description=("用户勾选的知识中是否带结构化数据。NOTE: 目前该值为 True 时才会进行 nature 方式的知识召回"),
    )
    with_index_specific_search: bool = Field(
        default=os.getenv("WITH_INDEX_SPECIFIC_SEARCH", "true").lower() == "true",
        description="是否使用基于 embedding 模型的 index specific 召回",
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
        description="是否使用 weighted reciprocal rank fusion 对多路召回的结果进行融合。",
    )
    self_query_threshold_top_n: int = Field(
        default=int(os.getenv("SELF_QUERY_THRESHOLD_TOP_N", "0")),
        description="""在第 1 步意图识别判断用户 query 是否涉及结构化数据的时候，
            使用全量检索结果的 top_n 中是否包含结构化数据来判断。
            NOTE: 当前先将其值置为0，即不开启 self query 分支。
            TODO: 后续去除 nature 分支后，即可将其值置为 5 等，开启 self query 分支。""",
    )
    tool_resource_rough_recall_topk: int = Field(
        default=int(os.getenv("TOOL_RESOURCE_ROUGH_RECALL_TOPK", "10")), description="工具类资源粗召 topk 值"
    )
    tool_resource_reject_threshold: Tuple[float, float] = Field(
        default=(
            float(os.getenv("TOOL_RESOURCE_REJECT_THRESHOLD_MIN", "0.25")),
            float(os.getenv("TOOL_RESOURCE_REJECT_THRESHOLD_MAX", "0.75")),
        ),
        description="工具类资源拒答和直接回答的阈值",
    )
    tool_resource_fine_grained_score_type: FineGrainedScoreType = Field(
        default=FineGrainedScoreType(os.getenv("TOOL_RESOURCE_FINE_GRAINED_SCORE_TYPE", "EXCLUSIVE_SIMILARITY_MODEL")),
        description="工具类资源进行细粒度的相似度计算的模型类型",
    )
    tool_count_threshold: int = Field(
        default=int(os.getenv("TOOL_COUNT_THRESHOLD", "10000")),
        description="当能够获取的工具的个数大于该阈值时，才开启工具类资源的粗召 + 精排，否则每次调用兜底LLM agent时都附上所有工具类资源",
    )
    gen_pseudo_tool_resource_desc: bool = Field(
        default=os.getenv("GEN_PSEUDO_TOOL_RESOURCE_DESC", "true").lower() == "true",
        description="在进行工具类资源的粗召时，是否进行伪工具类资源描述的生成",
    )
    retrieved_knowledge_resources: list = Field(default_factory=list, description="用户自带的历史检索的上下文")
    merge_query_cls_with_resp_or_rewrite: bool = Field(
        default=os.getenv("MERGE_QUERY_CLS_WITH_RESP_OR_REWRITE", "false").lower() == "true",
        description="是否将意图切换检测和 query 重写/直接答复合并在一次LLM调用中",
    )
    tool_resource_base_ids: List[int] = Field(
        default_factory=list,
        description=("工具类资源 base ID 列表。NOTE: 目前工具类资源统一放 base ID 中不放 item ID 中"),
    )
    token_limit_margin: int = Field(
        default=int(os.getenv("TOKEN_LIMIT_MARGIN", "100")), description=("上下文最大Token限制边界")
    )
    llm_token_limit: int = Field(default=int(os.getenv("LLM_TOKEN_LIMIT", "28000")), description=("LLM最大Token限制"))


class AgentOptions(BaseModel):
    # agent 执行选项
    intent_recognition_options: IntentRecognition = Field(default_factory=IntentRecognition, description="意图识别选项")
    knowledge_query_options: KnowledgebaseSettings = Field(
        default_factory=KnowledgebaseSettings, description="知识库查询选项"
    )
