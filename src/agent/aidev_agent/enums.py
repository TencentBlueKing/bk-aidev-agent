import enum


class PromptRole(enum.Enum):
    """chat prompt 包含的角色"""

    ROLE = "role"  # 前端传入用于指定当前预设角色的提示词,需要转为system
    SYSTEM = "system"  # 前端传入的system需要被过滤
    TIME = "time"
    USER = "user"
    ASSISTANT = "assistant"
    AI = "ai"
    GUIDE = "guide"
    HIDDEN = "hidden"
    PAUSE = "pause"  # 暂停演绎,等待用户输入
    USER_IMAGE = "user-image"  # 用户带图片的输入
    TOOL = "tool"  # 工具调用结果
    REASONING = "reasoning"  # 演绎过程
    ACTIVITY = "activity"  # 活动,用于指定自定义消息的类
    INTERRUPT = "interrupt"  # 中断,用于工具审批等交互场景
    INFO = "info"  # 系统信息,用于上下文压缩通知等系统级提示

    @classmethod
    def skip_roles(cls) -> list[str]:
        return [cls.REASONING.value]


class ChatContentStatus(enum.Enum):
    LOADING = "loading"
    ERROR = "error"
    SUCCESS = "success"
    COMPLETE = "complete"
    PENDING = "pending"  # 前端根据最后一条content状态为pending判断发起轮询


class IntentStatus(enum.Enum):
    QA_WITH_RETRIEVED_KNOWLEDGE_RESOURCES = "QA_WITH_RETRIEVED_KNOWLEDGE_RESOURCES"
    AGENT_FINISH_WITH_RESPONSE = "AGENT_FINISH_WITH_RESPONSE"
    DIRECTLY_RESPOND_BY_AGENT = "DIRECTLY_RESPOND_BY_AGENT"
    PROCESS_BY_AGENT = "PROCESS_BY_AGENT"


class Decision(enum.Enum):
    GENERAL_QA = "GENERAL_QA"
    PRIVATE_QA = "PRIVATE_QA"
    QUERY_CLARIFICATION = "QUERY_CLARIFICATION"


class FineGrainedScoreType(enum.Enum):
    LLM = "LLM"
    EXCLUSIVE_SIMILARITY_MODEL = "EXCLUSIVE_SIMILARITY_MODEL"
    EMBEDDING = "EMBEDDING"


class IndependentQueryMode(enum.Enum):
    INIT = "INIT"  # 直接使用原始的，不进行重写
    REWRITE = "REWRITE"  # 根据 chat history 对 query 进行重写
    SUM_AND_CONCATE = "SUM_AND_CONCATE"  # 对 chat history 进行总结，并跟 query 进行拼接


class KnowledgeBaseQueryFunction(enum.Enum):
    """检索方式"""

    SEMANTIC = "semantic"  # 语义检索
    MIXED = "mixed"  # 混合检索
    SQL = "sql"  # SQL检索


class IntentCategory(enum.Enum):
    KNOWLEDGE_BASE = "knowledge base"
    KNOWLEDGE_ITEM = "knowledge item"
    TOOL = "tool"


class StreamEventType(enum.Enum):
    NO = ""  # 不会展示这个
    LOADING = "loading"
    TEXT = "text"
    DONE = "done"
    ERROR = "error"
    REFERENCE_DOC = "reference_doc"
    THINK = "think"


class CredentialType(enum.Enum):
    NULL = "null"
    BLUEAPPS = "blueapps"  # apigw
    CUSTOM = "custom"  # proxy


class ContextType(enum.Enum):
    PRIVATE = "private"
    QA_RESPONSE = "qa_response"
    BOTH = "both"


class AgentBuildType(enum.Enum):
    """Agent构建类型"""

    SESSION = "session"
    DIRECT = "direct"


class AgentType(enum.Enum):
    """Agent类型"""

    CHAT = "chat"
    TASK = "task"
    FLOW = "flow"


class ChannelType(str, enum.Enum):
    """调用渠道类型"""

    # openapi 调用渠道
    API = "api"
    # 小鲸渠道（chatbox主页和小鲸组件弹窗）
    POPUP = "popup"
    # 蓝鲸插件调用渠道
    BKPLUGIN = "bkplugin"
    # 企微机器人渠道（aidev_wxbot）
    RTX = "rtx"


class SessionsStatus(enum.Enum):
    """会话状态（断点续传）"""

    PENDING = "pending"  # 等待中
    RUNNING = "running"  # 运行中
    FINISHED = "finished"  # 已完成
    FAILED = "failed"  # 已失败
    CANCELLED = "cancelled"  # 已取消（用户主动停止）


class ActivityType(enum.Enum):
    """Activity 消息的 builtin_property 类型标识"""

    REFERENCE_DOCUMENT = "reference_document"
    FLOW_AGENT = "flow_agent"
    ARTIFACTS_GENERATED = "artifacts_generated"


class MessageHandlerType(str, enum.Enum):
    """消息处理器类型"""

    INMEMORY = "inmemory"  # 内存队列，适用于单进程模式
    RABBITMQ = "rabbitmq"  # RabbitMQ 队列，适用于多进程模式，支持断点续传
    REDIS = "redis"  # Redis Streams，适用于多进程模式，支持游标回放
    AUTO = "auto"  # 自动检测运行环境选择
