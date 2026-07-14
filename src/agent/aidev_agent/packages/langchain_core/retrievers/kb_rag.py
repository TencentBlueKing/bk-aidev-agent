# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import concurrent.futures
import copy
import logging
import os
from collections import defaultdict
from typing import Any, ClassVar, Dict, List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from typing_extensions import NotRequired

from aidev_agent.enums import Decision, FineGrainedScoreType, IndependentQueryMode
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.packages.langchain_core.retrievers.utils import deduplicate_knowledge_chunks, is_structured_data
from aidev_agent.packages.langgraph.streaming.utils import conditional_dispatch_custom_event
from aidev_agent.pydantic_models import KnowledgeSettings
from aidev_agent.utils.decorator import retry, timeit

from .prompts import DEFAULT_INTENT_RECOGNITION_PROMPT_TEMPLATES
from .utils import (
    HUNYUAN_SPECIFIC_RESPONSE,
    calculate_similarity,
    deduplicate_knowledge_file_paths,
    dispatch_rag_event_chunk,
    invoke_decorator,
    normalize_query_for_search,
    resolve_display_sort_key,
)

logger = logging.getLogger(__name__)

knowledge_bk_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("KNOWLEDGE_BK_EXECUTOR_MAX_WORKERS", "10"))
)


class KnowledgeRagRetrieveResult(TypedDict):
    """
    知识库召回的 State 输出字段
        - knowledge_content: 高相关性知识内容
        - knowledge_qa_content: QA 对知识内容
        - reference_doc: 去重后的知识文件路径列表
        - decision: Decision 枚举 (GENERAL_QA/PRIVATE_QA/QUERY_CLARIFICATION)
        - with_qa_response: QA 响应标记
        - knowledge_resources_highly_relevant: 高相关性资源
        - knowledge_resources_moderately_relevant: 中等相关性资源
        - knowledge_resources_lowly_relevant: 低相关性资源
        - knowledge_resources_emb_recalled: 所有 embedding 召回的资源（含细粒度分数），用于 AIDev 产品页面检索测试

    其中：knowledge_content 和 knowledge_qa_content 会被用于后续 Model 节点的 prompt_var 拼接
    其中：decision 和 with_qa_response 用于 后续 Model 选择模板
    其中：reference_doc 用于给 invoke 提供返回知识库召回了哪些文档
    其中：knowledge_resources_highly_relevant，knowledge_resources_moderately_relevant， knowledge_resources_lowly_relevant 用于审计返回知识相关性
    其中：knowledge_resources_emb_recalled 用于 AIDev 产品页面检索测试，返回所有召回资源（带细粒度分数）
    """

    decision: Decision
    knowledge_resources_highly_relevant: list
    knowledge_resources_moderately_relevant: list
    knowledge_resources_lowly_relevant: list
    knowledge_resources_emb_recalled: NotRequired[list]
    knowledge_content: NotRequired[list]
    knowledge_qa_content: NotRequired[list]
    translated_query: NotRequired[str]
    with_qa_response: NotRequired[bool]
    reference_doc: NotRequired[list]
    response: NotRequired[str]


class KnowledgeRag:
    """
    RAG 检索增强生成（Retrieval Augmented Generation）
    包含 pre_retrieval、retrieval、post_retrieval 三个主要阶段

    在关于智能体的认知研究中，长期记忆一般分为程序记忆，语义记忆，情感记忆
    语义记忆也就是对一般知识和概念的存储和处理，目前使用向量化数据库来实现知识库的检索和加载
    对于 AGent 使用：
        默认使用两步 RAG
        提供Agentic RAG，以便于让LLM 驱动的Agent决定何时以及如何在推理过程中进行检索
    """

    intent_recognition_prompt_templates: ClassVar[Dict[str, Any]] = DEFAULT_INTENT_RECOGNITION_PROMPT_TEMPLATES

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        parent_factory = getattr(super(cls, cls), "intent_recognition_prompt_templates", {})
        current_factory = getattr(cls, "intent_recognition_prompt_templates", {})
        cls.intent_recognition_prompt_templates = {**parent_factory, **current_factory}

    def __init__(
        self,
        llm=None,
        kb_retriever: BkRetriever | None = None,
    ) -> None:
        self.llm = llm or ChatModel.get_setup_instance(model="hunyuan-turbo")
        self.kb_retriever = kb_retriever or BkRetriever()

    # ====================================================================================================
    # PRE_RETRIEVAL 阶段方法
    # ====================================================================================================
    def query_transformation(self, query: str, **kwargs) -> str:
        """
        查询转换 - 将用户问题进行转换，防止用户的模糊性表达
        对应 intent_recognition.py 中的查询重写相关功能
        """
        # 该方法在 intent_recognition.py 中有多个相关实现，包括：
        # - query_rewrite_for_independence (第342-377行)
        # - query_cls_with_resp_or_rewrite (第381-423行)
        # 等待具体实现

    def query_enhancement(self, query: str, **kwargs) -> str:
        """
        查询增强 - 增强或者扩大用户输入的query语义，例如预设答案
        对应 intent_recognition.py 中的查询翻译和关键词提取功能
        """
        # 该方法在 intent_recognition.py 中有相关实现：
        # - query_translation (第293-310行)
        # - extract_query_keywords (第271-289行)
        # 等待具体实现

    def query_decomposition(self, query: str, **kwargs) -> List[str]:
        """
        查询分解 - 把用户的复杂query分解成多个可管理的子问题
        """
        # intent_recognition.py 中没有直接对应的实现
        # 等待具体实现

    @timeit(message="用户提问关键词提取")
    @retry(max_retries=5, max_seconds=3600)
    def extract_query_keywords(self, query, llm, **kwargs):
        """
        对应 intent_recognition.py 第271-289行的 extract_query_keywords 方法
        """
        sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "extract_query_keywords_sys_prompt_template"
        )
        usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "extract_query_keywords_usr_prompt_template"
        ).render(query=query)
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        # TODO: 待确认：并发请求内部无法 dispatch_custom_event，所以无需调用 conditional_dispatch_custom_event
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages)
        resp_content = resp.content
        extracted_keywords = resp_content.strip().split("\n")
        extracted_keywords = list(filter(None, extracted_keywords))
        logger.info(f"=====> <extract_query_keywords的结果>：{extracted_keywords}")
        return extracted_keywords

    @timeit(message="用户提问翻译")
    @retry(max_retries=5, max_seconds=3600)
    def query_translation(self, query, llm, **kwargs):
        """
        对应 intent_recognition.py 第293-310行的 query_translation 方法
        """
        sys_prompt = self.__class__.intent_recognition_prompt_templates.get("query_translation_sys_prompt_template")
        usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "query_translation_usr_prompt_template"
        ).render(query=query)
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        # TODO: 待确认：并发请求内部无法 dispatch_custom_event，所以无需调用 conditional_dispatch_custom_event
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages)
        resp_content = resp.content
        logger.info(f"=====> <query_translation的结果>：{resp_content}")
        if resp_content.strip() == "None":
            return None
        else:
            return resp_content

    @timeit(message="意图切换检测")
    @retry(max_retries=5, max_seconds=3600)
    def latest_query_classification(self, chat_history, query, llm, **kwargs):
        sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "latest_query_classification_sys_prompt_template"
        )
        usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "latest_query_classification_usr_prompt_template"
        ).render(chat_history=chat_history, query=query)
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        conditional_dispatch_custom_event("custom_event", {"front_end_display": False}, **kwargs)
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages, **kwargs)
        conditional_dispatch_custom_event("custom_event", {"front_end_display": True}, **kwargs)
        resp_content = resp.content
        logger.info(f"=====> <query分类结果>：{resp_content}")
        if "<<<<<new>>>>>" in resp_content:
            return "new"
        elif "<<<<<continue>>>>>" in resp_content:
            return "continue"
        elif "<<<<<finish>>>>>" in resp_content:
            return "finish"
        else:
            return "new"  # 其余所有边缘情况默认直接重新开始

    @timeit(message="独立查询重写")
    @retry(max_retries=5, max_seconds=3600)
    def query_rewrite_for_independence(self, chat_history, query, llm, display=False, **kwargs):
        """
        对应 intent_recognition.py 第342-377行的 query_rewrite_for_independence 方法
        :param display: 是否将独立查询重写的结果也展示在前端
        """
        sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "query_rewrite_for_independence_sys_prompt_template"
        )
        usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "query_rewrite_for_independence_usr_prompt_template"
        ).render(chat_history=chat_history, query=query)
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        if display:
            conditional_dispatch_custom_event(
                "custom_event",
                {"custom_return_chunk": "结合历史对话信息，您似乎是想问："},
                **kwargs,
            )
            invoke_func = invoke_decorator(llm.invoke, llm)
            resp = invoke_func(messages, **kwargs)
            conditional_dispatch_custom_event(
                "custom_event",
                {"custom_return_chunk": "。接下来我尝试进行回答。\n\n"},
                **kwargs,
            )
        else:
            # 包在这 2 行 conditional_dispatch_custom_event 代码之间的 LLM 输出不会在前端展示
            conditional_dispatch_custom_event("custom_event", {"front_end_display": False}, **kwargs)
            invoke_func = invoke_decorator(llm.invoke, llm)
            resp = invoke_func(messages, **kwargs)
            conditional_dispatch_custom_event("custom_event", {"front_end_display": True}, **kwargs)
        resp_content = resp.content
        logger.info(f"=====> <query重写结果>：{resp_content}")
        return resp_content

    @timeit(message="独立查询重写，依据上下文总结")
    @retry(max_retries=5, max_seconds=3600)
    def sum_chat_history_for_query(self, chat_history, query, llm, **kwargs):
        if not chat_history:
            return None
        sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "sum_chat_history_for_query_sys_prompt_template"
        )
        usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "sum_chat_history_for_query_usr_prompt_template"
        ).render(chat_history=chat_history, query=query)
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        conditional_dispatch_custom_event("custom_event", {"front_end_display": False}, **kwargs)
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages, **kwargs)
        conditional_dispatch_custom_event("custom_event", {"front_end_display": True}, **kwargs)
        resp_content = resp.content
        if resp_content.strip() == "None":
            return None
        else:
            return resp_content

    @timeit(message="意图切换检测和独立查询重写/直接答复")
    @retry(max_retries=5, max_seconds=3600)
    def query_cls_with_resp_or_rewrite(self, chat_history, query, llm, **kwargs):
        sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "query_cls_with_resp_or_rewrite_sys_prompt_template"
        )
        usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
            "query_cls_with_resp_or_rewrite_usr_prompt_template"
        ).render(chat_history=chat_history, query=query)
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        conditional_dispatch_custom_event("custom_event", {"front_end_display": False}, **kwargs)
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages)
        conditional_dispatch_custom_event("custom_event", {"front_end_display": True}, **kwargs)
        resp_content = resp.content
        logger.info(f"=====> <query_cls_with_resp_or_rewrite的结果>：{resp_content}")
        if resp_content.startswith("<<<<<new>>>>>"):
            return {
                "query_cls": "new",
            }
        elif resp_content.startswith("<<<<<continue>>>>>"):
            if resp_content.startswith("<<<<<continue>>>>>$REWRITTEN_QUERY: "):
                rewritten_query = resp_content[len("<<<<<continue>>>>>$REWRITTEN_QUERY: ") :]
            else:
                rewritten_query = resp_content[len("<<<<<continue>>>>>") :]
            return {
                "query_cls": "continue",
                "rewritten_query": rewritten_query,
            }
        elif resp_content.startswith("<<<<<finish>>>>>"):
            if resp_content.startswith("<<<<<finish>>>>>$RESPONSE: "):
                response = resp_content[len("<<<<<finish>>>>>$RESPONSE: ") :]
            else:
                response = resp_content[len("<<<<<finish>>>>>") :]
            return {
                "query_cls": "finish",
                "response": response,  # TODO: 后半段stream化
            }
        else:
            return {
                "query_cls": "new",
            }  # 其余所有边缘情况默认直接重新开始

    def query_cls_pipeline(self, chat_history, query, llm, knowledge_query_options: KnowledgeSettings, **kwargs):
        if knowledge_query_options.merge_query_cls_with_resp_or_rewrite:
            if chat_history:
                result = self.query_cls_with_resp_or_rewrite(chat_history, query, llm, **kwargs)
                query_cls = result["query_cls"]
            else:
                # 如无history，目前处理成相当于开始一个新的话题
                query_cls = "new"

            if query_cls == "finish":
                # 如果是结束话题，则直接返回生成的回复
                # 待实现，目前先用通识知识回答
                return KnowledgeRagRetrieveResult(
                    response=result["response"],
                    decision=Decision.GENERAL_QA,
                    knowledge_resources_highly_relevant=[],
                    knowledge_resources_moderately_relevant=[],
                    knowledge_resources_lowly_relevant=[],
                )
            elif query_cls == "continue":
                # 如果是继续话题，则其实也未必能直接复用上一轮会话的意图识别结果（除了）
                # 因为例如用户是在RAG意图下，但是改了原本输错的参数，则其实也是需要重新检索资源进行新的具体资源意图判断的
                # 因此，意图识别结果的复用其实最多到知识类、资源类这种级别的复用
                independent_query = result["rewritten_query"]
            elif query_cls == "new":
                # 如果是新的话题，则独立query即为输入的query
                independent_query = query
        else:
            if chat_history:
                if knowledge_query_options.with_query_cls:
                    query_cls = self.latest_query_classification(chat_history, query, llm, **kwargs)
                else:
                    query_cls = "continue"
            else:
                query_cls = "new"

            if query_cls == "finish":
                return KnowledgeRagRetrieveResult(
                    decision=Decision.GENERAL_QA,
                    knowledge_resources_highly_relevant=[],
                    knowledge_resources_moderately_relevant=[],
                    knowledge_resources_lowly_relevant=[],
                )
            elif query_cls == "continue":
                independent_query = self.query_rewrite_for_independence(chat_history, query, llm, **kwargs)
            elif query_cls == "new":
                independent_query = query

        return independent_query

    # ====================================================================================================
    # RETRIEVAL 阶段方法
    # 使用具体的 Retrival 类来实现
    # 默认使用 Bk_Retriever
    # ====================================================================================================

    # ====================================================================================================
    # POST_RETRIEVAL 阶段方法
    # ====================================================================================================

    def rerank(self, docs: List[Document], query: str, **kwargs) -> List[Document]:
        """
        重新排序 - 对召回结果进行重新排序
        对应 intent_recognition.py 中的融合排序功能
        """
        # 该方法在 intent_recognition.py 中有相关实现：
        # - weighted_reciprocal_rank_fusion (第480-512行)
        # 等待具体实现

    def compression(self, docs: List[Document], **kwargs) -> List[Document]:
        """
        压缩 - 对召回结果进行压缩
        对应 intent_recognition.py 中的LLM压缩功能
        """
        # 该方法在 intent_recognition.py 中有相关实现：
        # - llm_context_compressor (第656-690行)
        # - llm_context_compressor_parallel (第693-706行)
        # 等待具体实现

    def selection(self, docs: List[Document], **kwargs) -> List[Document]:
        """
        选择 - 对召回结果进行挑选
        对应 intent_recognition.py 中的相关性判断功能
        """
        # 该方法在 intent_recognition.py 中有相关实现：
        # - llm_relevance_determiner (第595-638行)
        # - llm_relevance_determiner_parallel (第641-653行)
        # - separate_docs_by_scores (第571-592行)
        # 等待具体实现

    def weighted_reciprocal_rank_fusion(self, searched_docs, weights, k=60):
        """
        对应 intent_recognition.py 第480-512行的 weighted_reciprocal_rank_fusion 方法
        加权倒数排名融合算法。

        参数:
        :param searched_docs: 一个列表，其中每个元素是一个包含文档的列表。
        :param weights: 一个列表，表示每个检索支路的权重。
        :param k: 一个整数，表示排名的最大考虑深度。

        返回:
        - 一个按照融合分数降序排序后的文档列表，每个文档的 `metadata` 字段中增加一个 `rrf_score` 字段。
          同时将 `__score__` 更新为最终融合分，原始召回分保存在 `retrieval_score`。
        """

        if len(searched_docs) != len(weights):
            raise ValueError("结果列表和权重列表的长度必须相同。")

        fusion_scores = defaultdict(float)
        doc_content = {}

        for result, weight in zip(searched_docs, weights):
            for rank, doc in enumerate(result):
                if rank < k:
                    doc_id = doc["metadata"]["uid"]
                    fusion_scores[doc_id] += weight / (rank + 1)
                    if doc_id not in doc_content:
                        doc_content[doc_id] = doc

        for doc_id, score in fusion_scores.items():
            metadata = doc_content[doc_id]["metadata"]
            if "__score__" in metadata and "retrieval_score" not in metadata:
                metadata["retrieval_score"] = metadata["__score__"]
            metadata["rrf_score"] = score
            metadata["__score__"] = score

        sorted_docs = sorted(doc_content.values(), key=lambda x: x["metadata"]["rrf_score"], reverse=True)

        return sorted_docs

    def calculate_fine_grained_scores(
        self,
        fine_grained_score_type,
        query_for_search,
        llm,
        context_docs_with_scores,
        knowledge_query_options: KnowledgeSettings,
        **kwargs,
    ):
        """
        对应 intent_recognition.py 第514-569行的 calculate_fine_grained_scores 方法
        """
        if fine_grained_score_type == FineGrainedScoreType.LLM:
            # NOTE: 如果 FineGrainedScoreType 为 LLM，则因为当前只有是/否相关的判断，因此分数只有 1.0 或 0.0
            fine_grained_scores = self.llm_relevance_determiner_parallel(
                (
                    kwargs.get("translated_query", query_for_search)
                    if knowledge_query_options.use_independent_query_in_scores
                    else kwargs["input"]
                ),
                [doc for doc, _ in context_docs_with_scores],
                llm,
                **kwargs,
            )
        elif fine_grained_score_type == FineGrainedScoreType.EXCLUSIVE_SIMILARITY_MODEL:
            # 使用专属小模型计算的分数作为最终的细粒度相似度分数
            # TODO: 目前知识类资源和工具类资源是独立使用小模型的，可以考虑在都要计算的情况下，合成一个batch进行计算
            # NOTE: 如果有 index_content 且是结构化数据则取 index_content，否则才取 page_content（兼容写法）。
            # 待知识库后台对非结构化数据的处理方式的 index_content 不是默认使用LLM总结后的内容之后，
            # 可将"且是结构化数据"的逻辑去除。
            # NOTE: 目前暂不考虑检索返回模板对 page_content 的影响
            fine_grained_scores = calculate_similarity(
                [
                    (
                        (
                            kwargs.get("translated_query", query_for_search)
                            if knowledge_query_options.use_independent_query_in_scores
                            else kwargs["input"]
                        ),
                        (
                            doc.metadata["index_content"]
                            if "index_content" in doc.metadata and is_structured_data(doc)
                            else doc.page_content
                        ),
                    )
                    for doc, _ in context_docs_with_scores
                ]
            )
            fine_grained_scores = [float(fine_grained_score) for fine_grained_score in fine_grained_scores]
        elif fine_grained_score_type == FineGrainedScoreType.EMBEDDING:
            # 直接使用emb分数作为最终的细粒度相似度分数
            fine_grained_scores = [float(emb_score) for _, emb_score in context_docs_with_scores]
        else:
            raise ValueError(
                f"当前仅支持以下计算细粒度相关分数的方式：{[score_type for score_type in FineGrainedScoreType]}，"
                f"但传入的 fine_grained_score_type 为：`{fine_grained_score_type}`"
            )

        return fine_grained_scores

    def separate_docs_by_scores(self, context_docs_with_scores, fine_grained_scores, reject_threshold):
        """
        对应 intent_recognition.py 第571-592行的 separate_docs_by_scores 方法
        """
        contexts_emb_recalled = []
        contexts_lowly_relevant = []
        contexts_moderately_relevant = []
        contexts_highly_relevant = []
        for context_doc_with_score, fine_grained_score in zip(context_docs_with_scores, fine_grained_scores):
            context_doc_with_fine_grained_score = copy.deepcopy(context_doc_with_score[0].dict())
            context_doc_with_fine_grained_score["metadata"]["fine_grained_score"] = fine_grained_score
            contexts_emb_recalled.append(context_doc_with_fine_grained_score)
            if fine_grained_score < reject_threshold[0]:
                contexts_lowly_relevant.append(context_doc_with_fine_grained_score)
            elif reject_threshold[0] <= fine_grained_score < reject_threshold[1]:
                contexts_moderately_relevant.append(context_doc_with_fine_grained_score)
            elif fine_grained_score >= reject_threshold[1]:
                contexts_highly_relevant.append(context_doc_with_fine_grained_score)

        return (
            contexts_emb_recalled,
            contexts_lowly_relevant,
            contexts_moderately_relevant,
            contexts_highly_relevant,
        )

    @retry(max_retries=5, max_seconds=3600)
    def llm_relevance_determiner(self, query, doc, llm, **kwargs):
        """
        对应 intent_recognition.py 第595-638行的 llm_relevance_determiner 方法
        """
        # 相比与 intent_recognition.py 的变化，用于处理 kwargs 没有 input 参数的情况
        if "input" not in kwargs:
            logger.warning("llm_relevance_determiner中的 kwargs 没有 input 参数")
            kwargs_input = query
        else:
            kwargs_input = kwargs["input"]

        # NOTE: 如果有 index_content 且是结构化数据则取 index_content，否则才取 page_content（兼容写法）。
        # 待知识库后台对非结构化数据的处理方式的 index_content 不是默认使用LLM总结后的内容之后，
        # 可将"且是结构化数据"的逻辑去除。
        # NOTE: 目前暂不考虑检索返回模板对 page_content 的影响
        if len(query) > len(kwargs_input) and query.endswith(f"\n{kwargs_input}"):  # 拼接场景
            his_sum = query[: -(len(kwargs_input) + 1)]
            sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_relevance_determiner_concate_sys_prompt_template"
            )
            usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_relevance_determiner_concate_usr_prompt_template"
            ).render(
                his_sum=his_sum,
                query=kwargs_input,
                doc=(
                    doc.metadata["index_content"]
                    if "index_content" in doc.metadata and is_structured_data(doc)
                    else doc.page_content
                ),
            )
        else:
            sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_relevance_determiner_sys_prompt_template"
            )
            usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_relevance_determiner_usr_prompt_template"
            ).render(
                query=query,
                doc=(
                    doc.metadata["index_content"]
                    if "index_content" in doc.metadata and is_structured_data(doc)
                    else doc.page_content
                ),
            )
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        # TODO: 待确认：并发请求内部无法 dispatch_custom_event，所以无需调用 conditional_dispatch_custom_event
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages)
        resp_content = resp.content
        return not resp_content.startswith("0")  # 用0来判断，减少误删

    @timeit(message="使用LLM并发进行query和召回文档相关性判断")
    def llm_relevance_determiner_parallel(self, query, fusion_docs, llm, **kwargs):
        """
        对应 intent_recognition.py 第641-653行的 llm_relevance_determiner_parallel 方法
        """
        try:
            futures = [
                knowledge_bk_executor.submit(self.llm_relevance_determiner, query, doc, llm, **kwargs)
                for doc in fusion_docs
            ]
            results = [1.0 if future.result() else 0.0 for future in futures]
        except Exception:
            # 如果 LLM 调用失败则不进行过滤
            results = [1.0] * len(fusion_docs)
            logger.warning("调用 LLM 来判断提问和知识相关性时失败，因此不进行过滤！")
        logger.info(f"=====> < llm_relevance_determiner_parallel 的结果>：{results}")
        return results

    @retry(max_retries=5, max_seconds=3600)
    def llm_context_compressor(self, provided_chat_history, query, candidate_context, llm, **kwargs):
        """
        对应 intent_recognition.py 第656-690行的 llm_context_compressor 方法
        """
        # 默认使用 specific 方式。
        compressor_type = kwargs.get("llm_context_compressor_type", "specific")
        if compressor_type == "common":
            sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_common_compressor_sys_prompt_template"
            )
            usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_common_compressor_usr_prompt_template"
            ).render(content=candidate_context)
        elif compressor_type == "specific":
            sys_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_context_compressor_sys_prompt_template"
            )
            usr_prompt = self.__class__.intent_recognition_prompt_templates.get(
                "llm_context_compressor_usr_prompt_template"
            ).render(
                provided_chat_history=provided_chat_history,
                query=query,
                candidate_context=candidate_context,
            )
        else:
            raise ValueError(f"不支持的知识库知识压缩方式：{compressor_type}")
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        # TODO: 待确认：并发请求内部无法 dispatch_custom_event，所以无需调用 conditional_dispatch_custom_event
        invoke_func = invoke_decorator(llm.invoke, llm)
        resp = invoke_func(messages)
        resp_content = resp.content
        # 如果触发了混元的特殊回复，则不进行压缩
        if resp_content == HUNYUAN_SPECIFIC_RESPONSE:
            resp_content = candidate_context
        return resp_content

    @timeit(message="使用LLM并发进行知识库内容压缩总结")
    def llm_context_compressor_parallel(self, provided_chat_history, query, context, llm, **kwargs):
        """
        对应 intent_recognition.py 第693-706行的 llm_context_compressor_parallel 方法
        """
        try:
            futures = [
                knowledge_bk_executor.submit(
                    self.llm_context_compressor,
                    provided_chat_history,
                    query,
                    candidate_context,
                    llm,
                    **kwargs,
                )
                for candidate_context in context
            ]
            results = [future.result() for future in futures]
        except Exception:
            # 如果 LLM 调用失败则不进行总结
            results = context
            logger.warning("调用 LLM 来对知识库内容进行压缩总结时失败，因此不进行总结！")
        return results

    # ====================================================================================================
    # 默认实现
    # ====================================================================================================
    @timeit(message="知识库检索（self query方式，使用完整query）")
    @retry(max_retries=5, max_seconds=3600)
    def search_knowledge_self_query(self, query_for_search, llm, **kwargs):
        # TODO: 这里需要考虑是否将 self-query 模块接口化，然后这里就只通过接口的方式调用即可，方便本地调试
        # TODO: 以下为临时写法，用于串通整个流程
        # TODO: self_query_retriever是有可能执行失败的，需要retry机制，以及最终实在失败了的处理机制
        # NOTE NOTE NOTE NOTE NOTE TODO:
        # 后续步骤LLM判断可回答性的prompt还得针对性优化，或者使用不同的prompt分支，因为对于召回的某一行，
        # 类似"成绩高于85分、18岁以上的学生有多少个"的提问LLM会觉得不可回答，
        # 类似"成绩高于85分、18岁以上的学生有哪些"的提问LLM会觉得可回答。
        # 这类求总数量的query确实会比较特殊，单条知识会导致LLM觉得不可回答，都返回了个0
        raise NotImplementedError

    def handle_knowledge_resources(
        self, recog_results_with_knowledge_resource_type: list, knowledge_query_options: KnowledgeSettings
    ):
        """
        在知识库召回知识以后进行标准处理
        由于 IntentRecognition 和 LangGraph 难以一同使用，因此将 IntentRecognitionMixin 的 knowledge_resources_postproc 进行了重构
        """
        # NOTE: 如果有 index_content 且是结构化数据则取 index_content，否则才取 page_content（兼容写法）。
        # 待知识库后台对非结构化数据的处理方式的 index_content 不是默认使用LLM总结后的内容之后，可将"且是结构化数据"的逻辑去除
        # NOTE: 目前暂不考虑检索返回模板对 page_content 的影响
        qa_response_kb_ids = knowledge_query_options.qa_response_kb_ids
        qa_set = set(qa_response_kb_ids)

        knowledge_base_ids = set()
        for doc in recog_results_with_knowledge_resource_type:
            if "knowledge_base_id" not in doc.get("metadata", {}):
                raise ValueError("Document metadata missing required field: knowledge_base_id")
            else:
                knowledge_base_ids.add(doc["metadata"]["knowledge_base_id"])
        state = {
            "knowledge_content": [
                (
                    doc["metadata"]["index_content"]
                    if "index_content" in doc["metadata"] and is_structured_data(doc)
                    else doc["page_content"]
                )
                for doc in recog_results_with_knowledge_resource_type
                if doc["metadata"]["knowledge_base_id"] not in qa_response_kb_ids
            ],
            "knowledge_qa_content": [
                (
                    doc["metadata"]["index_content"]
                    if "index_content" in doc["metadata"] and is_structured_data(doc)
                    else doc["page_content"]
                )
                for doc in recog_results_with_knowledge_resource_type
                if doc["metadata"]["knowledge_base_id"] in qa_response_kb_ids
            ],
            "with_qa_response": qa_set.issubset(knowledge_base_ids),
        }
        return state

    def retrieve(
        self, query: str, knowledge_query_options: KnowledgeSettings, chat_history: Optional[list] = None, **kwargs
    ) -> KnowledgeRagRetrieveResult:
        # 基本校验
        dispatch_rag_event_chunk("开始召回知识")
        if not any(
            [
                knowledge_query_options.with_index_specific_search,
                knowledge_query_options.with_index_specific_search_init,
                knowledge_query_options.with_index_specific_search_translation,
                knowledge_query_options.with_index_specific_search_keywords,
                knowledge_query_options.with_es_search_query,
                knowledge_query_options.with_es_search_keywords,
            ]
        ):
            raise RuntimeError("请至少选择一种召回方式！")

        # 获取基本配置信息
        # 获取原始输入，基于记忆系统，查询有时候会被重写
        raw_input = kwargs.get("input", query)
        # 获取 LLM 实例，如果没有提供，使用默认的 LLM
        llm = kwargs.get("llm", self.llm)
        # 获取知识库配置信息, 如果没有提供，使用配置中的知识库配置
        knowledge_items = kwargs.get("knowledge_items", knowledge_query_options.knowledge_items)
        knowledge_bases = kwargs.get("knowledge_bases", knowledge_query_options.knowledge_bases)
        # 初始化知识库操作实例，如果没有提供，使用默认的实例
        kb_retriever = kwargs.get("kb_retriever", self.kb_retriever)
        output_state = {}
        # 过滤chat_history中的消息，只保留HumanMessage和AIMessage类型的消息
        chat_history = [msg for msg in (chat_history or []) if isinstance(msg, (HumanMessage, AIMessage))]
        res = raw_input
        if knowledge_query_options.independent_query_mode == IndependentQueryMode.REWRITE:
            res = self.query_cls_pipeline(chat_history, query, llm, knowledge_query_options, **kwargs)
        elif knowledge_query_options.independent_query_mode == IndependentQueryMode.SUM_AND_CONCATE:
            sum_res = self.sum_chat_history_for_query(chat_history, query, llm, **kwargs)
            if sum_res:
                res = f"{sum_res}\n{query}"
        if isinstance(res, dict) and "decision" in res:
            return res
        query_for_search = normalize_query_for_search(res)
        # 并发执行多种召回策略
        futures = {}

        # 1. index_specific 召回
        if (knowledge_bases or knowledge_items) and knowledge_query_options.with_index_specific_search:
            futures["index_specific"] = knowledge_bk_executor.submit(
                kb_retriever.search_knowledge_index_specific,
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                query=query_for_search,
                topk=knowledge_query_options.knowledge_resource_rough_recall_topk,
                knowledge_query_options=knowledge_query_options,
                **kwargs,
            )

        # 2. 原始查询召回（如果查询被重写过）
        if (knowledge_bases or knowledge_items) and (
            knowledge_query_options.with_index_specific_search_init and query_for_search != raw_input
        ):
            futures["index_specific_init"] = knowledge_bk_executor.submit(
                kb_retriever.search_knowledge_index_specific,
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                query=raw_input,
                topk=knowledge_query_options.knowledge_resource_rough_recall_topk,
                knowledge_query_options=knowledge_query_options,
                **kwargs,
            )

        # 3. 翻译查询召回
        if (knowledge_bases or knowledge_items) and knowledge_query_options.with_index_specific_search_translation:
            # 先执行查询翻译
            translated_query_future = knowledge_bk_executor.submit(
                self.query_translation,
                query=(query_for_search if knowledge_query_options.use_independent_query_in_translation else raw_input),
                llm=llm,
                **kwargs,
            )
            translated_query = translated_query_future.result()
            futures["index_specific_translation"] = knowledge_bk_executor.submit(
                kb_retriever.search_knowledge_index_specific_translation,
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                translated_query=translated_query,
                topk=knowledge_query_options.knowledge_resource_rough_recall_topk,
                knowledge_query_options=knowledge_query_options,
                **kwargs,
            )
            # 如果配置了在评分中使用翻译查询
            if knowledge_query_options.use_translated_query_in_scores and translated_query:
                output_state["translated_query"] = translated_query

        # 4. 关键词召回
        if (knowledge_bases or knowledge_items) and knowledge_query_options.with_index_specific_search_keywords:
            # 先提取关键词
            extracted_keywords_future = knowledge_bk_executor.submit(
                self.extract_query_keywords,
                query=query_for_search,
                llm=llm,
                **kwargs,
            )
            extracted_keywords = extracted_keywords_future.result()
            futures["index_specific_keywords"] = knowledge_bk_executor.submit(
                kb_retriever.search_knowledge_index_specific_keywords,
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                extracted_keywords=extracted_keywords,
                topk=knowledge_query_options.knowledge_resource_rough_recall_topk,
                knowledge_query_options=knowledge_query_options,
                **kwargs,
            )

        # 5. QA响应知识库召回
        if knowledge_query_options.qa_response_knowledge_bases:
            futures["qa_response"] = knowledge_bk_executor.submit(
                kb_retriever.search_knowledge_index_specific,
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_query_options.qa_response_knowledge_bases,
                query=query_for_search,
                topk=knowledge_query_options.knowledge_resource_rough_recall_topk,
                knowledge_query_options=knowledge_query_options,
                **kwargs,
            )

        # 6. nature方式召回（将被废弃）
        if (knowledge_bases or knowledge_items) and knowledge_query_options.with_structured_data:
            futures["nature"] = knowledge_bk_executor.submit(
                kb_retriever.search_knowledge_nature,
                knowledge_items=knowledge_items,
                knowledge_bases=knowledge_bases,
                query=query_for_search,
                topk=knowledge_query_options.knowledge_resource_rough_recall_topk,
                **kwargs,
            )

        # 收集所有召回结果
        retrieved_results = {key: future.result() for key, future in futures.items()}
        dispatch_rag_event_chunk("重排召回结果中")

        # 获取各种召回结果
        retrieved_results_index_specific = retrieved_results.get("index_specific", [])
        retrieved_results_qa_response = retrieved_results.get("qa_response", [])
        retrieved_results_index_specific_init = retrieved_results.get("index_specific_init", [])
        retrieved_results_index_specific_translation = retrieved_results.get("index_specific_translation", [])
        retrieved_results_index_specific_keywords = retrieved_results.get("index_specific_keywords", [])
        retrieved_results_nature = retrieved_results.get("nature", [])

        # 结果融合
        if knowledge_query_options.with_rrf:
            # 使用加权倒数排名融合
            sources = [
                retrieved_results_index_specific,
                retrieved_results_qa_response,
                retrieved_results_index_specific_init,
                retrieved_results_index_specific_translation,
                retrieved_results_index_specific_keywords,
                retrieved_results_nature,
            ]
            fusion_docs = self.weighted_reciprocal_rank_fusion(
                sources,
                weights=[1.0 / len(sources)] * len(sources),
            )
        else:
            # 简单合并并按分数排序
            fusion_docs = sorted(
                deduplicate_knowledge_chunks(
                    retrieved_results_index_specific
                    + retrieved_results_qa_response
                    + retrieved_results_index_specific_init
                    + retrieved_results_index_specific_translation
                    + retrieved_results_index_specific_keywords
                    + retrieved_results_nature
                ),
                key=lambda x: x.get("metadata", {}).get("__score__", 0.0),
                reverse=True,
            )
        # TODO: 这里也可以考虑先使用 rerank 小模型排个序再取 self_query_threshold_top_n 文档来判断 query 是否涉及结构化数据
        # TODO: 待去除 nature 分支后即可正式走以下流程：
        if knowledge_query_options.with_structured_data and any(
            [is_structured_data(doc) for doc in fusion_docs[: knowledge_query_options.self_query_threshold_top_n]]
        ):
            # 在这种情况下需要使用 self-query 模块进行 2 次召回
            re_retrieved_res = self.search_knowledge_self_query(query_for_search, llm, **kwargs)
            fusion_docs.extend(re_retrieved_res)

        # 转换为Document对象并计算细粒度分数
        context_docs_with_scores = [
            (Document(**item), item.get("metadata", {}).get("__score__", 0.0)) for item in fusion_docs
        ]

        fine_grained_scores = self.calculate_fine_grained_scores(
            knowledge_query_options.knowledge_resource_fine_grained_score_type,
            query_for_search,
            llm,
            context_docs_with_scores,
            knowledge_query_options,
            **kwargs,
        )

        # 根据分数分类文档
        (
            knowledge_resources_emb_recalled,
            knowledge_resources_lowly_relevant,
            knowledge_resources_moderately_relevant,
            knowledge_resources_highly_relevant,
        ) = self.separate_docs_by_scores(
            context_docs_with_scores,
            fine_grained_scores,
            knowledge_query_options.knowledge_resource_reject_threshold,
        )

        # 决策逻辑
        if (not knowledge_resources_emb_recalled) or (
            len(knowledge_resources_lowly_relevant) == len(knowledge_resources_emb_recalled)
        ):
            decision = Decision.GENERAL_QA
        elif len(knowledge_resources_highly_relevant) > 0:
            # 如果没有绑定知识库 or 所有文档都是超低分，则直接进行无私域知识、无工具的通用回答
            decision = Decision.PRIVATE_QA
        else:
            # 其他情况：如果存在一些可能是 query【意图不明确】或【描述不清】导致的中间分相关文档，根据中分相关文档进行 query 重写
            decision = Decision.QUERY_CLARIFICATION

        # 根据决策类型处理知识资源
        if decision == Decision.PRIVATE_QA:
            # 私有知识问答:处理高相关性资源
            output_state.update(
                self.handle_knowledge_resources(
                    knowledge_resources_highly_relevant,
                    knowledge_query_options=knowledge_query_options,
                )
            )
            output_state["reference_doc"] = deduplicate_knowledge_file_paths(
                knowledge_resources_highly_relevant,
                sort_key=resolve_display_sort_key(knowledge_query_options.knowledge_resource_fine_grained_score_type),
            )
        elif decision == Decision.QUERY_CLARIFICATION:
            # 查询澄清:处理中等相关性资源
            output_state.update(
                self.handle_knowledge_resources(
                    knowledge_resources_moderately_relevant,
                    knowledge_query_options=knowledge_query_options,
                )
            )
            output_state["reference_doc"] = deduplicate_knowledge_file_paths(
                knowledge_resources_moderately_relevant,
                sort_key=resolve_display_sort_key(knowledge_query_options.knowledge_resource_fine_grained_score_type),
            )

        dispatch_rag_event_chunk("完成召回并分类")
        return KnowledgeRagRetrieveResult(
            decision=decision,
            knowledge_resources_highly_relevant=knowledge_resources_highly_relevant,
            knowledge_resources_moderately_relevant=knowledge_resources_moderately_relevant,
            knowledge_resources_lowly_relevant=knowledge_resources_lowly_relevant,
            knowledge_resources_emb_recalled=knowledge_resources_emb_recalled,
            **output_state,
        )
