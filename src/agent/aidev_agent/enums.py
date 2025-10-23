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


class ChatContentStatus(enum.Enum):
    LOADING = "loading"
    FAIL = "fail"
    SUCCESS = "success"


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
