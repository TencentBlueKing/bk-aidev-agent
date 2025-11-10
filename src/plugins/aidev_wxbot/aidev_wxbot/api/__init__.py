import json
from logging import getLogger

import requests
from django.conf import settings

logger = getLogger(__name__)


class ActionFailed(Exception):
    """
    Action failed to execute.
    """

    def __init__(self, code, info=None):
        self.code = code
        self.info = info


class Api(object):
    def __init__(self, base_url):
        self.base_url = base_url

    def get_auth_header(self, bk_username):
        return {}

    def call_action(self, action: str, method="POST", bk_username="admin", **params):
        if not bk_username:
            bk_username = (
                params.get("json", {}).get("bk_username", None)
                or params.get("params", {}).get("bk_username", None)
                or "admin"
            )
        auth_header = self.get_auth_header(bk_username)
        url = f"{self.base_url}/{action}"
        if "headers" not in params:
            params["headers"] = auth_header
        else:
            params["headers"].update(auth_header)
        logger.info(
            f"\n-----call action-----\n {method}\n {url}\n"
            f" {json.dumps(params, ensure_ascii=False)} \n-------------------"
        )
        try:
            response = requests.request(method, url, **params)
            logger.info(f"\n-----resp-----\n {response.url} {response.text}")
            if 200 <= response.status_code < 300:
                result = response.json()
                if isinstance(result, dict):
                    if (
                        result.get("result", False)
                        or result.get("code", -1) == 0
                        or result.get("status", -1) != -1
                        or result.get("errcode", 1) == 0
                    ):
                        return result.get("data", result)
                    logger.exception(result)
                    raise ActionFailed(code=result.get("code"), info=result)

            logger.exception(response.text)
        except Exception as e:
            logger.exception(e)
            raise e


class BkApi(Api):
    BK_APIGW_MANAGER_URL_TMPL = settings.BK_APIGW_MANAGER_URL_TMPL
    AIDEV_GATEWAY_NAME = settings.AIDEV_GATEWAY_NAME
    BK_APIGW_STAGE = settings.BK_APIGW_STAGE
    BKPAAS_APP_SECRET = settings.BKPAAS_APP_SECRET
    BKPAAS_APP_CODE = settings.BKPAAS_APP_CODE

    def __init__(self, api_name=None):
        api_name = api_name or self.AIDEV_GATEWAY_NAME
        base_url = f"{self.BK_APIGW_MANAGER_URL_TMPL}/{self.BK_APIGW_STAGE}".format(api_name=api_name)
        super().__init__(base_url)

    def get_auth_header(self, bk_username):
        return {
            "X-Bkapi-Authorization": json.dumps(
                {
                    "bk_app_code": self.BKPAAS_APP_CODE,
                    "bk_app_secret": self.BKPAAS_APP_SECRET,
                    "bk_username": bk_username,
                }
            )
        }
