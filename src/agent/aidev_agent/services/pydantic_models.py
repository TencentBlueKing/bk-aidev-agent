from enum import Enum
from typing import List, Literal, Optional, Tuple

from pydantic import AliasChoices, BaseModel, Field


class FineGrainedScoreType(Enum):
    LLM = "LLM"
    EXCLUSIVE_SIMILARITY_MODEL = "EXCLUSIVE_SIMILARITY_MODEL"
    EMBEDDING = "EMBEDDING"


class IndependentQueryMode(Enum):
    INIT = "INIT"  # 直接使用原始的，不进行重写
    REWRITE = "REWRITE"  # 根据 chat history 对 query 进行重写
    SUM_AND_CONCATE = "SUM_AND_CONCATE"  # 对 chat history 进行总结，并跟 query 进行拼接


class KnowledgeBaseQueryFunction(Enum):
    """检索方式"""

    SEMANTIC = "semantic"  # 语义检索
    MIXED = "mixed"  # 混合检索
    SQL = "sql"  # SQL检索


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


class SessionContentProperty(BaseModel):
    """会话内容的一些额外属性"""

    extra: SessionContentExtra | None = None


class ChatPrompt(BaseModel):
    id: int | None = None
    role: str
    content: str
    extra: SessionContentExtra | None = None


class IntentRecognition(BaseModel):
    intent_recognition_knowledgebase_id: Optional[list[int]] = Field(default=None, description=("意图识别知识库id"))
    intent_recognition_topk: float = Field(default=None, description=("意图识别topk值"))
    intent_recognition_llm: str = Field(default=None, description="意图识别使用的LLM")
    enable_logging: bool = Field(default=True, description="是否启用日志记录")
    intent_recognition_llm_code: str = Field(default=None, description=("约定的意图识别 code，用于快速单跳"))
    with_index_specific_search_init: bool = Field(
        default=True, description=("意图识别with_index_specific_search_init参数")
    )
    with_index_specific_search_translation: bool = Field(
        default=False, description=("意图识别with_index_specific_search_translation参数")
    )
    with_index_specific_search_keywords: bool = Field(
        default=False, description=("意图识别with_index_specific_search_keywords参数")
    )
    tool_output_compress_thrd: int = Field(default=5000, description=("工具输出压缩阈值"))


class KnowledgebaseSettings(BaseModel):
    knowledge_bases: list[dict] = Field(default_factory=list, description=("关联知识库,有可能没有关联"))
    knowledge_items: list[dict] = Field(default_factory=list, description=("关联知识,可能没有关联"))
    qa_response_kb_ids: list[int] = Field(default_factory=list, description=("历史反馈问答知识库id,可能不存在"))
    retriever_code: str = Field(default=None, max_length=255, description=("检索器ID"))
    query_function: KnowledgeBaseQueryFunction = Field(
        default=KnowledgeBaseQueryFunction.SEMANTIC, description=("查询方式")
    )
    document_fragment_count: int = Field(default=0, description=("文档片段数"))
    knowledge_resource_fine_grained_score_type: FineGrainedScoreType = Field(
        default=FineGrainedScoreType.LLM, description=("相关性判断模型")
    )
    knowledge_resource_reject_threshold: Tuple[float, float] = Field(
        default=(0.001, 0.1),
        description=("相关性阈值"),
    )
    knowledge_resource_rough_recall_topk: int = Field(default=10, description=("知识类资源粗召 topk 值"), alias="topk")
    independent_query_mode: IndependentQueryMode = Field(
        default=IndependentQueryMode.SUM_AND_CONCATE, description=("预处理逻辑")
    )
    polish: bool = Field(default=True, description=("是否返回检索原始文档内容"))
    raw: bool = Field(default=False, description=("是否返回检索大模型总结内容"))
    knowledge_template_id: int = Field(default=0, description=("检索内容返回模板ID"))
    use_general_knowledge_on_miss: bool = Field(default=True, description=("未命中知识库时根据通识回答"))
    rejection_response: str = Field(
        default="无法根据当前文档回答当前问题。请更换问题。", max_length=1024, description=("拒答文案")
    )
    with_scalar_data: bool = Field(default=False, description=("with_scalar_data参数"))
    use_independent_query_in_translation: bool = Field(
        default=False, description=("use_independent_query_in_translation参数")
    )
    use_translated_query_in_scores: bool = Field(default=True, description=("use_translated_query_in_scores参数"))
    use_independent_query_in_scores: bool = Field(default=True, description=("use_independent_query_in_scores参数"))
    with_query_cls: bool = Field(
        default=True,
        description="是否进行意图切换检测。NOTE: 目前仅在非 merge_query_cls_with_resp_or_rewrite 的情况下才生效",
    )
    force_process_by_agent: bool = Field(
        default=False, description=("是否强制进入 IntentStatus.PROCESS_BY_AGENT 的 status。用于 AIDEV 产品页面召回测试")
    )
    role_prompt: str = Field(
        default=None,
        description=(
            "用户在 aidev 页面上创建 agent 时填写的 prompt。旧主站逻辑会将其与 prefix 拼接后作为整体外层 agent 的 system prompt。"
        ),
    )
    assets_list: str = Field(default=None, description=("assets_list参数"))
    with_structured_data: bool = Field(
        default=False,
        description=("用户勾选的知识中是否带结构化数据。NOTE: 目前该值为 True 时才会进行 nature 方式的知识召回"),
    )
    with_index_specific_search: bool = Field(
        default=True, description="是否使用基于 embedding 模型的 index specific 召回"
    )
    with_es_search_query: bool = Field(default=False, description="是否使用原始 query 在 ES 上进行召回")
    with_es_search_keywords: bool = Field(default=False, description="是否使用 query 提取的关键词 在 ES 上进行召回")
    with_rrf: bool = Field(
        default=True, description="是否使用 weighted reciprocal rank fusion 对多路召回的结果进行融合。"
    )
    self_query_threshold_top_n: int = Field(
        default=0,
        description="""在第 1 步意图识别判断用户 query 是否涉及结构化数据的时候，
            使用全量检索结果的 top_n 中是否包含结构化数据来判断。
            NOTE: 当前先将其值置为0，即不开启 self query 分支。
            TODO: 后续去除 nature 分支后，即可将其值置为 5 等，开启 self query 分支。""",
    )
    tool_resource_rough_recall_topk: int = Field(default=10, description="工具类资源粗召 topk 值")
    tool_resource_reject_threshold: Tuple[float, float] = Field(
        default=(0.25, 0.75), description="工具类资源拒答和直接回答的阈值"
    )
    tool_resource_fine_grained_score_type: FineGrainedScoreType = Field(
        default=FineGrainedScoreType.EXCLUSIVE_SIMILARITY_MODEL.value,
        description="工具类资源进行细粒度的相似度计算的模型类型",
    )
    tool_count_threshold: int = Field(
        default=10000,
        description="当能够获取的工具的个数大于该阈值时，才开启工具类资源的粗召 + 精排，否则每次调用兜底LLM agent时都附上所有工具类资源",
    )
    gen_pseudo_tool_resource_desc: bool = Field(
        default=True, description="在进行工具类资源的粗召时，是否进行伪工具类资源描述的生成"
    )
    retrieved_knowledge_resources: List = Field(default=None, description="用户自带的历史检索的上下文")
    merge_query_cls_with_resp_or_rewrite: bool = Field(
        default=False, description="是否将意图切换检测和 query 重写/直接答复合并在一次LLM调用中"
    )
    tool_resource_base_ids: List[int] = Field(
        default_factory=list,
        description=("工具类资源 base ID 列表。NOTE: 目前工具类资源统一放 base ID 中不放 item ID 中"),
    )
    token_limit_margin: int = Field(default=200, description=("token_limit_margin参数"))

    class Config:
        arbitrary_types_allowed = True


class AgentOptions(BaseModel):
    # agent 执行选项
    intent_recognition_options: IntentRecognition = Field(default_factory=IntentRecognition, description="意图识别选项")
    knowledge_query_options: KnowledgebaseSettings = Field(
        default_factory=KnowledgebaseSettings, description="知识库查询选项"
    )
