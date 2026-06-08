# -*- coding: utf-8 -*-

import copy

from django.conf import settings
from rest_framework.views import Response

from aidev_bkplugin.views.base import PluginViewSet


class ChatGroupViewSet(PluginViewSet):
    def create(self, request):
        data = request.data
        username = request.user.username

        data["users"] = copy.deepcopy(settings.CHAT_GROUP_STAFF)
        data["users"].append(username)
        data["chat_group_type"] = settings.CHAT_GROUP_TYPE
        data["username"] = username

        result = self.client.api.create_chat_group(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])
