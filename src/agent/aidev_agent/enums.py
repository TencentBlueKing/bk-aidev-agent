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


class StreamEventType(enum.Enum):
    NO = ""  # 不会展示这个
    TEXT = "text"
    THINK = "think"
    REFERENCE_DOC = "reference_doc"
    ERROR = "error"
    DONE = "done"


class ChatContentStatus(enum.Enum):
    LOADING = "loading"
    FAIL = "fail"
    SUCCESS = "success"
