from typing import Union

from pydantic import BaseConfig, BaseModel, ConfigDict, Field

from aidev_wxbot.context.message import Message
from aidev_wxbot.utils import AttrDict


class Context(BaseModel):
    # config类信息：
    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={BaseConfig: lambda v: v.to_dict(), AttrDict: lambda v: v.to_dict()}
    )
    msg_proxy_config: Union[BaseConfig, AttrDict, None] = Field(default=None, description="msg proxy config")

    # message相关：
    message: Union[Message, None] = Field(default=None, description="message content")
    # message来源信息：
    from_type: Union[str, None] = Field(default=None, description="whether message is from group or single")
    sender_id: Union[str, None] = Field(default=None, description="sender id")
    sender_code: Union[str, None] = Field(default=None, description="sender code")
    group_id: Union[str, None] = Field(default=None, description="message group id")
    create_time: Union[str, None] = Field(default=None, description="message send time, default str")
    to_me: bool = Field(default=False, description="whether message is send to bot")

    # api：
    payload: Union[dict, None] = Field(default=None, description="params from api request")
    action: Union[str, None] = Field(default=None, description="api action name")

    # other param：
    param_value: Union[str, None] = Field(default=None, description="set param value in this attribute")
    param_name: Union[str, None] = Field(default=None, description="set waiting param name in this attribute")

    def __getitem__(self, item):
        """
        Compatible with older versions using like a dict
        :param item:
        :return:
        """
        return getattr(self, item)

    def get(self, item, default=None):
        """
        Compatible with older versions using like a dict
        :param default:
        :param item:
        :return:
        """
        return getattr(self, item, default)
