from __future__ import annotations

import os
from enum import Enum
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictInt, model_validator

from aidev_agent.config import settings
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

    # A2A 嵌套控制
    spawn_depth: int = Field(default=0, description="当前嵌套深度，主 Agent 为 0")
    spawned_by: str | None = Field(default=None, description="父会话 session_code")
    max_spawn_depth: int = Field(default=1, description="最大嵌套深度")
    tool_deny: list[str] = Field(default_factory=list, description="工具黑名单（工具名）")
    tool_allow: list[str] = Field(default_factory=list, description="工具允许列表（工具名），非空时仅允许列表内工具")

    # A2A PV 共享
    sandbox_pv_id: str | None = Field(default=None, description="父 Agent 的沙箱 PV ID，子 Agent 通过此字段复用父 PV")

    CALLER_CONTEXT_FIELDS: ClassVar[tuple[str, ...]] = (
        "caller_bk_app_code",
        "caller_bk_biz_env",
        "caller_bk_biz_id",
        "caller_executor",
        "caller_order_type",
        "executor",
    )

    def to_caller_context(self) -> dict[str, Any]:
        """抽取可持久化到 ``ChatSession.property.caller_context`` 的调用方字段。

        不含 ``caller_trace_context``：那是当次请求的 W3C 头，不应跨 resume 复用。
        """
        data: dict[str, Any] = {}
        for name in self.CALLER_CONTEXT_FIELDS:
            value = getattr(self, name, None)
            if value not in (None, ""):
                data[name] = value
        return data

    def apply_caller_context(self, data: dict[str, Any] | None, *, overwrite: bool = False) -> ExecuteKwargs:
        """用会话 ``caller_context`` 填回空字段；``overwrite=True`` 时覆盖已有值（resume）。"""
        if not data:
            return self
        for name in self.CALLER_CONTEXT_FIELDS:
            stored = data.get(name)
            if stored in (None, ""):
                continue
            if overwrite or getattr(self, name, None) in (None, ""):
                setattr(self, name, stored)
        return self

    def apply_session_caller_defaults(self, username: str | None = None) -> ExecuteKwargs:
        """仅补齐 ``executor`` / ``caller_executor``，已有值不覆盖。

        ``caller_bk_app_code`` / ``caller_bk_biz_env`` / ``caller_bk_biz_id`` /
        ``caller_order_type`` 来自调用方入参（HTTP ``execute_kwargs``、BKFlow 工单表单、
        A2A ``spec.params``），此处不填默认值。
        """
        resolved = self.executor or self.caller_executor or username or None
        if resolved:
            self.executor = self.executor or resolved
            self.caller_executor = self.caller_executor or resolved
        return self


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
    trace_id: str = Field(default="", description="chat 入口 Trace ID；仅创建时传递，未提供时保持为空，更新时不修改")
    extra: SessionContentExtra | None = None
    # 前端输入框富文本结构，存储协议统一放在 property.docSchema 下。
    docSchema: list | None = Field(default=None, description="前端输入框富文本结构")  # noqa: N815


class ChatPrompt(BaseModel):
    model_config = ConfigDict(extra="allow")  # 透传任意非声明键（status/created_at/session_code/liked/property 原文等）

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
    enable_judge_response: bool = Field(default=False, description="是否启用任务完成度评估")
    context_window: int = Field(default=16, description="上下文窗口轮数上限（user 消息条数），超限在装配期截断")


class KnowledgeSettings(BaseModel):
    """知识库检索配置。

    整合了与知识库检索相关的字段，包括拒答文案。
    retrievers 包内部统一使用此模型。
    """

    # --- 知识库 / 知识条目 ---
    knowledge_bases: list[dict] = Field(default_factory=list, description="关联知识库")
    knowledge_items: list[dict] = Field(default_factory=list, description="关联知识条目")

    supports_multimodal_query: bool = Field(
        default=False,
        description="目标平台支持多模态知识查询；缺省沿用提取文字的兼容请求",
    )

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
    with_rrf: bool = Field(
        default=os.getenv("WITH_RRF", "true").lower() == "true",
        description="是否使用 weighted reciprocal rank fusion 对多路召回的结果进行融合",
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
        default=False,
        description="控制是否开启两步 RAG 使用 knowledge",
    )
    enable_agentic_rag_tool: bool = Field(
        default=True,
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


_DISABLE_VALUES = {"0", "false", "no", "off", "disable", "disabled"}


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔型环境变量。

    未设置返回 ``default``；命中禁用值（``0`` / ``false`` / ``no`` / ``off`` /
    ``disable`` / ``disabled``，不区分大小写）返回 ``False``，其余返回 ``True``。
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in _DISABLE_VALUES


class SandboxMode(str, Enum):
    """沙箱隔离模式（平台无关，Linux/macOS/Windows 共用语义）。"""

    READONLY = "readonly"
    WORKSPACE_WRITE = "workspace_write"
    FULL_ACCESS = "full_access"


class SandboxPolicy(BaseModel):
    """平台无关的沙箱安全策略。

    描述「沙箱应该如何隔离」，由各平台后端（Linux bwrap / macOS Seatbelt /
    Windows 受限令牌+AppContainer）翻译成各自的隔离机制。核心策略只收敛
    三平台能力的最小公共子集：文件（只读/可写出口/拒绝路径）、网络（开关+
    域名白名单）、模式（三档）。syscall/capability 等平台特有项作为扩展字段，
    由各后端按能力实现，不在核心策略中强制。

    字段语义：
    - ``mode``：隔离模式三档（readonly / workspace_write / full_access）。
    - ``readonly_paths``：只读挂载路径（系统命令 + 动态库），默认不含 /etc、
      /root、/home 等敏感目录。
    - ``writable_paths``：可写出口（通常仅工作区根）。
    - ``deny_paths``：敏感路径强制拒绝（如 /etc/ssh、~/.ssh、~/.aws），
      沙箱内「不存在」而非「无权限」。
    - ``allow_network``：是否保留网络；默认关闭，阻断外泄/SSRF。
    - ``allow_network_domains``：网络白名单域名（空则完全禁网）。
    - ``drop_privileges``：是否降权（Linux user namespace / macOS Seatbelt /
      Windows 非提升令牌）；默认开启。
    """

    mode: SandboxMode = Field(default=SandboxMode.WORKSPACE_WRITE, description="隔离模式三档")
    readonly_paths: list[str] = Field(
        default_factory=lambda: ["/usr", "/bin", "/lib", "/lib64"],
        description="只读挂载路径（系统命令 + 动态库），不含 /etc、/root、/home 等敏感目录",
    )
    writable_paths: list[str] = Field(default_factory=list, description="可写出口（通常仅工作区根）")
    deny_paths: list[str] = Field(default_factory=list, description="敏感路径强制拒绝（如 /etc/ssh、~/.ssh、~/.aws）")
    allow_network: bool = Field(default=False, description="是否保留网络；默认关闭（阻断外泄/SSRF）")
    allow_network_domains: list[str] = Field(default_factory=list, description="网络白名单域名（空则完全禁网）")
    drop_privileges: bool = Field(default=True, description="是否降权（默认开启）")


class SecurityRedactionSettings(BaseModel):
    """脱敏专用配置（独立于命令 / 网络 / 沙箱等安全开关）。

    原为 ``SecuritySettings`` 顶层的 17 个脱敏字段（16 个 ``redact_*`` +
    ``known_sensitive_values``）及专属 mandatory 校验器。提取为独立模型后，
    脱敏引擎（``packages.security.redaction``）与工具结果 guard 只依赖本模型，
    不再耦合总配置；总配置经 ``SecuritySettings.redaction`` 嵌套持有。

    取值来源分两级（与迁移前一致）：

    1. 字段默认工厂从环境变量读取（本地开发 / 兜底）；
    2. 平台侧在 ``agent_info["security_settings"]["redaction"]`` 下发同名字段时，
       由 ``SecuritySettings`` 直接构造（嵌套 dict 由 pydantic 投影）以平台值覆盖环境变量。

    本模型**不提供**自定义构造入口 —— 平台下发入口唯一保留在总配置
    ``SecuritySettings``（故旧扁平脱敏键不再生效，被 extra-ignore 忽略）。

    设计意图：
    - 评估时逐项关闭（观察单个脱敏能力对行为 / 性能的影响）；
    - 出问题（误拦截 / 误放行）时通过平台下发关闭（应急熔断）。

    **开关模型（全字段平等，无不可关项）**：
    - ``enable_redact_secrets`` 是**总开关**：置 False 时**三条脱敏出口全部熔断** ——
      文本引擎（``_detectors_for_scan`` 返回空列表）、结构化字段掩码
      （``redact_payload`` 凭据字段分支立即返回原对象）、runtime 工具结果脱敏
      （经文本引擎，同样不替换）均不执行，任何子项都无法绕过；
    - 其余各 ``enable_redact_*`` 是**分项开关**：作用域仅限自己的 detector，
      平台下发 False 即真关闭。历史上曾有一层「mandatory 不可关闭」
      （``registered`` / ``authorization_headers`` / ``private_keys`` 被平台下发
      False 时静默归 True，D-06），该层已删除 —— 它让总开关无法真正断开全部能力，
      与「所有功能都需要有开关」冲突。
    - 分项开关 `False` **不代表该能力彻底失效**：脱敏是分层兜底的多 detector 管线，
      同一份文本可能被更高层的 detector 命中（例如关闭 ``enable_redact_structured_fields``
      后，`password=<高熵值>` 仍可能由裸熵兜底遮掉）。要**彻底**关闭脱敏，用总开关。
    """

    model_config = ConfigDict(extra="ignore")

    # ---- 脱敏总开关（硬熔断：置 False 时引擎完全不跑，无任何子项可绕过）----
    enable_redact_secrets: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_SECRETS", True),
        description="脱敏总开关；置 False 时全部 detector 均不参与扫描（硬熔断）",
    )
    # ---- 脱敏分项开关（全字段平等，均可被平台 / 环境变量关闭）----
    enable_redact_registered_secrets: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_REGISTERED_SECRETS", True),
        description="已知 secret 精确值脱敏（可逐项关闭）",
    )
    enable_redact_authorization_headers: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_AUTHORIZATION_HEADERS", True),
        description="Authorization / API key header 脱敏（可逐项关闭）",
    )
    enable_redact_private_keys: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_PRIVATE_KEYS", True),
        description="PEM/PGP private key 脱敏（可逐项关闭）",
    )
    enable_redact_jwt: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_JWT", True),
        description="JWT 脱敏（可逐项关闭）",
    )
    enable_redact_vendor_tokens: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_VENDOR_TOKENS", True),
        description="厂商前缀 Token 脱敏（optional，可逐项关闭）",
    )
    enable_redact_structured_fields: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_STRUCTURED_FIELDS", True),
        description="结构化凭据字段脱敏（optional，可逐项关闭）",
    )
    enable_redact_url_credentials: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_URL_CREDENTIALS", True),
        description="URL 凭据脱敏（optional，可逐项关闭）",
    )
    enable_redact_dsn_passwords: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_DSN_PASSWORDS", True),
        description="DSN 密码脱敏（optional，可逐项关闭）",
    )
    enable_redact_cookies: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_COOKIES", True),
        description="Cookie 脱敏（optional，可逐项关闭）",
    )
    # ---- 裸熵兜底（heuristic 层，可按 sink 关闭）----
    enable_redact_bare_entropy: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENAVLE_REDACT_BARE_ENTROPY", True),
        description="裸高熵兜底检测（全 purpose 默认开启，可按 sink 关闭；非 mandatory）",
    )
    redact_secrets_min_length: int = Field(
        default=int(os.getenv("BKAI_REDACT_SECRETS_MIN_LENGTH", "32")),
        description="裸熵候选最小长度（默认 32）",
    )
    redact_secrets_entropy_threshold: float = Field(
        default=float(os.getenv("BKAI_REDACT_SECRETS_ENTROPY_THRESHOLD", "4.2")),
        description="裸熵 alnum/Base64URL 阈值（默认 4.2；标准 Base64 固定 4.5）",
    )
    # ---- partial 掩码阈值（默认与 masking.py 历史硬编码常量一致：32 / 6 / 4）----
    redact_partial_min_len: int = Field(
        default=int(os.getenv("BKAI_REDACT_PARTIAL_MIN_LEN", "32")),
        description="partial 掩码保留首尾的最小长度（>= 该值保留首尾，< 该值整体替换；默认 32）",
    )
    redact_partial_head: int = Field(
        default=int(os.getenv("BKAI_REDACT_PARTIAL_HEAD", "6")),
        description="partial 掩码保留的首部字符数（默认 6，常含厂商前缀）",
    )
    redact_partial_tail: int = Field(
        default=int(os.getenv("BKAI_REDACT_PARTIAL_TAIL", "4")),
        description="partial 掩码保留的尾部字符数（默认 4）",
    )

    # ---- 字符串 / 列表配置（逗号分隔原文）----
    known_sensitive_values: str = Field(
        default_factory=lambda: os.getenv("BKAI_KNOWN_SENSITIVE_VALUES", ""),
        description="已知敏感值（逗号分隔原文）—— 经 detector 管线（RegisteredSecretDetector）"
        "在工具结果进入模型上下文前做精确匹配脱敏。runtime 工具出口会把 SBX_SENSITIVE_VALUES "
        "与 backend 额外值合并进本字段（见 provider._merge_known_values）",
    )

    # 已删除 ``_force_mandatory_redaction``（``mode="before"`` 校验器 + ``_MANDATORY_REDACT_FIELDS``）：
    # 它把 registered / authorization_headers / private_keys 的平台下发 False 静默归 True（D-06）。
    # 删除依据：该层使总开关 ``enable_redact_secrets=False`` **无法真正断开全部能力** ——
    # mandatory 三项仍照跑，与「所有功能都需要有开关，总开关闭合时必须全部可关」冲突。
    # 现全字段平等：平台下发 False 即真关闭；要彻底关闭脱敏用总开关（引擎硬熔断）。


class RuleSpecConfig(BaseModel):
    """平台下发的单条规则（与 Codex 一致下发 ``RuleSpec`` 形态，Phase 11 D-10）。

    **统一声明模型：一条声明 = 一条完整规则，或一次按 id 关闭。**

    平台只做一个动作——下发一条 ``RuleSpec`` 形态的规则声明；由 ``enabled`` 单一开关
    决定它的含义（**没有第二套语义，也没有 ``custom:`` 前缀这种隐式区分**）：

    - ``enabled=True``（默认）：声明**一条完整规则**。``rule_id`` 命中内置 → 替换该内置
      （内容 + 判定一并替换）；``rule_id`` 未登记 → 新增一条规则。两条路径**语义完全一致**，
      平台无需知道某 id 是不是内置的。
    - ``enabled=False``：**按 id 关闭**该规则（仅需给 ``rule_id``）。这使**带代码谓词的
      内置规则**（如 ``mkfs_format`` / ``syntax:background``）也能被平台关掉——它们的内容
      不可下发，但可关闭。

    下发通道的准入判据由**整条声明**的 :class:`Pattern` 形状决定（``tokens`` + 五个修饰符字段），
    而非 ``tokens`` 一项：不可字面化的规则（正则 / 参数内匹配 / 跨命令关系）无法用声明式数据
    表达，故不得下发；非字面化者在加载期 ``RuleConfigError``（fail-closed）。``enabled=True``
    的声明**必须有可字面化内容**（空 tokens / 无修饰符一律拒绝），该判据对「改内置」与
    「新增」**同一套**——这正是本模型要消除的双重含义。
    判据实现只有一处（命令包的形状层 :meth:`Pattern.from_mapping`），本层只做**类型**与
    **字段名**的把关——在 pydantic 层另写一套「修饰符组合是否合法」的校验就是 C-02 的同型错误，
    那是 :meth:`Pattern.__post_init__` 的职责。

    ⭐ **对 Codex 的有意偏离：``verdict`` 在 ``enabled=True`` 时必填。**
    Codex 的 ``decision`` **默认为 ``allow``**；本仓库**必须不采用该默认**——空规则 entry
    不得判 allow（``command_security._evaluate_rules`` 在零规则命中时回落 ``review``，
    正是该语义的载体），若照搬「默认 allow」，
    未知命令会从 ``review`` 翻成 ``allow``，等于**静默取消全部未知命令的人工审批**（fail-open）。
    ``enabled=False``（纯关闭）不产出任何命中，故不要求 ``verdict`` / ``justification``。

    ``extra="forbid"``：本模型是我们完全拥有的形状，且是实际攻击面。平台把
    ``{"descision": "forbidden"}`` 拼错时，静默忽略会让运营者以为规则已生效而它没有，
    故此处必须报错（父模型的 ``extra="ignore"`` 保留，用于向前容错）。
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(
        min_length=1,
        max_length=64,
        description="规则 id：命中内置 id 即替换该内置规则；未登记 id 即新增一条规则"
        "（**无需任何前缀**——内置 id 与新增 id 用同一命名空间，不需要 `custom:` 之类约定）",
    )
    enabled: bool = Field(
        default=True,
        description="单一开关。true（默认）= 声明一条完整规则（替换同 id 内置，或新增）；"
        "false = **仅按 id 关闭**该规则（此时只需 rule_id，verdict/justification/内容均可省略）。"
        "「关闭」与「降为 allow」是两件事：后者仍产出 allow 命中，只是不阻断",
    )
    verdict: Literal["allow", "review", "block"] | None = Field(
        default=None,
        description="命中时的判定。``enabled=True`` 时**必填**（无默认，避免误用 allow）；"
        "``enabled=False``（纯关闭）不产出命中，故可省略。"
        "取值与报告契约的 CommandVerdict 一致——**此处刻意内联字面量而非 import 它**："
        "``CommandVerdict`` 住在 ``packages/security/command``（依赖叶子），而依赖方向是"
        "``packages/security`` → ``pydantic_models``，反向 import 会破坏分层。"
        "两处字面量形状相同，由 parity 测试钉住（见 test_security_settings 的 rule 配置用例）",
    )
    justification: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="命中时呈现给审批人 / 模型的原因文案（合一原 reason 与 description）。"
        "``enabled=True`` 时**必填**；``enabled=False``（纯关闭）可省略",
    )
    tokens: list[str | list[str]] = Field(
        default_factory=list,
        description="可字面化的内容 token（有序；列表元素表示任一可选）。"
        "**单一含义**：空列表 = 无声明式内容。``enabled=True`` 的声明**必须有可字面化内容**"
        "（空 tokens 且无修饰符一律拒收，加载期报错）——该判据对「替换内置」与「新增」"
        "同一套，不存在「空 = 只调开关」的第二种含义",
    )
    positional_index: int | None = Field(
        default=None,
        ge=0,
        le=64,
        description="位置 token 匹配：取「跳过选项后的第 N 个非选项 token」与该位置的值比较。"
        "None 表示不启用位置匹配。**无正则**——匹配是 token 级线性比较（本仓库有 ReDoS 前科）。"
        "与 tokens 同属下发维度：只有可字面化的组合才允许下发",
    )
    positional_equals: list[str] = Field(
        default_factory=list,
        description="位置 token 的允许取值集合（如 chmod 的 ['777'] / chown 的 ['root']）。"
        "仅当 positional_index 非 None 时有意义；positional_index 缺省却给出本字段"
        "会在命令包的形状层构造期报错（fail-loud，不静默忽略）",
    )
    skip_flags: list[str] = Field(
        default_factory=list,
        description="位置定位时**额外**跳过的 token 集合（如 apt 的 ['-y','--yes']）。"
        "必须精确列举：未列举的前缀 flag 不跳过，否则 `apt -o X install vim` 会误命中。"
        "**类型是字符串数组（不是布尔）**——曾有一处把 True 传进本语义的缺陷（C-01），"
        "故此处与命令包的 frozenset[str] 一次性对齐",
    )
    strip_colon: bool = Field(
        default=False,
        description="位置 token 比较前剥掉 ':group'（chown root:grp -> root）。仅当 positional_index 非 None 时有意义",
    )
    requires_any_flag: bool = Field(
        default=False,
        description="要求参数中存在**任一** '-' 开头的 token（不指定具体 flag）。"
        "这是「命令 + flag」的放宽变体（如 iptables 的任何变更动作）",
    )
    category: str = Field(
        default="custom",
        pattern=r"^[a-z_]{1,32}$",
        description="分类标签，用于结果明细与聚合展示",
    )

    @model_validator(mode="after")
    def _require_verdict_and_justification_when_enabled(self) -> "RuleSpecConfig":
        """``enabled=True`` 时必须给出 ``verdict`` 与 ``justification``（纯存在性判定）。

        ``enabled=False`` 是「按 id 关闭」——不产出任何命中，故二者可省略（关闭一条规则
        不该被迫编造一条判定与文案）。

        **只判「在不在」，不判「形状合不合法」**：内容能否字面化（``tokens`` + 五个修饰符）
        的判据只有一处（命令包的形状层 ``Pattern.from_mapping``），本层另写一套就是 C-02
        的同型错误。该形状校验由 ``build_rule_set`` 在加载期执行。
        """
        if self.enabled and self.verdict is None:
            raise ValueError(f"规则 {self.rule_id!r} 声明为启用（enabled=true），必须给出 verdict")
        if self.enabled and self.justification is None:
            raise ValueError(f"规则 {self.rule_id!r} 声明为启用（enabled=true），必须给出 justification")
        return self


class SecurityCommandSettings(BaseModel):
    """命令防护专用配置（独立于脱敏 / 沙箱 / 网络等安全开关）。

    原为 ``SecuritySettings`` 顶层的 4 个命令字段（``enable_command_blocklist`` /
    ``enable_command_approval`` / ``command_approval_mode`` / ``command_approval_approvers``）。
    提取为独立模型后，命令防护能力（``packages.security.command``）只依赖本模型，
    不再耦合总配置；总配置经 ``SecuritySettings.command`` 嵌套持有。

    取值来源分两级（与迁移前一致）：

    1. 字段默认工厂从环境变量读取（本地开发 / 兜底）；
    2. 平台侧在 ``agent_info["security_settings"]["command"]`` 下发同名字段时，
       由 ``SecuritySettings`` 直接构造（嵌套 dict 由 pydantic 投影）以平台值覆盖环境变量。

    **平台下发始终优先于环境变量**：平台显式给出的键直接成为构造入参，环境变量
    只在该键**缺失**时经默认工厂生效。
    故引入环境变量不会使平台下发失效——这一点对 ``rules`` 尤其重要：
    ``rules`` 是策略下发的单一字段，环境变量只是它的**初始化值**。

    本模型**不提供**自定义构造入口 —— 平台下发入口唯一保留在总配置
    ``SecuritySettings``（故旧扁平命令键不再生效，被 extra-ignore 忽略）。

    设计意图：
    - 评估时逐项关闭（观察单条命令防护能力对行为的影响）；
    - 出问题（误拦截 / 误放行）时通过平台下发关闭（应急熔断）。

    **字段（14 个）的取值来源**：

    - ``enable_command_blocklist`` / ``enable_command_blocklist_dynamic_exec`` /
      ``enable_command_blocklist_unsupported`` / ``enable_command_syntax_rules`` /
      ``enable_command_review_auto`` /
      ``command_review_disposition`` / ``command_approval_approvers`` —— 环境变量兜底：
      ``BKAI_ENABLE_COMMAND_BLOCKLIST`` / ``BKAI_ENABLE_COMMAND_BLOCKLIST_DYNAMIC_EXEC`` /
      ``BKAI_ENABLE_COMMAND_BLOCKLIST_UNSUPPORTED`` / ``BKAI_ENABLE_COMMAND_SYNTAX_RULES`` /
      ``BKAI_ENABLE_COMMAND_REVIEW_AUTO`` /
      ``BKAI_COMMAND_REVIEW_DISPOSITION`` / ``BKAI_COMMAND_APPROVAL_APPROVERS``；
    - ``rules`` —— 环境变量兜底 ``BKAI_SECURITY_COMMAND_RULES``（JSON 数组字符串）；
    - ``allowed_script_dirs`` / ``dynamic_execution_policy`` / 四项预算
      （``max_command_length`` / ``max_nodes`` / ``max_depth`` / ``max_reparse_depth``）
      —— 读**代码内默认值**，只能由平台经 ``security_settings.command`` 下发覆盖。
    四项预算为 ``StrictInt``（不接受 ``bool`` / 浮点 / 字符串数字的隐式转换）且限定合法范围，
    默认值只在模型字段处定义一处（消费方从字段默认派生，不重复硬编码）。

    **放行平台白名单命令不再有专用参数**（2026-09-24，C-03 / 用户硬目标）：
    原先的请求级旁路参数（本模型的「额外放行命令」列表字段）**已删除**。
    平台要放行某条未知命令，改为经 ``rules`` 下发一条 allow 规则，
    例如 ``RuleSpecConfig(rule_id="mycmd", verdict="allow", justification="...",
    tokens=["mycmd"])``。**语义不变**：``rules`` 仍随 ``SecurityCommandSettings`` 每请求读取，
    ``RuleSet`` 每请求构造（Phase 11 D-12），故平台改配置立即生效。
    ⚠ **breaking change**：该平台键已删除，经 ``extra="ignore"`` 静默失效。
    **迁移窗口待确认**——不得自行假定外部平台已迁移
    （与 Phase 9 的 ``command_blacklist`` → ``enable_command_blocklist`` 等三处同型）。

    规则下发（统一声明模型，**取代原 ``rule_overrides`` + ``custom_rules`` 双字段**）：

    - ``rules``：平台下发的规则声明列表，统一 ``RuleSpecConfig`` 形态。由 ``enabled``
      单一开关决定语义：``enabled=True`` 声明**一条完整规则**（命中内置 id 即替换该内置，
      未登记 id 即新增——两条路径语义一致，**无 ``custom:`` 前缀要求**）；
      ``enabled=False`` **按 id 关闭**该规则（仅需 ``rule_id``）。
      后者使**带代码谓词的内置规则**（内容不可下发）也能被平台关掉。
      与 Codex 一致地「下发 ``RuleSpec`` 形态」；**不支持正则**（``tokens`` 是 token 匹配，
      正则等于把远程 DoS 原语交给配置控制方，本仓库有 ReDoS 前科）。

    它让平台可逐条替换可字面化规则（含 block→allow 降级），或按 id 关闭任一条规则。
    **不可关闭 / 不可替换**的是**全部分析失败标识**（``parse:*`` / ``budget:*`` / ``input:*`` /
    ``empty:*`` / ``analysis:*`` / ``rule:internal_error`` / ``ast:unknown_node``）
    ——注意分析失败**不在规则命名空间内**（它们不是规则，不占 rule_id，也不参与本字段）。
    另：``enabled=True`` 的声明**不得**用声明式内容遮蔽一条代码谓词内置规则（会静默解除
    它的代码判定）——要关它请用 ``enabled=False``，要改判据请新增一条不同 rule_id 的规则。

    注（2026-09-24）：``review`` 不是规则（它是「未命中任何规则」的处置，由控制流产出），
    故它既不在 RULE_SPECS 里、也无所谓可配性——原 ``whitelist:review`` 已删除。

    ``review`` 的处置由两个正交字段描述（取代原 ``enable_command_approval`` +
    ``command_approval_mode`` 的耦合写法）：

    - ``enable_command_review_auto``：处置档为 ``approval`` 时，是否先用智能风险评估器预分流以
      减少人工审批量。为真且注入评估器时，评估器返回与处置档同一套词汇——``allow`` 省掉审批直接
      放行 / ``block`` 直接拒绝（**覆盖**处置档），``approval`` 落回审批。处置档为 ``allow`` /
      ``block`` 时不跑评估器（已能自动决定，跑是纯开销）。
    - ``command_review_disposition``：处置档，三选一 ``allow`` / ``approval`` / ``block``。
      ``allow`` / ``block`` 不需要审批人；``approval`` 消费 ``command_approval_approvers``
      （无审批人时 fail-closed 拒绝）。默认 ``block``——等价旧「审批未启用」的 fail-closed 行为。
    """

    model_config = ConfigDict(extra="ignore")

    enable_command_blocklist: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_COMMAND_BLOCKLIST", True),
        description="危险命令黑名单（env 兜底名 BKAI_ENABLE_COMMAND_BLOCKLIST；平台下发键同字段名）",
    )
    enable_command_blocklist_dynamic_exec: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_COMMAND_BLOCKLIST_DYNAMIC_EXEC", False),
        description="动态执行内容规则 ``dynamic:execution_content`` 的开关"
        "（env 兜底名 BKAI_ENABLE_COMMAND_BLOCKLIST_DYNAMIC_EXEC；平台下发键同字段名）。"
        "为假时该规则整条不参与判定（含其谓词），命中面为解释器内联代码 / 未建模执行包装器 / "
        "动态命令名。**独立于** ``enable_command_blocklist``：后者只管「已知危险」族"
        "（category 落在 BLOCKLIST_CATEGORIES 内），本条规则的 category 是 ``dynamic``，不在该族内",
    )
    enable_command_blocklist_unsupported: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_COMMAND_BLOCKLIST_UNSUPPORTED", True),
        description="解析边界规则 ``invocation:unsupported`` 的开关"
        "（env 兜底名 BKAI_ENABLE_COMMAND_BLOCKLIST_UNSUPPORTED；平台下发键同字段名）。"
        "为假时该规则整条不参与判定，命中面为「已解析但执行语义未建模」的 shell 调用形态。"
        "**关闭属 fail-open**：这些形态的实际执行语义未能确定，关掉即放行到沙箱",
    )
    enable_command_syntax_rules: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_COMMAND_SYNTAX_RULES", False),
        description="结构约束族（9 条 ``syntax:*`` + 1 条 ``ast:*``）的开关"
        "（env 兜底名 BKAI_ENABLE_COMMAND_SYNTAX_RULES；平台下发键同字段名）。"
        "为假时这 10 条整族不参与判定（含其谓词），命中面为后台执行符 / ``|&`` / "
        "无条件禁用命令名 / 重定向 / heredoc / herestring / 大括号扩展 / 命令名路径 / "
        "脚本目录政策 / 参数内未建模执行结构。"
        "**独立于** ``enable_command_blocklist``：后者只管「已知危险」族"
        "（category 落在 BLOCKLIST_CATEGORIES 内），本族 category 是 ``syntax`` / ``ast``",
    )
    enable_command_review_auto: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_COMMAND_REVIEW_AUTO", False),
        description="处置档为 approval 时，是否先用智能风险评估器预分流以减少人工审批量"
        "（env 兜底名 BKAI_ENABLE_COMMAND_REVIEW_AUTO；平台下发键同字段名）。"
        "为真且注入了评估器时：评估器返回 allow 省掉审批直接放行 / reject 直接拒绝"
        "（二者**覆盖**处置档），approval 落回审批；处置档为 allow / block 时不跑评估器",
    )
    command_review_disposition: Literal["allow", "approval", "block"] = Field(
        default_factory=lambda: os.getenv("BKAI_COMMAND_REVIEW_DISPOSITION", "allow"),
        description="命令落入 review（未命中任何规则）时的处置"
        "（env 兜底名 BKAI_COMMAND_REVIEW_DISPOSITION；平台下发键同字段名）："
        "allow=自动放行（尽量不影响业务）/ approval=走 ITSMT 审批 / block=直接拒绝（高敏感任务）",
    )
    command_approval_approvers: str = Field(
        default_factory=lambda: os.getenv("BKAI_COMMAND_APPROVAL_APPROVERS", ""),
        description="命令级审批人（逗号分隔；env 兜底名 BKAI_COMMAND_APPROVAL_APPROVERS；"
        "平台下发键同字段名）。**仅当 command_review_disposition=approval 时被消费**",
    )
    allowed_script_dirs: list[str] = Field(
        default_factory=lambda: ["/workspace", "/home", "/tmp", "/app"],
        description="允许执行脚本的目录列表；不读环境变量，只能由平台经 "
        "security_settings.command.allowed_script_dirs 下发（数组形式）",
    )
    dynamic_execution_policy: Literal["block", "review"] = Field(
        default="block",
        description='动态执行内容（如 $CMD 作为命令名、bash -c "$SCRIPT" 等无法静态确定实际执行内容）'
        "的策略：仅 block / review，无 allow 档位。不读环境变量，只能由平台经 "
        "security_settings.command.dynamic_execution_policy 下发",
    )
    max_command_length: StrictInt = Field(
        default=8192,
        ge=1,
        le=65536,
        description="命令长度预算（字符）：全请求 root 与每段解码脚本文本的累计字符数上限；"
        "严格整数（拒 bool / 浮点 / 字符串数字），不读环境变量，只能由平台经 "
        "security_settings.command.max_command_length 下发",
    )
    max_nodes: StrictInt = Field(
        default=20000,
        ge=1,
        le=1000000,
        description="AST 节点预算：规范子边可达的真实 AST 节点累计数上限；"
        "严格整数（拒 bool / 浮点 / 字符串数字），不读环境变量，只能由平台经 "
        "security_settings.command.max_nodes 下发",
    )
    max_depth: StrictInt = Field(
        default=64,
        ge=1,
        le=4096,
        description="结构深度预算：每个 source 的 AST 根为 1、子边 +1 的递归深度上限；"
        "严格整数（拒 bool / 浮点 / 字符串数字），不读环境变量，只能由平台经 "
        "security_settings.command.max_depth 下发",
    )
    max_reparse_depth: StrictInt = Field(
        default=8,
        ge=1,
        le=64,
        description="脚本文本再解析深度预算：root 为 0、child=parent+1 的嵌套再解析层数上限；"
        "严格整数（拒 bool / 浮点 / 字符串数字），不读环境变量，只能由平台经 "
        "security_settings.command.max_reparse_depth 下发",
    )
    rules: list[RuleSpecConfig] = Field(
        default_factory=lambda: [
            RuleSpecConfig.model_validate(item) for item in (settings.BKAI_SECURITY_COMMAND_RULES or [])
        ],
        description="规则声明（统一形态，取代原 rule_overrides + custom_rules 双字段）。"
        "enabled=true 声明一条完整规则（命中内置 id 即替换，未登记 id 即新增，无前缀要求）；"
        "enabled=false 按 rule_id 关闭该规则。"
        "**取值优先级：平台下发 > 环境变量 > 默认（空列表）**——环境变量"
        "``BKAI_SECURITY_COMMAND_RULES``（JSON 数组字符串）仅作**初始化值**，"
        "平台经 ``security_settings.command.rules`` 下发同名键时整表覆盖之，"
        "故环境变量不会使平台下发失效。"
        "规则集合的语义校验（是否可字面化 / 是否可关闭 / 是否遮蔽代码谓词）由命令包在加载期执行"
        "（依赖方向：packages.security → pydantic_models，故本层不做）。"
        "⚠ 外部平台须同步迁移到本字段；旧键 rule_overrides / custom_rules 经 extra='ignore' "
        "静默失效，迁移窗口**待确认**（不得自行假定外部已迁移）；"
        "原「额外放行命令」列表键同样已删除（放行未知命令改经本字段下发 allow 规则），"
        "迁移窗口同样待确认",
    )

    @model_validator(mode="after")
    def _validate_rule_config(self) -> "SecurityCommandSettings":
        """校验 ``rules`` 的形状级约束。

        **只做拒绝，从不改写平台值**——刻意不用 ``mode="before"``，也不把缺省值
        补成更严的值。本仓库有过教训：``_force_mandatory_redaction`` 曾用 before
        validator 把平台 ``False`` 强翻 ``True``，反而废掉了主开关，后被删除。

        本方法只校验**本层可判定**的约束：``rules`` 内部 rule_id 不得重复 ——
        否则哪条规则生效未定义。

        **不在此处校验是否可字面化 / 是否可关闭 / 是否遮蔽代码谓词**：那需要命令包的
        基础定义模块（``packages.security.command.command_definitions``），而依赖方向是
        ``packages/security`` → ``pydantic_models``，反向导入会破坏分层
        （本模块现仅依赖 ``aidev_agent.enums``）。该语义校验由命令层在
        ``build_rule_set`` 入口执行，同样是构造期 fail-closed。

        **``extra="forbid"`` 只作用于 ``RuleSpecConfig`` 自身**，平台把字段名拼错
        （如 ``descision``）会报错；而 ``SecurityCommandSettings`` 保留
        ``extra="ignore"`` 以向前容错（旧键 ``rule_overrides`` / ``custom_rules``
        静默失效——这是有意的契约变更）。
        """
        rule_ids = [rule.rule_id for rule in self.rules]
        duplicated = sorted({rid for rid in rule_ids if rule_ids.count(rid) > 1})
        if duplicated:
            raise ValueError(f"rules 含重复的 rule_id：{duplicated}")

        return self


class SecuritySettings(BaseModel):
    """安全防护配置（所有安全功能的开关与配置项统一收口）。

    字段名即平台下发 ``security_settings`` 的键名。取值来源分两级：

    1. 字段默认工厂从环境变量读取（本地开发 / 兜底）；
    2. 平台侧在 ``agent_info["security_settings"]`` 下发同名字段时，由
       ``SecuritySettings`` 直接构造（嵌套 dict 由 pydantic 投影）以平台值覆盖
       环境变量，实现 per-agent / per-user 差异化配置。

    该实例在构建期统一解析**一次**：``BaseResourceManager.get_agent_config`` 从
    ``agent_info["security_settings"]`` 构造，填入
    ``AgentConfig.security_settings``；随后沿构建链拆入 ``ToolNodeSettings`` /
    ``ModelNodeSettings`` / 运行时 provider 等消费点。``agent_config`` 是运行时
    唯一的配置入口 —— 叶节点不再各自读取环境变量。

    脱敏配置（原 17 个脱敏字段）自本版本起由 ``redaction`` 嵌套持有
    （:class:`SecurityRedactionSettings`）；平台下发形态为
    ``{"redaction": {...}, ...}``，旧扁平脱敏键不再生效（extra-ignore 静默忽略）。

    命令防护配置（原 4 个命令字段）自本版本起由 ``command`` 嵌套持有
    （:class:`SecurityCommandSettings`）；平台下发形态为
    ``{"command": {...}, ...}``，旧扁平命令键不再生效（extra-ignore 静默忽略）。

    设计意图：
    - 评估时逐项关闭（观察单个安全功能对行为 / 性能的影响）；
    - 出问题（误拦截 / 误放行）时通过平台下发关闭（应急熔断）。
    """

    model_config = ConfigDict(extra="ignore")

    # ---- 脱敏配置（嵌套小模型；脱敏引擎只依赖它，不依赖本总模型）----
    redaction: SecurityRedactionSettings = Field(
        default_factory=SecurityRedactionSettings,
        description="脱敏专用配置（SecurityRedactionSettings）；平台下发形态为嵌套 dict，"
        "由 pydantic 自动解析。脱敏引擎与工具结果 guard 只消费本子配置",
    )

    # ---- 命令防护配置（嵌套小模型；命令包只依赖它，不依赖本总模型）----
    command: SecurityCommandSettings = Field(
        default_factory=SecurityCommandSettings,
        description="命令防护专用配置（SecurityCommandSettings）；平台下发形态为嵌套 dict，"
        "由 pydantic 自动解析。命令防护能力只消费本子配置",
    )

    # ---- 布尔开关（默认开启；命令审批默认关闭，fail-closed）----
    enable_tool_result_limit: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_TOOL_RESULT_LIMIT", True),
        description="工具结果超长限制（超阈值整段替换为拒绝提示）",
    )
    enable_tool_redaction: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_TOOL_REDACTION", True),
        description="工具结果脱敏",
    )
    enable_tool_untrusted_sanitize: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_TOOL_UNTRUSTED_SANITIZE", False),
        description="不可信工具结果净化（原型污染清理 + 注入扫描 + 包裹）",
    )
    enable_model_security_guidance: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_MODEL_SECURITY_GUIDANCE", True),
        description="模型引导层",
    )
    enable_prompt_injection_guard: bool = Field(
        default_factory=lambda: _env_bool("BKAI_ENABLE_PROMPT_INJECTION_GUARD", True),
        description="提示词注入净化",
    )

    # ---- 沙箱策略 ----
    sandbox_policy: SandboxPolicy | None = Field(
        default=None,
        description="平台无关沙箱策略（SandboxPolicy）；平台下发 dict 时自动解析，"
        "运行时据此启用内核级文件隔离。None 表示不启用",
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
    vision_llm: Optional[Any] = Field(
        default=None,
        description="视觉模型（BaseChatModel），用于 read_image 工具识别图片；未设置时不注册该工具",
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

    # 安全防护配置（构建期统一解析一次，含平台下发覆盖；ReActAgentBuilder 据此拆入 ToolNodeSettings / ModelNodeSettings）
    security_settings: Optional[SecuritySettings] = Field(
        default=None,
        description="安全防护配置实例；由 ChatCompletionAgent 从 AgentConfig.security_settings 传入。",
    )


class AgentConfig(BaseModel):
    """智能体配置"""

    agent_code: str = Field(..., description="智能体代码")
    agent_name: str = Field(..., description="智能体名称")
    chat_model: str = Field(..., description="LLM模型名称")
    fallback_model: str | None = Field(default=None, description="主模型请求失败时使用的备用模型")
    non_thinking_llm: str = Field(..., description="非深度思考模型")
    fast_llm: str | None = Field(default=None, description="快速模型")
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
    max_spawn_depth: int = Field(default=1, description="最大 Agent 嵌套深度")
    # 原始配置信息（来自 retrieve_agent_config 的完整字典，含 otel_info 等平台透传字段）
    agent_info: dict | None = Field(None, description="智能体配置信息，agent_info 接口的原始值，仅仅用于数据上报")
    # 安全防护配置（构建期统一解析一次，含平台下发覆盖；由 base.py 在 get_agent_config 时填充）
    security_settings: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="安全防护配置（平台下发覆盖环境变量，统一读取后拆入各节点）",
    )
