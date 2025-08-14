import pytest
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.config import settings
from aidev_agent.core.extend.models.llm_gateway import ChatModel, Embeddings


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_live_test():
    llm = ChatModel.get_setup_instance(model="hunyuan")
    assert llm.invoke("test")

    emb = Embeddings.get_setup_instance(model="bge-m3-embedding")
    assert emb.embed_query("test")


@pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_bkaidev_api():
    client = BKAidevApi.get_client()
    result = client.api.appspace_retrieve_knowledgebase(path_params={"id": 72})
    assert result


@pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
class TestAPI:
    def test_bkaidev_api_chat(self):
        client = BKAidevApi.get_client()

        session_code = "onlyfortest1"
        result = client.api.create_chat_session(json={"session_code": session_code, "session_name": "testonly"})
        assert result["data"]

        result = client.api.retrieve_chat_session(path_params={"session_code": result["data"]["session_code"]})
        assert result

        # 添加一些session content
        result = client.api.create_chat_session_content(
            json={
                "session_code": result["data"]["session_code"],
                "role": "user",
                "content": "test",
                "status": "success",
            }
        )
        assert result
        session_content_id = result["data"]["id"]
        # 更新一些session content
        result = client.api.update_chat_session_content(
            path_params={"id": session_content_id},
            json={
                "session_code": result["data"]["session_code"],
                "role": "user",
                "content": "test22222",
                "status": "success",
            },
        )
        assert result["data"]["content"] == "test22222"
        result = client.api.get_chat_session_contents(params={"session_code": result["data"]["session_code"]})
        assert len(result["data"]) == 1
        result = client.api.rename_chat_session(path_params={"session_code": session_code})
        client.api.destroy_chat_session_content(path_params={"id": session_content_id})
        result = client.api.get_chat_session_contents(params={"session_code": session_code})
        assert len(result["data"]) == 0

        client.api.destroy_chat_session(path_params={"session_code": "onlyfortest1"})

    def test_bkaidev_get_agent(self):
        client = BKAidevApi.get_client()
        result = client.api.retrieve_agent_config(path_params={"agent_code": settings.APP_CODE})
        print(result)

    def test_bkaidev_knowledge(self):
        client = BKAidevApi.get_client()
        obj = {
            "knowledge_base_id": 6,
            "file_path": "test_knowledge",
            "knowledge_name": "test_knowledge",
            "created_type": "manual",
            "content": "LangChain is a framework for developing applications powered by large language models (LLMs).",
        }
        result = client.api.add_knowledge_item(
            json=obj,
            headers={"X-BKAIDEV-USER": "user001"},
        )
        print(result)

    def test_bkaidev_dataset(self):
        client = BKAidevApi.get_client()
        result = client.api.add_dataset_item(
            json={
                "dataset_id": 9,
                "data": {"text": "test001"},
            },
            headers={"X-BKAIDEV-USER": "user001"},
        )
        print(result)

    def test_bkaidev_agent_session_management(self):
        client = BKAidevApi.get_client()
        results = client.api.list_chat_session()["data"]
        session_codes = [each["session_code"] for each in results]
        if session_codes:
            client.api.batch_delete_chat_session(json={"session_codes": session_codes})

        for _idx in range(5):
            _session_code = f"onlyfortest-{_idx}"
            result = client.api.create_chat_session(
                json={"session_code": _session_code, "session_name": f"testonly-{_idx}"}
            )
            session_codes.append(result["data"]["session_code"])

        results = client.api.list_chat_session()["data"]
        assert len(results) == 5
        client.api.batch_delete_chat_session(json={"session_codes": session_codes})

        results = client.api.list_chat_session()["data"]
        assert len(results) == 0
