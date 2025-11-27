from langchain_core.documents import Document


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


def deduplicate_knowledge_file_paths(knowledge_chunks):
    """按照 file path 进行去重，且只保留 metadata，且按照 fine grained score 进行降序排序"""
    unique_items = list(
        {item["metadata"]["file_path"]: {"metadata": item["metadata"]} for item in knowledge_chunks}.values()
    )
    return sorted(unique_items, key=lambda x: x["metadata"]["fine_grained_score"], reverse=True)


def filter_and_select_topk(items, score_threshold, topk):
    if score_threshold:
        filtered_items = [
            item for item in items if item.get("metadata", {}).get("fine_grained_score", 0) >= score_threshold
        ]
    else:
        filtered_items = items
    sorted_items = sorted(filtered_items, key=lambda x: x["metadata"]["fine_grained_score"], reverse=True)
    return sorted_items[:topk]
