import json
import logging
from typing import Any, Callable, Dict, List, Literal

from aidev_agent.services.pydantic_models import AgentOptions
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.utils.tools import timeit
from aidev_agent.core.knowledge.config import ProceduralRetrieverSettings
from aidev_agent.core.knowledge.schemas import ProceduralDocument
from aidev_agent.core.knowledge.protocol import VectorFilter, ScalarFilter, Filter
from aidev_agent.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class BkRetriever(BaseRetriever):
    """
    BkAi retriever: 用于使用 BkAi 平台知识库的检索机制进行长期记忆检索。
    包含以下两种机制：
    1. iwiki 文本召回
    2. csv 格式化的程序记忆
    """
    # ====================================================================================================
    # ES 相关内容，均未实现
    # ====================================================================================================
    def _es_client(self):
        raise NotImplementedError

    def _parse_es_hits(self, es_resp):
        raise NotImplementedError

    @timeit(message="知识库检索（ES方式，使用完整query）")
    def search_knowledge_es_query(
        self, knowledge_items: list[dict], knowledge_bases: list[dict], query, topk, **kwargs
    ):
        """基于ES获取相关文档（ES方式，使用完整query）"""
        raise NotImplementedError

    @timeit(message="知识库检索（ES方式，使用提取的关键词）")
    def search_knowledge_es_keywords(
        self, knowledge_items: list[dict], knowledge_bases: list[dict], extracted_keywords, topk, **kwargs
    ):
        raise NotImplementedError

    # ====================================================================================================
    # BK 知识库查询相关内容，依赖 api.create_knowledgebase_query 接口
    # ====================================================================================================
    @property
    def _query_instance(self) -> Callable:
        """
        对应 intent_recognition.py 第70-77行的 _query_instance 方法
        """
        try:
            obj = import_string("aidev.resource.knowledge_base.services.KnowledgeQueryService")
            return obj.internal_query
        except ImportError:
            # 不能resource则使用sdk
            client = BKAidevApi.get_client()
            return client.knowledge_query

    def _search_knowledge_by_client(self, data: dict):
        if "knowledge_template_id" in data and data["knowledge_template_id"] is None:
            data.pop("knowledge_template_id")
        try:
            logger.info(f"查询知识库： {data}")
            result = self._query_instance(data)
            docs = result["documents"]
            for doc in docs:
                if isinstance(doc, Document):
                    if not hasattr(doc, "metadata"):
                        raise RuntimeError(f"召回的文档缺少 metadata 字段！\n文档内容为：{doc}\n")
                    if "__score__" not in doc.metadata:
                        raise RuntimeError(f"召回的文档缺少 __score__ 字段！\n文档内容为：{doc}\n")
                elif isinstance(doc, dict):
                    if "metadata" not in doc:
                        raise RuntimeError(f"召回的文档缺少 metadata 字段！\n文档内容为：{doc}\n")
                    if "__score__" not in doc["metadata"]:
                        raise RuntimeError(f"召回的文档缺少 __score__ 字段！\n文档内容为：{doc}\n")
                else:
                    raise RuntimeError(f"召回文档格式有误！\n文档内容为：{doc}\n")
            return docs
        except Exception as err:
            logger.error(f"\n\n=====\n>>>>> 知识库查询接口调用出错！\n\ndata 内容为：\n{data}\n\n error: {err}")
            raise

    def _construct_index_query_kwargs(
        self, index_query_kwargs, query, knowledges, knowledge_type, resource_type, **kwargs
    ):
        """
        对应 intent_recognition.py 第104-161行的 _construct_index_query_kwargs 方法，和原方法保持一致，请勿修改
        """
        knowledge_type_to_id_type = {
            "knowledge_items": "knowledge_id",
            "knowledge_bases": "knowledge_base_id",
        }
        if resource_type == "knowledge":
            custom_index_name_key = "knowledge_resource_index_names"
        elif resource_type == "tool":
            custom_index_name_key = "tool_resource_index_names"
        else:
            raise ValueError(f"不支持的 resource 类型：{resource_type}")
        if knowledges:
            supported_ids = [knowledge.get("id") for knowledge in knowledges]
            for knowledge in knowledges:
                all_index_names = []
                supported_index_names = []
                if index_config := knowledge.get("index_config"):
                    for index_type in ["full_text_indexes", "vector_indexes"]:
                        if indexes := index_config.get(index_type):
                            for index in indexes:
                                if index_name := index.get("index_name"):
                                    supported_index_names.append(index_name)

                    custom_index_names = kwargs.get(custom_index_name_key, {})
                    custom_index_names_type = custom_index_names.get(knowledge_type)
                    if custom_index_names and custom_index_names_type:
                        if not set(list(custom_index_names_type.keys())).issubset(set(supported_ids)):
                            raise ValueError(
                                f"传入的 {knowledge_type} 类型的 ID 有：{supported_ids}，"
                                f"但传入的 {knowledge_type} 类型的自定义的向量索引 ID 有："
                                f"{list(custom_index_names_type.keys())}，"
                                "请确保后者是前者的子集！"
                            )
                        if custom_index_names_type_id := custom_index_names_type.get(knowledge.get("id")):
                            if not set(custom_index_names_type_id).issubset(set(supported_index_names)):
                                raise ValueError(
                                    f"{knowledge_type} 类型的知识（库）ID {knowledge.get('id')} "
                                    f"支持的向量索引有：{supported_index_names}，"
                                    f"但传入的自定义向量索引为：{custom_index_names_type_id}，"
                                    "请传入支持的向量索引的子集！"
                                )
                            all_index_names = custom_index_names_type_id
                if not all_index_names:
                    all_index_names = supported_index_names
                if not all_index_names:
                    raise RuntimeError(f"{knowledge_type} 类型的知识（库）ID {knowledge.get('id')} 的索引为空！")
                index_query_kwargs.extend(
                    [
                        {
                            "index_name": index_name,
                            "index_value": query,
                            knowledge_type_to_id_type[knowledge_type]: knowledge["id"],
                        }
                        for index_name in all_index_names
                    ]
                )

    def _construct_simple_filter(self, query, index_name, knowledge_id, knowledge_base_id, topk, scalar_expression, **kwargs):
        if scalar_expression:
            scalar_expression = scalar_expression.format(**kwargs)

        # 构建向量过滤器
        vector_filter = VectorFilter(
            index_name=index_name,
            index_value=query,
            knowledge_id=knowledge_id,
            knowledge_base_id=knowledge_base_id,
            topk=topk,
            scalar=ScalarFilter(expression=scalar_expression) if scalar_expression else None
        )
        return Filter(vector=[vector_filter], scalar=[])

    @timeit(message="知识库检索（index_specific方式）")
    def search_knowledge_index_specific(
        self,
        knowledge_items: list[dict],
        knowledge_bases: list[dict],
        query,
        topk,
        agent_options,
        resource_type="knowledge",
        **kwargs,
    ):
        """
        对应 intent_recognition.py 第164-191行的 search_knowledge_index_specific 方法
        基于向量检索获取相关文档（index_specific方式）
        """
        index_query_kwargs = []
        self._construct_index_query_kwargs(
            index_query_kwargs, query, knowledge_items, "knowledge_items", resource_type=resource_type, **kwargs
        )
        self._construct_index_query_kwargs(
            index_query_kwargs, query, knowledge_bases, "knowledge_bases", resource_type=resource_type, **kwargs
        )
        data = {
            "query": query,
            "topk": topk,
            "index_query_kwargs": index_query_kwargs,
            "knowledge_template_id": agent_options.knowledge_query_options.knowledge_template_id,
            "with_scalar_data": agent_options.knowledge_query_options.with_scalar_data,
            "raw": True,  # 知识库查询接口集成了本文件中的重排逻辑，设置为True防止循环重排。下同
            "type": "index_specific",
        }
        return self._search_knowledge_by_client(data)

    @timeit(message="知识库检索（index_specific方式，使用提取的关键词）")
    def search_knowledge_index_specific_keywords(
        self,
        knowledge_items: list[dict],
        knowledge_bases: list[dict],
        extracted_keywords,
        topk,
        agent_options,
        **kwargs,
    ):
        """
        对应 intent_recognition.py 第194-215行的 search_knowledge_index_specific_keywords 方法
        基于index_specific获取相关文档（index_specific方式，使用提取的关键词）
        """
        if extracted_keywords:
            return self.search_knowledge_index_specific(
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                query="\n\n".join(extracted_keywords),
                topk=topk,
                disable_timeit=True,
                agent_options=agent_options,
                **kwargs,
            )
        else:
            return []

    @timeit(message="知识库检索（index_specific方式，使用翻译后的中文）")
    def search_knowledge_index_specific_translation(
        self, knowledge_items: list[dict], knowledge_bases: list[dict], translated_query, topk, agent_options, **kwargs
    ):
        """
        对应 intent_recognition.py 第218-233行的 search_knowledge_index_specific_translation 方法
        基于index_specific获取相关文档（index_specific方式，使用翻译后的中文）
        """
        if translated_query:
            return self.search_knowledge_index_specific(
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                query=translated_query,
                topk=topk,
                disable_timeit=True,
                agent_options=agent_options,
                **kwargs,
            )
        else:
            return []

    @timeit(message="知识库检索（nature方式）")
    def search_knowledge_nature(self, knowledge_items: list[dict], knowledge_bases: list[dict], query, topk, **kwargs):
        """
        对应 intent_recognition.py 第235-248行的 search_knowledge_nature 方法
        基于向量检索获取相关文档（nature方式）
        """
        data = {
            "query": query,
            "topk": topk,
            "knowledge_id": [knowledge["id"] for knowledge in knowledge_items],
            "knowledge_base_id": [knowledge["id"] for knowledge in knowledge_bases],
            "knowledge_template_id": 0,
            "with_scalar_data": True,
            "raw": True,
            "type": "nature",
        }
        return self._search_knowledge_by_client(data)

    @timeit(message="程序记忆检索")
    def search_procedural(self, query: str, index_name: str, knowledge_id: int, knowledge_base_id: int, topk: int, scalar_expression: str, **kwargs):
        data = {
            "query": query,
            "type": "index_specific",
            "filter": self._construct_simple_filter(
                query,
                index_name=index_name,
                knowledge_id=knowledge_id,
                knowledge_base_id=knowledge_base_id,
                topk=topk,
                scalar_expression=scalar_expression,
                **kwargs
            ).model_dump(),
            "with_scalar_data": True,
            "raw": True,
        }
        # 调用API
        return self._search_knowledge_by_client(data)

    def parse_procedural_response(self, documents: List[Dict[str, Any]], desc_field_name: str, procedure_field_name: str):
        """解析程序记忆API响应。

        Args:
            documents: API响应字典
            desc_field_name: 描述字段名
            procedure_field_name: 程序字段名
        Returns:
            List[Document]: 解析后的程序记忆列表

        Raises:
            KeyError: 当响应中缺少必需字段时
            JSONDecodeError：当page_content不是有效的JSON字符串时
        """
        procedural_documents = []
        for doc in documents:
            # 获取page_content并解析JSON, page_content目前要求是一个 json 格式的字符串
            # 如果 doc 中没有page_content字段，会抛出 KeyError 的异常
            # 如果 page_content 不是有效的JSON字符串，会抛出 JSONDecodeError 的异常
            page_content: dict = json.loads(doc["page_content"])
            # 根据配置获取desc和procedure字段
            desc_value = page_content.get(desc_field_name, '')
            procedure_value = page_content.get(procedure_field_name, '')
            # 创建 ProceduralDocument 对象
            procedural_documents.append(ProceduralDocument(
                page_content=doc["page_content"],
                metadata=doc["metadata"],
                desc=desc_value,
                procedure=procedure_value
            ))

        return procedural_documents

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun,
        retriever_type: Literal["procedural", "knowledge"] = "procedural",
        agent_options: AgentOptions = None,
        procedural_options: ProceduralRetrieverSettings = None,
        **kwargs
    ) -> list[Document]:
        if retriever_type == "procedural":
            res = self.search_procedural(
                query,
                index_name=procedural_options.index_name,
                knowledge_id=procedural_options.knowledge_id,
                knowledge_base_id=procedural_options.knowledge_base_id,
                topk=procedural_options.topk,
                scalar_expression=procedural_options.scalar_expression,
                **kwargs
            )
            return self.parse_procedural_response(
                res,
                procedural_options.desc_field_name,
                procedural_options.procedure_field_name
            )
        raise ValueError("不支持使用 invoke 召回的类型")
