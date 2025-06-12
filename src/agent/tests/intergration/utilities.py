import json


def verify_streaming_result_format(results: list[str], need_reference_doc: bool = False) -> bool:
    # 验证流式输出结果
    has_reference_doc = not need_reference_doc
    done = results.pop()
    for each in results:
        each = json.loads(each[6:])
        if "documents" in each:
            has_reference_doc = True
            assert each["cover"] is True
        else:
            assert "content" in each
    assert has_reference_doc
    assert done == "data: [DONE]\n\n"
