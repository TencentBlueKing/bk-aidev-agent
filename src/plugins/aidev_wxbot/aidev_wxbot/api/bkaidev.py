from django.conf import settings

from aidev_wxbot.api import BkApi


class BkAiDevApi:
    def __init__(self):
        self.api = BkApi("bkaidev")

    def retrieve_agent_channel_configs(self, channel_type):
        return self.api.call_action(
            f"openapi/aidev/resource/v1/agent_channel/configs/?channel_type={channel_type}", "GET"
        )

    def convert_to_rtx(self, open_id):
        return self.api.call_action("resource/v1/qyweixin/convert_to_userid/", "POST", json={"open_id": open_id})


class AgentBackend:
    def __init__(self):
        self.api = BkApi(settings.BKPAAS_BK_PLUGIN_APIGW_NAME)

    def invoke(self, content):
        data = {
            "inputs": {
                "command": "chat",
                "input": content,
                "stream": False,
                "chat_history": [{"role": "user", "content": content}],
                "context": [],
            },
            "context": {"executor": "user"},
        }
        return self.api.call_action("invoke/1.0.0assistant", "POST", json=data)
