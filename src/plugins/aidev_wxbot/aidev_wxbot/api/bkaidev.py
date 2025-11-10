from aidev_wxbot.api import BkApi


class BkAiDevApi:
    def __init__(self):
        self.api = BkApi()

    def retrieve_agent_channel_configs(self, channel_type):
        return self.api.call_action(
            f"openapi/aidev/resource/v1/agent_channel/configs/?channel_type={channel_type}", "GET"
        )

    def convert_to_rtx(self, openid):
        return self.api.call_action(
            "openapi/aidev/resource/v1/qyweixin/convert_to_userid/", "POST", json={"openid": openid}
        )
