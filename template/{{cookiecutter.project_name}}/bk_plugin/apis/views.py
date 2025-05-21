import os

from aidev_agent.api.bk_aidev import BKAidevApi
from django.conf import settings
from django.http import HttpResponse
from langchain_core.prompts import jinja2_formatter
from rest_framework.views import APIView

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


class IndexView(APIView):
    def get(self, request):
        client = BKAidevApi.get_client()
        result = client.api.retrieve_agent_config(path_params={"agent_code": settings.APP_CODE})
        agent_name = result["data"]["agent_name"]
        with open(f"{BASE_DIR}/dist/index.html") as fo:
            rendered = jinja2_formatter(
                fo.read(),
                SITE_URL="",
                BK_STATIC_URL="",
                BK_API_PREFIX="/bk_plugin/plugin_api",
                BK_USER_NAME=getattr(request.user, "username", ""),
                BK_AGENT_NAME=agent_name,
            )
        return HttpResponse(rendered)
