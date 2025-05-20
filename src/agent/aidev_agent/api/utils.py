# -*- coding: utf-8 -*-
import logging

from aidev_agent.api.constants import APIGW_URL_FORMAT, PAGE_SIZE
from aidev_agent.config import settings

logger = logging.getLogger("component")


def get_endpoint(api_name, stage=None):
    """
    获取BK-API endpoint
    """
    # 默认环境
    if not stage:
        stage = "prod" if settings.RUN_MODE == "PRODUCT" else "stag"
    return APIGW_URL_FORMAT.format(api_name=api_name, stage=stage)


gevent_active = False

try:
    import gevent

    gevent_active = True

    def bulk_fetch(
        esb_function, kwargs=None, get_data=lambda x: x["results"], get_count=lambda x: x["count"], limit=PAGE_SIZE
    ):
        """
        并发请求接口，用于需要分页多次请求的情况
        :param esb_function: api方法对象
        :param kwargs: api请求参数
        :param get_data: 获取数据函数
        :param get_count: 获取总数函数
        :param limit: 一次请求数量
        :return: 请求结果
        """
        request_params = {"page": 1, "page_size": limit}
        request_params.update(kwargs)

        response = esb_function(request_params)
        if not response or not response["result"]:
            raise ValueError(response["message"])

        result = response["data"]
        count = get_count(result)
        data = get_data(result)
        start = limit

        futures = []
        while start < count:
            next_offset = start

            next_page = (next_offset / limit) + 1

            request_params = {"page": int(next_page), "page_size": limit}

            request_params.update(kwargs)

            futures.append(gevent.spawn(esb_function, request_params))

            start += limit

        gevent.joinall(futures)

        for res in futures:
            data.extend(get_data(res.value["data"]))

        logger.info(f"[aidev.packages.api.utils.bulk_fetch] {esb_function}: params: {kwargs}")
        return data
except ImportError:
    from multiprocessing.pool import ThreadPool

    def bulk_fetch(
        esb_function,
        kwargs=None,
        get_data=lambda x: x["results"],
        get_count=lambda x: x["count"],
        limit=PAGE_SIZE,
        max_workers=10,
    ):
        """
        并发请求接口，用于需要分页多次请求的情况
        :param esb_function: api方法对象
        :param kwargs: api请求参数，默认为None
        :param get_data: 获取数据函数，默认从结果中提取"results"字段
        :param get_count: 获取总数函数，默认从结果中提取"count"字段
        :param limit: 一次请求数量，默认为PAGE_SIZE
        :param max_workers: 线程池最大工作线程数，默认为10
        :return: 请求结果列表
        """
        if kwargs is None:
            kwargs = {}

        request_params = {"page": 1, "page_size": limit}
        request_params.update(kwargs)

        # 首次请求获取总数
        response = esb_function(request_params)
        if not response or not response["result"]:
            raise ValueError(response.get("message", "Unknown error occurred"))

        result = response["data"]
        count = get_count(result)
        data = get_data(result)

        # 计算需要并发的请求数量
        total_pages = (count + limit - 1) // limit  # 向上取整
        if total_pages <= 1:
            return data

        # 准备并发请求参数
        requests_params = []
        for page in range(2, total_pages + 1):
            params = {"page": page, "page_size": limit}
            params.update(kwargs)
            requests_params.append(params)

        # 使用线程池并发请求
        with ThreadPool(processes=max_workers) as pool:
            responses = pool.map(esb_function, requests_params)

        # 处理响应结果
        for resp in responses:
            if resp and resp.get("result"):
                data.extend(get_data(resp["data"]))
            else:
                logger.warning(f"请求失败: {resp.get('message', 'Unknown error')}")

        logger.info(f"[aidev.packages.api.utils.bulk_fetch] {esb_function.__name__}: params: {kwargs}")
        return data
