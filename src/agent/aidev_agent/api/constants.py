# -*- coding: utf-8 -*-
from aidev_agent.config import settings

APIGW_URL_FORMAT = "{}/{{stage}}".format(settings.BK_API_URL_TMPL)

AUTHORIZATION_HEADER = "X-Bkapi-Authorization"

CONCURRENCY_NUMS = 1

PAGE_SIZE = 10
LIMIT = 500
