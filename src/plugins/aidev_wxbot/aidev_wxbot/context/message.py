import enum
from itertools import chain
from typing import Union

from pydantic import BaseModel, ConfigDict, Field


class MsgType(enum.Enum):
    Api = "api"
    Event = "event"
    EnterChat = "enter_chat"
    Click = "click"
    Text = "text"
    Markdown = "markdown"
    Image = "image"
    Voice = "voice"
    Emotion = "emotion"
    Video = "video"
    File = "file"
    Quote = "quote"
    ChatRecord = "chat_record"
    RichText = "rich_text"
    Mentioned = "mentioned"
    Url = "url"
    WxBotSurface = "wxbot_surface"
    WxBotLayout = "wxbot_layout"
    WxBotSubCLayout = "wxbot_sub_layout"
    Stream = "stream"
    StreamWithTemplateCard = "stream_with_template_card"
    UpdateTemplateCard = "update_template_card"
    Unknown = "unknown"


class MsgTargetType(enum.Enum):
    Group = "group"
    Single = "single"


class MsgSenderType(enum.Enum):
    Bot = "bot"
    User = "user"


class MessageTarget(BaseModel):
    """消息发送的对象"""

    target_type: str = Field(default=None, description="target type of message")
    target_id: str = Field(default=None, description="target id of message")
    visible_user: list = Field(default=None, description="visible user of message")


class SingleMessageTarget(MessageTarget):
    def __init__(self, target_id: str):
        super().__init__(target_type=MsgTargetType.Single.value, target_id=target_id)


class GroupMessageTarget(MessageTarget):
    def __init__(self, target_id: str):
        super().__init__(target_type=MsgTargetType.Group.value, target_id=target_id)


class UrlBrowser(enum.Enum):
    INNER: str = "inner"
    SYSTEM: str = "system"


class Message(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    """消息体结构，希望能在接受和发送的时候使用同个结构体"""
    msg_id: Union[str, None] = Field(default=None, description="id of message")
    msg_type: Union[str, None] = Field(default=None, description="type of message")

    # 文本数据
    text: Union[str, None] = Field(default=None, description="text data")

    # 引用数据
    quote_user: Union[str, None] = Field(default=None, description="the user quoted")
    quote_text: Union[str, None] = Field(default=None, description="the msg quoted")  # tip: 企微引用的数据都会变成text

    # 媒体数据
    file_name: Union[str, None] = Field(default=None, description="file name")  # file使用
    pic_url: Union[str, None] = Field(default=None, description="url of picture")  # emotion/image使用
    media_id: Union[str, None] = Field(default=None, description="MediaId")  # 收只收id，file/voice/image使用。
    media_data: Union[bytes, None] = Field(default=None, description="bytes of media message")  # 发送用数据

    # 事件数据
    event: Union[str, None] = Field(default=None, description="event of message")
    event_key: Union[str, None] = Field(default=None, description="event key of message")
    event_name: Union[str, None] = Field(default=None, description="event_name of message")

    # 富文本数据, 接受forward/mixed数据时使用。
    rich_texts: Union[list, None] = Field(default=None, description="for rich text msg, contains a list of message")

    # 点击事件数据
    click_key: Union[str, None] = Field(default=None, description="for click msg, contains a key of click")
    browser: Union[str, None] = Field(
        default=UrlBrowser.SYSTEM.value, description="for click msg, contains a browser type"
    )

    # 发送目标
    target: Union[MessageTarget, None] = Field(default=None, description="send to whom")
    mention_list: Union[list, None] = Field(default=None, description="for mentioned msg, contains a list of user id")

    response_url: Union[str, None] = Field(default=None, description="url to response")  # 企微机器人使用
    response_code: Union[str, None] = Field(default=None, description="code to response")  # 企微机器人使用

    layouts: Union[list, None] = Field(default=None, description="for column layout msg, contains a list of message")
    wxbot_send_body: Union[dict, None] = Field(
        default=None, description="wxbot send body"
    )  # 企微机器人使用的发送消息的结构体，直接透传
    wxbot_interaction_json: Union[dict, None] = Field(default=None, description="wxbot interaction json")
    wxbot_interaction_text: Union[str, None] = Field(default=None, description="wxbot interaction text")
    wx_markdown_attachments: Union[list, None] = Field(
        default=None, description="wxbot markdown msg attachments body"
    )  # 企微发送markdown消息的附件
    wxaibot_template_card_event: Union[dict, None] = Field(default=None, description="wxaibot template card event")
    stream_id: Union[str, None] = Field(default=None, description="stream id of message")

    def __str__(self):
        return self.text or ""


class TextMessage(Message):
    def __init__(self, text: str, **kwargs):
        super().__init__(msg_type=MsgType.Text.value, text=text, **kwargs)


class RichTextMessage(Message):
    def __init__(self, rich_texts: list, **kwargs):
        super().__init__(msg_type=MsgType.RichText.value, rich_texts=rich_texts, **kwargs)


class MarkdownMessage(Message):
    def __init__(self, markdown: str, **kwargs):
        super().__init__(msg_type=MsgType.Markdown.value, text=markdown, **kwargs)


class MentionedMessage(Message):
    def __init__(self, mention_list: list, **kwargs):
        super().__init__(msg_type=MsgType.Mentioned.value, mention_list=mention_list, **kwargs)


class ClickMessage(Message):
    def __init__(self, text: str, key: str, **kwargs):
        super().__init__(msg_type=MsgType.Click.value, text=text, click_key=key, **kwargs)


class FileMessage(Message):
    def __init__(self, media_id: str):
        super().__init__(msg_type=MsgType.File.value, media_id=media_id)


class UrlMessage(Message):
    def __init__(self, text: str, key: str, browser=UrlBrowser.SYSTEM.value, **kwargs):
        super().__init__(msg_type=MsgType.Url.value, text=text, click_key=key, browser=browser, **kwargs)


class InteractionMessage(Message):
    class SubColumnLayoutInteractionType(int, enum.Enum):
        REPORT_DATA = 2001
        URL = 2002
        DIALOG = 2003
        COMPONENT = 2005
        MODAL = 2006

    msg_type: str = Field(default=MsgType.WxBotSubCLayout.value, description="type of message")
    interaction_type: SubColumnLayoutInteractionType = SubColumnLayoutInteractionType.REPORT_DATA
    report_data: str = Field(default="", description="report_data")
    url: str = Field(default="", description="url of message")
    dialog: dict = Field(default={}, description="dialog")
    template_id: str = Field(default="", description="template id")

    @property
    def wx_json(self):
        layout = {"type": self.interaction_type.value, "data": {}}
        if self.interaction_type == self.SubColumnLayoutInteractionType.REPORT_DATA:
            layout["data"] = {"report_data": self.report_data}
        elif self.interaction_type == self.SubColumnLayoutInteractionType.URL:
            layout["data"] = {"url": self.url}
        elif self.interaction_type == self.SubColumnLayoutInteractionType.DIALOG:
            layout["data"] = {"report_data": self.report_data, "dialog": self.dialog}
        elif self.interaction_type == self.SubColumnLayoutInteractionType.COMPONENT:
            layout["data"] = {"report_data": self.report_data, "dialog": self.dialog}
        elif self.interaction_type == self.SubColumnLayoutInteractionType.MODAL:
            layout["template_id"] = self.template_id
            layout["data"] = {"report_data": self.report_data}
        return layout


class LocationType(str, enum.Enum):
    TOP = "top"
    RIGHT = "right"
    LEFT = "left"
    BUTTOM = "buttom"


class WxbotMarkdownMessage(Message):
    @property
    def wx_json_list(self):
        # 将文本按每1000字符分割成块
        chunk_size = 1000
        text_chunks = [self.text[i : i + chunk_size] for i in range(0, len(self.text), chunk_size)]

        # 为每个文本块创建markdown消息
        return [{"type": "markdown", "text": chunk, "style": "sub_text"} for chunk in text_chunks]


class WxbotPlainTextMessage(Message):
    class PlainTextStyle(str, enum.Enum):
        TITLE = "title"
        REGULAR = "regular"
        SUBTEXT = "subtext"

    msg_type: str = Field(default=MsgType.WxBotSubCLayout.value, description="type of message")
    style: PlainTextStyle = PlainTextStyle.REGULAR

    @property
    def wx_json(self):
        return {"type": "plain_text", "text": self.text, "style": self.style.value}


class TextInputMessage(Message):
    msg_type: str = Field(default=MsgType.WxBotSubCLayout.value, description="type of message")
    hint: str = Field(default="", description="hint of input")
    key: str = Field(default="", description="key of input")
    label_text: str = Field(default="", description="label_text of input")
    label_location: LocationType = LocationType.LEFT
    label_width: float = Field(default=0.3, description="label_width of input")

    @property
    def wx_json(self):
        return {
            "type": "text_input",
            "hint": self.hint,
            "key": self.key,
            "label": {"text": self.label_text, "location": self.label_location.value, "width": self.label_width},
        }


class SelectorMessage(Message):
    class Option:
        def __init__(self, select_id, text):
            self.select_id = select_id
            self.text = text

        @property
        def wx_json_list(self):
            return [{"text": self.text, "id": self.select_id}]

    msg_type: str = Field(default=MsgType.WxBotSubCLayout.value, description="type of message")
    label_text: str = Field(default="", description="label text")
    label_location: LocationType = LocationType.LEFT

    key: str = Field(description="key")
    options: list[Option] = Field(default=[], description="a list contains dict with key 'text' and 'id' ")

    @property
    def wx_json(self):
        return {
            "type": "selector",
            "label": {"text": self.label_text, "location": self.label_location.value},
            "key": self.key,
            "options": [item.wx_json for item in self.options],
        }


class ButtonMessage(Message):
    class ButtonColor(str, enum.Enum):
        GREEN = "green"
        RED = "red"
        YELLOW = "yellow"
        POSITIVE = "positive"
        WARNING = "warning"
        NEGATIVE = "negative"

    class ButtonFill(str, enum.Enum):
        DEFAULT = "default"
        FOLLOW = "follow"

    class ButtonType(str, enum.Enum):
        DEFAULT = "default"
        OUTSTAND = "outstand"
        GENERAL = "general"
        COLORFUL = "colorful"
        ICON = "icon"

    msg_type: str = Field(default=MsgType.WxBotSubCLayout.value, description="type of message")
    color: ButtonColor = ButtonColor.GREEN
    fill: ButtonFill = ButtonFill.DEFAULT
    button_type: ButtonType = ButtonType.DEFAULT
    interaction_data: Union[InteractionMessage, None] = Field(default=None, description="report_data")

    @property
    def wx_json_list(self):
        return [
            {
                "type": "button",
                "text": self.text,
                "button_style": {"type": self.button_type.value, "color": self.color.value, "fill": self.fill.value},
                "interaction": self.interaction_data.wx_json,
            }
        ]


class LayoutMessage(Message):
    class LayoutType(str, enum.Enum):
        COLUMN_LAYOUT = "column_layout"
        ROW_LAYOUT = "row_layout"
        FLEX_LAYOUT = "flex_layout"

    msg_type: str = Field(default=MsgType.WxBotLayout.value, description="type of message")
    layout_type: LayoutType = LayoutType.COLUMN_LAYOUT
    layouts: list[Union[ButtonMessage, SelectorMessage, WxbotMarkdownMessage]] = Field(
        default=[], description="layouts"
    )
    extra_config: dict = Field(default={}, description="extra config")

    @property
    def wx_json(self):
        layout_item = {
            "type": self.layout_type.value,
            "components": list(chain(*[item.wx_json_list for item in self.layouts])),
        }
        layout_item.update(self.extra_config)
        layouts = [layout_item]
        return layouts

    def append(self, component):
        self.layouts.append(component)

    def insert(self, index, component):
        self.layouts.insert(index, component)


class WxBotSurfaceMessage(Message):
    msg_type: str = Field(default=MsgType.WxBotSurface.value, description="type of message")
    layouts: list[LayoutMessage] = Field(default=[], description="layouts")

    @property
    def wx_json(self):
        return {"msgtype": "message", "layouts": [item.wx_json for item in self.layouts]}
