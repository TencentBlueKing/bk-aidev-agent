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

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.enums import Decision, FineGrainedScoreType
from aidev_agent.packages.langchain_core.retrievers.kb_rag import KnowledgeRag
from aidev_agent.pydantic_models import KnowledgeSettings
from langchain_core.documents import Document


def create_mock_llm_response(content: str):
    """创建模拟的 LLM 响应"""
    mock_response = MagicMock()
    mock_response.content = content
    return mock_response


def create_knowledge_settings(
    with_index_specific_search: bool = True,
    with_rrf: bool = False,
    knowledge_resource_reject_threshold: tuple = (0.3, 0.7),
) -> KnowledgeSettings:
    """创建 KnowledgeSettings 配置"""
    return KnowledgeSettings(
        knowledge_bases=[],
        with_index_specific_search=with_index_specific_search,
        with_rrf=with_rrf,
        knowledge_resource_reject_threshold=knowledge_resource_reject_threshold,
    )


def create_multimodal_query(text: str = "蓝鲸是什么") -> list[dict]:
    """创建图文混合 query。"""
    return [
        {"type": "image_url", "image_url": {"url": "https://example.com/test.png"}},
        {"type": "text", "text": text},
    ]


def create_retrieval_doc(uid: str, score: float) -> dict:
    return {
        "page_content": uid,
        "metadata": {
            "uid": uid,
            "file_path": f"{uid}.md",
            "knowledge_base_id": 1,
            "__score__": score,
        },
    }


class TestKnowledgeRag:
    """KnowledgeRag 类的单元测试"""

    def test_init(self):
        """测试 __init__ 方法"""
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        rag = KnowledgeRag(llm=mock_llm, kb_retriever=mock_retriever)

        assert rag.llm == mock_llm
        assert rag.kb_retriever == mock_retriever

    def test_init_subclass(self):
        """测试 __init_subclass__ 方法 - 验证子类的 prompt 模板继承"""

        class CustomKnowledgeRag(KnowledgeRag):
            intent_recognition_prompt_templates = {"custom_key": "custom_value"}

        # 子类应该同时拥有父类和自己的模板
        assert "custom_key" in CustomKnowledgeRag.intent_recognition_prompt_templates
        # 父类的模板应该仍然存在
        assert "extract_query_keywords_sys_prompt_template" in CustomKnowledgeRag.intent_recognition_prompt_templates

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_extract_query_keywords(self, mock_invoke_decorator):
        """测试 extract_query_keywords 方法"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("关键词1\n关键词2\n关键词3"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.extract_query_keywords(query="什么是蓝鲸智云平台", llm=mock_llm)

        assert isinstance(result, list)
        assert len(result) == 3
        assert "关键词1" in result
        mock_invoke_func.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_query_translation(self, mock_invoke_decorator):
        """测试 query_translation 方法"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("蓝鲸智云平台"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.query_translation(query="blueking platform", llm=mock_llm)

        assert result == "蓝鲸智云平台"
        mock_invoke_func.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_query_translation_returns_none(self, mock_invoke_decorator):
        """测试 query_translation 方法 - 当输入为中文时返回 None"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("None"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.query_translation(query="蓝鲸智云平台", llm=mock_llm)

        assert result is None

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_query_rewrite_for_independence(self, mock_invoke_decorator, mock_dispatch):
        """测试 query_rewrite_for_independence 方法"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("手机号123也存在经常被无故停机的问题"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.query_rewrite_for_independence(
            chat_history="[HumanMessage(content='我的手机号xxx存在经常被无故停机的问题')]",
            query="手机号123也是",
            llm=mock_llm,
            display=False,
        )

        assert "手机号123也存在经常被无故停机的问题" in result
        mock_invoke_func.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_sum_chat_history_for_query(self, mock_invoke_decorator, mock_dispatch):
        """测试 sum_chat_history_for_query 方法"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("用户询问手机停机问题"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.sum_chat_history_for_query(
            chat_history="[HumanMessage(content='我的手机号经常被停机')]",
            query="为什么",
            llm=mock_llm,
        )

        assert result == "用户询问手机停机问题"

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_sum_chat_history_for_query_empty_history(self, mock_invoke_decorator, mock_dispatch):
        """测试 sum_chat_history_for_query 方法 - 空历史记录"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)

        result = rag.sum_chat_history_for_query(chat_history="", query="什么是蓝鲸", llm=mock_llm)

        assert result is None
        mock_invoke_decorator.assert_not_called()

    def test_weighted_reciprocal_rank_fusion(self):
        """测试 weighted_reciprocal_rank_fusion 方法"""
        rag = KnowledgeRag()

        searched_docs = [
            [
                {"metadata": {"uid": "doc1", "__score__": 0.1}, "page_content": "content1"},
                {"metadata": {"uid": "doc2", "__score__": 0.2}, "page_content": "content2"},
            ],
            [
                {"metadata": {"uid": "doc2", "__score__": 0.3}, "page_content": "content2"},
                {"metadata": {"uid": "doc3", "__score__": 0.4}, "page_content": "content3"},
            ],
        ]
        weights = [0.5, 0.5]

        result = rag.weighted_reciprocal_rank_fusion(searched_docs, weights, k=60)

        assert isinstance(result, list)
        assert len(result) == 3
        # doc2 出现在两个列表中，分数应该最高
        assert result[0]["metadata"]["uid"] == "doc2"
        # 验证 rrf_score 被添加到 metadata
        for doc in result:
            assert "rrf_score" in doc["metadata"]
            assert doc["metadata"]["__score__"] == doc["metadata"]["rrf_score"]
            assert "retrieval_score" in doc["metadata"]

    def test_weighted_reciprocal_rank_fusion_uses_rrf_score_as_final_score(self):
        """RRF 后的最终分应覆盖单路召回分，避免 EMBEDDING 二次排序翻转。"""
        rag = KnowledgeRag()
        searched_docs = [
            [
                {"metadata": {"uid": "154140716", "__score__": 0.882688969373703}, "page_content": "154140716"},
                {"metadata": {"uid": "154140719", "__score__": 0.8799408078193665}, "page_content": "154140719"},
            ],
            [
                {"metadata": {"uid": "154140719", "__score__": 0.8966792523860931}, "page_content": "154140719"},
                {"metadata": {"uid": "154140716", "__score__": 0.8952388763427734}, "page_content": "154140716"},
            ],
        ]

        result = rag.weighted_reciprocal_rank_fusion(searched_docs, weights=[0.2, 0.8])

        assert [doc["metadata"]["uid"] for doc in result[:2]] == ["154140719", "154140716"]
        assert result[0]["metadata"]["retrieval_score"] == 0.8799408078193665
        assert result[0]["metadata"]["__score__"] == result[0]["metadata"]["rrf_score"]
        assert result[0]["metadata"]["__score__"] > result[1]["metadata"]["__score__"]

    def test_weighted_reciprocal_rank_fusion_mismatched_lengths(self):
        """测试 weighted_reciprocal_rank_fusion 方法 - 结果列表和权重列表长度不匹配"""
        rag = KnowledgeRag()

        searched_docs = [[{"metadata": {"uid": "doc1"}, "page_content": "content1"}]]
        weights = [0.5, 0.5]

        with pytest.raises(ValueError, match="结果列表和权重列表的长度必须相同"):
            rag.weighted_reciprocal_rank_fusion(searched_docs, weights)

    def test_separate_docs_by_scores(self):
        """测试 separate_docs_by_scores 方法"""
        rag = KnowledgeRag()

        doc1 = Document(page_content="content1", metadata={"uid": "1"})
        doc2 = Document(page_content="content2", metadata={"uid": "2"})
        doc3 = Document(page_content="content3", metadata={"uid": "3"})

        context_docs_with_scores = [(doc1, 0.9), (doc2, 0.5), (doc3, 0.1)]
        fine_grained_scores = [0.9, 0.5, 0.1]
        reject_threshold = (0.3, 0.7)

        (
            contexts_emb_recalled,
            contexts_lowly_relevant,
            contexts_moderately_relevant,
            contexts_highly_relevant,
        ) = rag.separate_docs_by_scores(context_docs_with_scores, fine_grained_scores, reject_threshold)

        assert len(contexts_emb_recalled) == 3
        assert len(contexts_lowly_relevant) == 1  # 分数 0.1 < 0.3
        assert len(contexts_moderately_relevant) == 1  # 0.3 <= 分数 0.5 < 0.7
        assert len(contexts_highly_relevant) == 1  # 分数 0.9 >= 0.7

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_llm_relevance_determiner(self, mock_invoke_decorator):
        """测试 llm_relevance_determiner 方法"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("1"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)
        doc = Document(page_content="蓝鲸是腾讯开发的运维平台", metadata={})

        result = rag.llm_relevance_determiner(query="什么是蓝鲸", doc=doc, llm=mock_llm, input="什么是蓝鲸")

        assert result is True

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.knowledge_bk_executor")
    def test_llm_relevance_determiner_parallel(self, mock_executor):
        """测试 llm_relevance_determiner_parallel 方法"""
        mock_llm = MagicMock()

        # 模拟 future 对象
        mock_future1 = MagicMock()
        mock_future1.result.return_value = True
        mock_future2 = MagicMock()
        mock_future2.result.return_value = False

        mock_executor.submit.side_effect = [mock_future1, mock_future2]

        rag = KnowledgeRag(llm=mock_llm)
        docs = [
            Document(page_content="content1", metadata={}),
            Document(page_content="content2", metadata={}),
        ]

        result = rag.llm_relevance_determiner_parallel(query="test query", fusion_docs=docs, llm=mock_llm)

        assert result == [1.0, 0.0]

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_llm_context_compressor(self, mock_invoke_decorator):
        """测试 llm_context_compressor 方法"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("压缩后的内容"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.llm_context_compressor(
            provided_chat_history="[]",
            query="什么是蓝鲸",
            candidate_context="蓝鲸是腾讯开发的运维平台，具有很多功能...",
            llm=mock_llm,
            llm_context_compressor_type="specific",
        )

        assert result == "压缩后的内容"

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_llm_context_compressor_invalid_type(self, mock_invoke_decorator):
        """测试 llm_context_compressor 方法 - 不支持的压缩类型"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)

        with pytest.raises(ValueError, match="不支持的知识库知识压缩方式"):
            rag.llm_context_compressor(
                provided_chat_history="[]",
                query="test",
                candidate_context="content",
                llm=mock_llm,
                llm_context_compressor_type="invalid_type",
            )

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.knowledge_bk_executor")
    def test_llm_context_compressor_parallel(self, mock_executor):
        """测试 llm_context_compressor_parallel 方法"""
        mock_llm = MagicMock()

        mock_future1 = MagicMock()
        mock_future1.result.return_value = "压缩内容1"
        mock_future2 = MagicMock()
        mock_future2.result.return_value = "压缩内容2"

        mock_executor.submit.side_effect = [mock_future1, mock_future2]

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.llm_context_compressor_parallel(
            provided_chat_history="[]",
            query="test",
            context=["内容1", "内容2"],
            llm=mock_llm,
        )

        assert result == ["压缩内容1", "压缩内容2"]

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.calculate_similarity")
    def test_calculate_fine_grained_scores_embedding(self, mock_calculate_similarity):
        """EMBEDDING 使用 dense 原始分，而不是 RRF 融合分。"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)
        knowledge_settings = KnowledgeSettings(
            knowledge_resource_fine_grained_score_type=FineGrainedScoreType.EMBEDDING
        )

        doc = Document(page_content="test content", metadata={"retrieval_source": "vector", "retrieval_score": 0.85})
        context_docs_with_scores = [(doc, 0.2)]

        result = rag.calculate_fine_grained_scores(
            fine_grained_score_type=FineGrainedScoreType.EMBEDDING,
            query_for_search="test query",
            llm=mock_llm,
            context_docs_with_scores=context_docs_with_scores,
            knowledge_query_options=knowledge_settings,
            input="test query",
        )

        assert result == [0.85]
        assert doc.metadata["dense_score"] == 0.85
        mock_calculate_similarity.assert_not_called()

    def test_calculate_fine_grained_scores_embedding_rejects_sparse_score(self):
        rag = KnowledgeRag(llm=MagicMock())
        doc = Document(page_content="test content", metadata={"retrieval_source": "sparse"})

        with pytest.raises(ValueError, match="仅支持 dense 召回文档"):
            rag.calculate_fine_grained_scores(
                FineGrainedScoreType.EMBEDDING,
                "query",
                MagicMock(),
                [(doc, 3.981)],
                KnowledgeSettings(knowledge_resource_fine_grained_score_type=FineGrainedScoreType.EMBEDDING),
                input="query",
            )

    def test_calculate_fine_grained_scores_original_is_not_a_scoring_strategy(self):
        rag = KnowledgeRag(llm=MagicMock())

        with pytest.raises(ValueError, match="ORIGINAL 模式不计算细粒度分数"):
            rag.calculate_fine_grained_scores(
                FineGrainedScoreType.ORIGINAL,
                "query",
                MagicMock(),
                [],
                KnowledgeSettings(knowledge_resource_fine_grained_score_type=FineGrainedScoreType.ORIGINAL),
                input="query",
            )

    def test_calculate_fine_grained_scores_invalid_type(self):
        """测试 calculate_fine_grained_scores 方法 - 无效的类型"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)
        knowledge_settings = create_knowledge_settings()

        doc = Document(page_content="test content", metadata={})
        context_docs_with_scores = [(doc, 0.85)]

        with pytest.raises(ValueError, match="当前仅支持以下计算细粒度相关分数的方式"):
            rag.calculate_fine_grained_scores(
                fine_grained_score_type="INVALID_TYPE",
                query_for_search="test query",
                llm=mock_llm,
                context_docs_with_scores=context_docs_with_scores,
                knowledge_query_options=knowledge_settings,
                input="test query",
            )

    def test_handle_knowledge_resources(self):
        """测试 handle_knowledge_resources 方法"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)

        knowledge_settings = KnowledgeSettings(
            knowledge_bases=[],
            with_index_specific_search=True,
            with_rrf=False,
            knowledge_resource_reject_threshold=(0.3, 0.7),
            qa_response_kb_ids=[100],
        )

        # 新的方法签名直接接收文档列表
        docs_list = [
            {"page_content": "content1", "metadata": {"knowledge_base_id": 1}},
            {"page_content": "content2", "metadata": {"knowledge_base_id": 100}},
        ]

        result = rag.handle_knowledge_resources(
            recog_results_with_knowledge_resource_type=docs_list,
            knowledge_query_options=knowledge_settings,
        )

        assert "knowledge_content" in result
        assert "knowledge_qa_content" in result
        # knowledge_base_id=1 的不在 qa_response_kb_ids 中，应该在 knowledge_content
        assert len(result["knowledge_content"]) == 1
        # knowledge_base_id=100 在 qa_response_kb_ids 中，应该在 knowledge_qa_content
        assert len(result["knowledge_qa_content"]) == 1

    def test_handle_knowledge_resources_missing_knowledge_base_id(self):
        """测试 handle_knowledge_resources 方法 - 缺少 knowledge_base_id"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)
        knowledge_settings = KnowledgeSettings()

        # 新的方法签名直接接收文档列表
        docs_list = [
            {"page_content": "content1", "metadata": {}},
        ]

        with pytest.raises(ValueError, match="Document metadata missing required field: knowledge_base_id"):
            rag.handle_knowledge_resources(
                recog_results_with_knowledge_resource_type=docs_list,
                knowledge_query_options=knowledge_settings,
            )

    def test_search_knowledge_self_query_not_implemented(self):
        """测试 search_knowledge_self_query 方法 - 应抛出 NotImplementedError"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)

        with pytest.raises(NotImplementedError):
            rag.search_knowledge_self_query("test query", mock_llm)

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.dispatch_rag_event_chunk")
    def test_retrieve_no_recall_method_selected(self, mock_dispatch_rag_event):
        """测试 retrieve 方法 - 未选择任何召回方式"""
        mock_llm = MagicMock()
        rag = KnowledgeRag(llm=mock_llm)

        # 所有召回选项都为 False
        knowledge_settings = KnowledgeSettings(
            with_index_specific_search=False,
            with_index_specific_search_init=False,
            with_index_specific_search_translation=False,
            with_index_specific_search_keywords=False,
            with_es_search_query=False,
            with_es_search_keywords=False,
        )

        with pytest.raises(RuntimeError, match="请至少选择一种召回方式"):
            rag.retrieve(query="test query", knowledge_query_options=knowledge_settings)

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.dispatch_rag_event_chunk")
    def test_retrieve_normalizes_non_string_result_before_search(self, mock_dispatch_rag_event):
        """测试非字符串 res 会在召回前归一化为文本。"""
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.search_knowledge_index_specific.return_value = []
        rag = KnowledgeRag(llm=mock_llm, kb_retriever=mock_retriever)
        knowledge_settings = KnowledgeSettings(
            knowledge_items=[{"id": 1}],
            with_index_specific_search_init=False,
        )
        query = create_multimodal_query()

        result = rag.retrieve(
            query="蓝鲸是什么",
            knowledge_query_options=knowledge_settings,
            input=query,
        )

        assert result["decision"] == Decision.GENERAL_QA
        assert mock_retriever.search_knowledge_index_specific.call_args.kwargs["query"] == "蓝鲸是什么"

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.dispatch_rag_event_chunk")
    def test_retrieve_original_skips_scoring_rejection_and_secondary_sort(self, _mock_dispatch):
        mock_retriever = MagicMock()
        mock_retriever.search_knowledge_index_specific.return_value = [
            create_retrieval_doc("first", 0.8),
            create_retrieval_doc("second", 0.7),
        ]
        rag = KnowledgeRag(llm=MagicMock(), kb_retriever=mock_retriever)
        settings = KnowledgeSettings(
            knowledge_items=[{"id": 1}],
            with_index_specific_search_init=False,
            with_rrf=False,
            knowledge_resource_fine_grained_score_type=FineGrainedScoreType.ORIGINAL,
            knowledge_resource_reject_threshold=(0.99, 1.0),
        )

        with (
            patch.object(rag, "calculate_fine_grained_scores") as mock_calculate,
            patch.object(rag, "separate_docs_by_scores") as mock_separate,
        ):
            result = rag.retrieve("query", settings, input="query")

        mock_calculate.assert_not_called()
        mock_separate.assert_not_called()
        assert result["decision"] == Decision.PRIVATE_QA
        for relevance in ("lowly", "moderately"):
            assert not result[f"knowledge_resources_{relevance}_relevant"]
        expected_uids = ["first", "second"]
        assert [doc["metadata"]["uid"] for doc in result["knowledge_resources_highly_relevant"]] == expected_uids
        assert [doc["metadata"]["uid"] for doc in result["reference_doc"]] == expected_uids
        assert all("fine_grained_score" not in doc["metadata"] for doc in result["knowledge_resources_emb_recalled"])

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_latest_query_classification(self, mock_invoke_decorator, mock_dispatch):
        """测试 latest_query_classification 方法 - 返回 new"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("<<<<<new>>>>>"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.latest_query_classification(
            chat_history="[HumanMessage(content='云桌面黑屏处理方法')]",
            query="你好",
            llm=mock_llm,
        )

        assert result == "new"
        mock_invoke_decorator.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_latest_query_classification_continue(self, mock_invoke_decorator, mock_dispatch):
        """测试 latest_query_classification 方法 - 返回 continue"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("<<<<<continue>>>>>"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.latest_query_classification(
            chat_history="[HumanMessage(content='云桌面黑屏处理方法')]",
            query="那绿屏怎么解决",
            llm=mock_llm,
        )

        assert result == "continue"
        mock_invoke_decorator.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_latest_query_classification_finish(self, mock_invoke_decorator, mock_dispatch):
        """测试 latest_query_classification 方法 - 返回 finish"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("<<<<<finish>>>>>"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.latest_query_classification(
            chat_history="[HumanMessage(content='云桌面黑屏处理方法')]",
            query="谢谢",
            llm=mock_llm,
        )

        assert result == "finish"
        mock_invoke_decorator.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_query_cls_with_resp_or_rewrite(self, mock_invoke_decorator, mock_dispatch):
        """测试 query_cls_with_resp_or_rewrite 方法 - 返回 new"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(return_value=create_mock_llm_response("<<<<<new>>>>>"))
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.query_cls_with_resp_or_rewrite(
            chat_history="[HumanMessage(content='云桌面黑屏处理方法')]",
            query="你好",
            llm=mock_llm,
        )

        assert result == {"query_cls": "new"}
        mock_invoke_decorator.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_query_cls_with_resp_or_rewrite_continue(self, mock_invoke_decorator, mock_dispatch):
        """测试 query_cls_with_resp_or_rewrite 方法 - 返回 continue"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(
            return_value=create_mock_llm_response("<<<<<continue>>>>>$REWRITTEN_QUERY: 云桌面绿屏解决方法")
        )
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.query_cls_with_resp_or_rewrite(
            chat_history="[HumanMessage(content='云桌面黑屏处理方法')]",
            query="那绿屏怎么解决",
            llm=mock_llm,
        )

        assert result == {"query_cls": "continue", "rewritten_query": "云桌面绿屏解决方法"}
        mock_invoke_decorator.assert_called_once()

    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.conditional_dispatch_custom_event")
    @patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.invoke_decorator")
    def test_query_cls_with_resp_or_rewrite_finish(self, mock_invoke_decorator, mock_dispatch):
        """测试 query_cls_with_resp_or_rewrite 方法 - 返回 finish"""
        mock_llm = MagicMock()
        mock_invoke_func = MagicMock(
            return_value=create_mock_llm_response("<<<<<finish>>>>>$RESPONSE: 不客气！很高兴能帮到您。")
        )
        mock_invoke_decorator.return_value = mock_invoke_func

        rag = KnowledgeRag(llm=mock_llm)

        result = rag.query_cls_with_resp_or_rewrite(
            chat_history="[HumanMessage(content='云桌面黑屏处理方法')]",
            query="谢谢",
            llm=mock_llm,
        )

        assert result == {"query_cls": "finish", "response": "不客气！很高兴能帮到您。"}
        mock_invoke_decorator.assert_called_once()
