import logging
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage

from aidev_agent.packages.resource_manager.registry import resource_manager
from aidev_agent.pydantic_models import KnowledgeSettings

logger = logging.getLogger(__name__)


class BkRetriever:
    """Build and submit the SDK knowledge-query request to the WEB API."""

    @property
    def _query_instance(self) -> Callable:
        return resource_manager().knowledge_query

    def query_knowledge(
        self,
        query: str,
        knowledge_query_options: KnowledgeSettings,
        chat_history: list | None = None,
        *,
        llm_code: str | None = None,
    ) -> dict:
        """Submit one complete knowledge query and return the API result unchanged."""

        query_payload = self._build_query_payload(query, knowledge_query_options, chat_history or [], llm_code)
        logger.info("查询知识库： %s", query_payload)
        response = self._query_instance(query_payload)
        self._validate_documents(response["documents"])
        return response

    def _build_query_payload(
        self,
        query: str,
        knowledge_query_options: KnowledgeSettings,
        chat_history: list,
        llm_code: str | None,
    ) -> dict:
        knowledge_base_ids = self._knowledge_ids(knowledge_query_options.knowledge_bases)
        qa_knowledge_base_ids = list(
            dict.fromkeys(
                [
                    *knowledge_query_options.qa_response_kb_ids,
                    *self._knowledge_ids(knowledge_query_options.qa_response_knowledge_bases),
                ]
            )
        )
        query_payload = {
            "query": query,
            "type": "nature",
            "raw": False,
            "knowledge_base_id": list(dict.fromkeys([*knowledge_base_ids, *qa_knowledge_base_ids])),
            "qa_response_knowledge_base_id": qa_knowledge_base_ids,
            "knowledge_id": self._knowledge_ids(knowledge_query_options.knowledge_items),
            "topk": knowledge_query_options.knowledge_resource_rough_recall_topk,
            "document_fragment_count": knowledge_query_options.knowledge_resource_rough_recall_topk,
            "independent_query_mode": knowledge_query_options.independent_query_mode.value,
            "chat_history": self._serialize_chat_history(chat_history),
            "with_scalar_data": knowledge_query_options.with_scalar_data,
            "use_rerank": True,
            "rrf_weights": knowledge_query_options.rrf_weights,
            "knowledge_resource_fine_grained_score_type": (
                knowledge_query_options.knowledge_resource_fine_grained_score_type.value
            ),
            "knowledge_resource_reject_threshold": list(knowledge_query_options.knowledge_resource_reject_threshold),
            "rejection_message": knowledge_query_options.rejection_message,
            "is_response_when_no_knowledgebase_match": (
                knowledge_query_options.is_response_when_no_knowledgebase_match
            ),
        }
        if knowledge_query_options.knowledge_template_id is not None:
            query_payload["knowledge_template_id"] = knowledge_query_options.knowledge_template_id
        if knowledge_query_options.recall_channels is not None:
            query_payload["recall_channels"] = list(knowledge_query_options.recall_channels)
        if knowledge_query_options.scalar_expression:
            query_payload["filter"] = {"scalar": [{"expression": knowledge_query_options.scalar_expression}]}
        if llm_code:
            query_payload["llm_code"] = llm_code
        return query_payload

    @staticmethod
    def _knowledge_ids(knowledge_resources: list[dict]) -> list[int]:
        return list(dict.fromkeys(resource["id"] for resource in knowledge_resources if resource.get("id")))

    @staticmethod
    def _serialize_chat_history(chat_history: list) -> list[dict[str, str]]:
        serialized_messages = []
        for message in chat_history:
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                continue
            serialized_messages.append({"role": role, "content": str(message.content)})
        return serialized_messages

    @staticmethod
    def _validate_documents(documents: list[dict]) -> None:
        for document in documents:
            if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
                raise RuntimeError(f"召回文档格式有误！\n文档内容为：{document}\n")
            if "__score__" not in document["metadata"]:
                raise RuntimeError(f"召回的文档缺少 __score__ 字段！\n文档内容为：{document}\n")
