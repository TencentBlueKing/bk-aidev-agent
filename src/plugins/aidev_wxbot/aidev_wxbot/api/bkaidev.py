from aidev_wxbot.api import BkApi
from aidev_wxbot.wxaibot.tracing import CLIENT, trace_headers, wxbot_span


class BkAiDevApi:
    def __init__(self):
        self.api = BkApi()

    def retrieve_agent_channel_configs(self, channel_type):
        with wxbot_span("wxbot.channel_config.fetch", kind=CLIENT):
            return self.api.call_action(
                f"openapi/aidev/resource/v1/agent_channel/configs/?channel_type={channel_type}",
                "GET",
                headers=trace_headers(),
            )

    def convert_to_rtx(self, openid):
        return self.api.call_action(
            "openapi/aidev/resource/v1/qyweixin/convert_to_userid/",
            "POST",
            json={"openid": openid},
            headers=trace_headers(),
        )
