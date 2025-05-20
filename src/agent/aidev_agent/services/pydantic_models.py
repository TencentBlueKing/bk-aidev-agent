from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


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


class AgentOptions(BaseModel):
    # agent 执行选项
    intent_recognition_options: dict = Field(default_factory=dict, description="意图识别选项")
    knowledge_query_options: dict = Field(default_factory=dict, description="知识库查询选项")
