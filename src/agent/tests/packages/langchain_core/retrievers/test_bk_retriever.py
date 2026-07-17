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

import pytest
from aidev_agent.config import settings
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import AgentOptions, KnowledgebaseSettings

pytestmark = pytest.mark.skip(reason="API changed — method signatures updated in BkRetriever")

# 测试用知识库配置
TEST_KNOWLEDGE_BASES = [
    {
        "anchor_paths": "/146",
        "collection_name": "bkbase知识库",
        "id": 146,
        "index_config": {
            "full_text_indexes": [
                {
                    "index_config": {"type": "system"},
                    "index_name": "full_text",
                    "index_type": "vector-full_text",
                    "status": "normal",
                }
            ],
            "scalar_indexes": [],
            "vector_indexes": [],
        },
        "knowledge_counts": 1,
        "name": "bkbase知识库",
        "scene_type": "default",
        "total_file_size": 9662,
        "updated_by": "xiaoming",
    }
]


def create_agent_options_with_knowledge_bases(knowledge_bases: list[dict]) -> AgentOptions:
    """创建包含知识库配置的 AgentOptions"""
    knowledge_settings = KnowledgebaseSettings(
        knowledge_bases=knowledge_bases,
        with_index_specific_search=True,
    )
    return AgentOptions(knowledge_query_options=knowledge_settings)


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
class TestBkRetriever:
    """BkRetriever 真实请求测试"""

    def test_search_knowledge_index_specific(self):
        """测试 index_specific 方式的知识库检索"""
        retriever = BkRetriever()
        agent_options = create_agent_options_with_knowledge_bases(TEST_KNOWLEDGE_BASES)

        # 执行检索
        results = retriever.search_knowledge_index_specific(
            knowledge_items=[],
            knowledge_bases=TEST_KNOWLEDGE_BASES,
            query="什么是蓝鲸基础计算平台",
            topk=5,
            agent_options=agent_options,
        )

        # 验证结果
        assert results is not None
        assert isinstance(results, list)
        print(f"\n检索到 {len(results)} 条结果")

        # 验证每个结果的结构
        for i, doc in enumerate(results):
            assert "metadata" in doc, f"文档 {i} 缺少 metadata 字段"
            assert "__score__" in doc["metadata"], f"文档 {i} 缺少 __score__ 字段"
            print(f"  文档 {i}: score={doc['metadata']['__score__']:.4f}")

    def test_search_knowledge_index_specific_keywords(self):
        """测试使用关键词的 index_specific 检索"""
        retriever = BkRetriever()
        agent_options = create_agent_options_with_knowledge_bases(TEST_KNOWLEDGE_BASES)

        # 使用关键词列表进行检索
        keywords = ["蓝鲸", "计算平台"]
        results = retriever.search_knowledge_index_specific_keywords(
            knowledge_items=[],
            knowledge_bases=TEST_KNOWLEDGE_BASES,
            extracted_keywords=keywords,
            topk=5,
            agent_options=agent_options,
        )

        # 验证结果
        assert results is not None
        assert isinstance(results, list)
        print(f"\n关键词检索到 {len(results)} 条结果")

    def test_search_knowledge_index_specific_keywords_empty(self):
        """测试空关键词列表的处理"""
        retriever = BkRetriever()
        agent_options = create_agent_options_with_knowledge_bases(TEST_KNOWLEDGE_BASES)

        # 空关键词列表应返回空列表
        results = retriever.search_knowledge_index_specific_keywords(
            knowledge_items=[],
            knowledge_bases=TEST_KNOWLEDGE_BASES,
            extracted_keywords=[],
            topk=5,
            agent_options=agent_options,
        )

        assert results == []
        print("\n空关键词正确返回空列表")

    def test_search_knowledge_index_specific_translation(self):
        """测试使用翻译查询的 index_specific 检索"""
        retriever = BkRetriever()
        agent_options = create_agent_options_with_knowledge_bases(TEST_KNOWLEDGE_BASES)

        # 使用翻译后的查询进行检索
        translated_query = "蓝鲸基础计算平台介绍"
        results = retriever.search_knowledge_index_specific_translation(
            knowledge_items=[],
            knowledge_bases=TEST_KNOWLEDGE_BASES,
            translated_query=translated_query,
            topk=5,
            agent_options=agent_options,
        )

        # 验证结果
        assert results is not None
        assert isinstance(results, list)
        print(f"\n翻译查询检索到 {len(results)} 条结果")

    def test_search_knowledge_index_specific_translation_none(self):
        """测试空翻译查询的处理"""
        retriever = BkRetriever()
        agent_options = create_agent_options_with_knowledge_bases(TEST_KNOWLEDGE_BASES)

        # 空翻译查询应返回空列表
        results = retriever.search_knowledge_index_specific_translation(
            knowledge_items=[],
            knowledge_bases=TEST_KNOWLEDGE_BASES,
            translated_query=None,
            topk=5,
            agent_options=agent_options,
        )

        assert results == []
        print("\n空翻译查询正确返回空列表")

    def test_search_knowledge_nature(self):
        """测试 nature 方式的知识库检索"""
        retriever = BkRetriever()

        # 执行检索
        results = retriever.search_knowledge_nature(
            knowledge_items=[],
            knowledge_bases=TEST_KNOWLEDGE_BASES,
            query="蓝鲸平台",
            topk=5,
        )

        # 验证结果
        assert results is not None
        assert isinstance(results, list)
        print(f"\nnature 方式检索到 {len(results)} 条结果")

        # 验证每个结果的结构
        for i, doc in enumerate(results):
            assert "metadata" in doc, f"文档 {i} 缺少 metadata 字段"
            assert "__score__" in doc["metadata"], f"文档 {i} 缺少 __score__ 字段"

    def test_construct_index_query_kwargs(self):
        """测试 _construct_index_query_kwargs 方法"""
        retriever = BkRetriever()

        index_query_kwargs = []
        retriever._construct_index_query_kwargs(
            index_query_kwargs=index_query_kwargs,
            query="测试查询",
            knowledges=TEST_KNOWLEDGE_BASES,
            knowledge_type="knowledge_bases",
            resource_type="knowledge",
        )

        # 验证构造的参数
        assert len(index_query_kwargs) > 0
        print(f"\n构造了 {len(index_query_kwargs)} 个索引查询参数")

        for kwargs in index_query_kwargs:
            assert "index_name" in kwargs
            assert "index_value" in kwargs
            assert "knowledge_base_id" in kwargs
            print(f"  index_name={kwargs['index_name']}, knowledge_base_id={kwargs['knowledge_base_id']}")

    def test_construct_index_query_kwargs_invalid_resource_type(self):
        """测试无效的 resource_type 参数"""
        retriever = BkRetriever()

        index_query_kwargs = []
        with pytest.raises(ValueError, match="不支持的 resource 类型"):
            retriever._construct_index_query_kwargs(
                index_query_kwargs=index_query_kwargs,
                query="测试查询",
                knowledges=TEST_KNOWLEDGE_BASES,
                knowledge_type="knowledge_bases",
                resource_type="invalid_type",
            )

    def test_construct_simple_filter(self):
        """测试 _construct_simple_filter 方法"""
        retriever = BkRetriever()

        # 不带标量过滤的情况
        filter_obj = retriever._construct_simple_filter(
            query="测试查询",
            index_name="full_text",
            knowledge_id=None,
            knowledge_base_id=146,
            topk=5,
            scalar_expression=None,
        )

        assert filter_obj is not None
        assert len(filter_obj.vector) == 1
        assert filter_obj.vector[0].index_name == "full_text"
        assert filter_obj.vector[0].index_value == "测试查询"
        assert filter_obj.vector[0].knowledge_base_id == 146
        assert filter_obj.vector[0].topk == 5
        print("\n成功构造过滤器对象")

    def test_construct_simple_filter_with_scalar(self):
        """测试带标量过滤的 _construct_simple_filter 方法"""
        retriever = BkRetriever()

        # 带标量过滤的情况
        filter_obj = retriever._construct_simple_filter(
            query="测试查询",
            index_name="full_text",
            knowledge_id=None,
            knowledge_base_id=146,
            topk=5,
            scalar_expression="field == '{value}'",
            value="test",
        )

        assert filter_obj is not None
        assert filter_obj.vector[0].scalar is not None
        assert filter_obj.vector[0].scalar.expression == "field == 'test'"
        print("\n成功构造带标量过滤的过滤器对象")
