from typing import Any, List, Tuple

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.packages.langchain_core.models.utils import is_deepseek_r1_series_models, remove_thinking_process
from aidev_agent.packages.model_management.registry import RegistryPluginMixIn
from aidev_agent.utils.decorator import timeit

HUNYUAN_SPECIFIC_RESPONSE = "很抱歉，我还未学习到如何回答这个问题的内容，暂时无法提供相关信息。"
reg = RegistryPluginMixIn()


def normalize_query_for_search(query: Any) -> str:
    """将多模态 content 归一化为知识库可检索文本。"""
    if query is None:
        return ""
    if isinstance(query, str):
        return query
    if isinstance(query, list):
        text_parts = []
        for item in query:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type")
                text = item.get("text") or item.get("content")
                if (
                    item_type == "text"
                    and isinstance(text, str)
                    or item_type not in {"image_url", "input_image"}
                    and isinstance(text, str)
                ):
                    text_parts.append(text)
        return "\n".join(part for part in text_parts if part.strip())
    return str(query)


def is_structured_data(doc):
    structured_data_file_types = ["csv", "xlsx"]
    if isinstance(doc, Document):
        if not hasattr(doc, "metadata"):
            raise RuntimeError(f"召回的文档没有metadata属性！\n文档格式为 Document\n文档内容为：{doc}\n")
        return "file_type" in doc.metadata and doc.metadata["file_type"] in structured_data_file_types
    elif isinstance(doc, dict):
        if "metadata" not in doc:
            raise RuntimeError(f"召回的文档没有metadata属性！\n文档格式为 dict\n文档内容为：{doc}\n")
        return "file_type" in doc["metadata"] and doc["metadata"]["file_type"] in structured_data_file_types
    else:
        raise RuntimeError(f"不支持的文档格式！\n文档内容为：{doc}\n")


def deduplicate_knowledge_chunks(knowledge_chunks):
    return list({item["metadata"]["uid"]: item for item in knowledge_chunks}.values())


def resolve_display_sort_key(fine_grained_score_type) -> str:
    """确定展示排序使用的分数字段。

    - EMBEDDING（「保留原始顺序」）：按 ``rrf_score`` 排序，尊重资源侧多路 RRF 融合顺序
      （已含 BM25 词法通道），不被各通道原始 ``fine_grained_score``（emb/bm25 量纲不一）打乱；
    - LLM / EXCLUSIVE_SIMILARITY_MODEL：仍按 ``fine_grained_score`` 重排（这两种本就是重排语义）。

    注意：拒答分级用的仍是 ``fine_grained_score``（见 ``separate_docs_by_scores``），此处只改
    展示排序键，不影响拒答阈值判定。
    """

    if str(getattr(fine_grained_score_type, "value", fine_grained_score_type)) == "EMBEDDING":
        return "rrf_score"
    return "fine_grained_score"


def _sort_score(item, sort_key: str) -> float:
    """取排序分：优先 sort_key，缺失时回退 fine_grained_score，保证无回归。"""
    metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
    if sort_key in metadata:
        return metadata.get(sort_key) or 0
    return metadata.get("fine_grained_score", 0) or 0


def deduplicate_knowledge_file_paths(knowledge_chunks, sort_key: str = "fine_grained_score"):
    """按照 file path 进行去重，且只保留 metadata，且按照指定分数（默认 fine_grained_score）降序排序"""
    unique_items = list(
        {item["metadata"]["file_path"]: {"metadata": item["metadata"]} for item in knowledge_chunks}.values()
    )
    return sorted(unique_items, key=lambda x: _sort_score(x, sort_key), reverse=True)


def filter_and_select_topk(items, score_threshold, topk, sort_key: str = "fine_grained_score"):
    if score_threshold:
        filtered_items = [
            item for item in items if item.get("metadata", {}).get("fine_grained_score", 0) >= score_threshold
        ]
    else:
        filtered_items = items
    sorted_items = sorted(filtered_items, key=lambda x: _sort_score(x, sort_key), reverse=True)
    return sorted_items[:topk]


def invoke_decorator(invoke_func, llm):
    def wrapper(*args, **kwargs):
        # 根据 https://huggingface.co/deepseek-ai/DeepSeek-R1#usage-recommendations 的建议：
        # Avoid adding a system prompt; all instructions should be contained within the user prompt.
        # NOTE: 目前假设只有第 1 个 message 才可能是 SystemMessage
        invoke_func_to_use = invoke_func

        if (
            is_deepseek_r1_series_models(llm)
            and isinstance(args[0][0], SystemMessage)
            and isinstance(args[0][-1], HumanMessage)
        ):
            args[0][-1] = HumanMessage(content=f"{args[0][0].content}\n\n{args[0][-1].content}")
            del args[0][0]

        result = invoke_func_to_use(*args)
        if kwargs.get("llm_input_output"):
            kwargs["llm_input_output"][llm.model_name]["input"].append(args[0])
            kwargs["llm_input_output"][llm.model_name]["output"].append(result.content)
        if is_deepseek_r1_series_models(llm):
            # deepseek-r1 系列模型会有 think 过程，在使用结果的时候需要去除
            result.content = remove_thinking_process(result.content)
            result.content = result.content.strip()

        return result

    return wrapper


@timeit(message="相似度计算小模型")
def calculate_similarity(
    text_pairs: List[Tuple[str, str]],
    similarity_model_gpu_cls: str = "model.self_host.similarity_model.SimilarityModel",
) -> List[float]:
    similarity_model_gpu = reg.get_registered_object(service_name=similarity_model_gpu_cls)
    if text_pairs:
        return similarity_model_gpu.compute_similarity(text_pairs)
    else:
        return []


def dispatch_rag_event_chunk(message: str):
    """Dispatch rag event chunk

    Args:
        message (str): The message to dispatch
        config (RunnableConfig): The runnable configuration
    """
    if not message.endswith("\n"):
        message += "\n"
    dispatch_custom_event(
        CustomMessageType.KNOWLEDGE_RAG_TEXT_CONTENT.value,
        data={"chunk": {"content": message}},
    )
