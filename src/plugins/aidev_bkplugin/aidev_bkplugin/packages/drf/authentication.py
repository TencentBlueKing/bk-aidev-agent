# -*- coding: utf-8 -*-

from rest_framework.authentication import SessionAuthentication

from aidev_bkplugin.utils import is_local_dev


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """关闭csrf验证"""

    def enforce_csrf(self, request):
        return


custom_authentication_classes = (
    [
        CsrfExemptSessionAuthentication,
    ]
    if is_local_dev()
    else []
)
