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

from pydantic import PrivateAttr

from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import KnowledgeSettings

TEST_QUERY_VALUE = "errorcode是154140719"
KNOWLEDGE_BASE_ID = 305
KNOWLEDGE_BASE_WITHOUT_INDEX_TYPE_ID = 306
FULL_TEXT_INDEX_NAME = "full_text"
QA_INDEX_NAME = "qa"
FULL_TEXT_INDEX_TYPE = "vector-full_text"
QA_INDEX_TYPE = "vector-multi_column"


class CapturingBkRetriever(BkRetriever):
    _query_data: dict | None = PrivateAttr(default=None)

    @property
    def query_data(self) -> dict | None:
        return self._query_data

    @property
    def _query_instance(self):
        def query(data: dict) -> dict:
            self._query_data = data
            return {"documents": []}

        return query


def _knowledge_base_with_full_text_and_qa_index() -> dict:
    return {
        "id": KNOWLEDGE_BASE_ID,
        "index_config": {
            "full_text_indexes": [{"index_name": FULL_TEXT_INDEX_NAME, "index_type": FULL_TEXT_INDEX_TYPE}],
            "vector_indexes": [{"index_name": QA_INDEX_NAME, "index_type": QA_INDEX_TYPE}],
        },
    }


def _knowledge_base_without_index_type() -> dict:
    return {
        "id": KNOWLEDGE_BASE_WITHOUT_INDEX_TYPE_ID,
        "index_config": {
            "full_text_indexes": [{"index_name": FULL_TEXT_INDEX_NAME}],
            "vector_indexes": [{"index_name": QA_INDEX_NAME}],
        },
    }


def test_construct_index_query_kwargs_preserves_index_type() -> None:
    index_query_kwargs = []
    BkRetriever()._construct_index_query_kwargs(
        index_query_kwargs=index_query_kwargs,
        query=TEST_QUERY_VALUE,
        knowledges=[_knowledge_base_with_full_text_and_qa_index()],
        knowledge_type="knowledge_bases",
        resource_type="knowledge",
    )

    assert index_query_kwargs == [
        {
            "index_name": FULL_TEXT_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_ID,
            "index_type": FULL_TEXT_INDEX_TYPE,
        },
        {
            "index_name": QA_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_ID,
            "index_type": QA_INDEX_TYPE,
        },
    ]


def test_construct_index_query_kwargs_defaults_index_type_by_index_group() -> None:
    index_query_kwargs = []
    BkRetriever()._construct_index_query_kwargs(
        index_query_kwargs=index_query_kwargs,
        query=TEST_QUERY_VALUE,
        knowledges=[_knowledge_base_without_index_type()],
        knowledge_type="knowledge_bases",
        resource_type="knowledge",
    )

    assert index_query_kwargs == [
        {
            "index_name": FULL_TEXT_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_WITHOUT_INDEX_TYPE_ID,
            "index_type": FULL_TEXT_INDEX_TYPE,
        },
        {
            "index_name": QA_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_WITHOUT_INDEX_TYPE_ID,
            "index_type": QA_INDEX_TYPE,
        },
    ]


def test_construct_index_query_kwargs_keeps_index_type_for_custom_index_names() -> None:
    index_query_kwargs = []
    BkRetriever()._construct_index_query_kwargs(
        index_query_kwargs=index_query_kwargs,
        query=TEST_QUERY_VALUE,
        knowledges=[_knowledge_base_with_full_text_and_qa_index()],
        knowledge_type="knowledge_bases",
        resource_type="knowledge",
        knowledge_resource_index_names={"knowledge_bases": {KNOWLEDGE_BASE_ID: [QA_INDEX_NAME]}},
    )

    assert index_query_kwargs == [
        {
            "index_name": QA_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_ID,
            "index_type": QA_INDEX_TYPE,
        }
    ]


def test_search_knowledge_index_specific_sends_index_type_to_resource_query() -> None:
    retriever = CapturingBkRetriever()
    retriever.search_knowledge_index_specific(
        knowledge_items=[],
        knowledge_bases=[_knowledge_base_with_full_text_and_qa_index()],
        query=TEST_QUERY_VALUE,
        topk=10,
        knowledge_query_options=KnowledgeSettings(knowledge_bases=[]),
    )

    assert retriever.query_data["index_query_kwargs"] == [
        {
            "index_name": FULL_TEXT_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_ID,
            "index_type": FULL_TEXT_INDEX_TYPE,
        },
        {
            "index_name": QA_INDEX_NAME,
            "index_value": TEST_QUERY_VALUE,
            "knowledge_base_id": KNOWLEDGE_BASE_ID,
            "index_type": QA_INDEX_TYPE,
        },
    ]
