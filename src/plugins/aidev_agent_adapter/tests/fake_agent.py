"""真实 stdio JSON-RPC 测试对端；不依赖已安装的协作智能体。"""

import json
import os
import sys
import time


def send(message):
    print(json.dumps({"jsonrpc": "2.0", **message}), flush=True)


def update(session, data):
    send({"method": "session/update", "params": {"sessionId": session, "update": data}})


sessions = 0
for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        assert not request["params"].get("clientCapabilities", {}).get("terminal")
        assert "AIDEV_ACCESS_TOKEN" not in os.environ
        send({"id": request_id, "result": {"protocolVersion": 1, "agentCapabilities": {}}})
    elif method == "session/new":
        sessions += 1
        send({"id": request_id, "result": {"sessionId": f"session-{sessions}"}})
    elif method == "session/prompt":
        params = request["params"]
        session = params["sessionId"]
        text = params["prompt"][0]["text"]
        if text == "crash":
            sys.exit(7)
        if text == "timeout":
            time.sleep(10)
        if text == "slow":
            time.sleep(0.15)
        if text == "permission":
            send(
                {
                    "id": "permission",
                    "method": "session/request_permission",
                    "params": {
                        "sessionId": session,
                        "toolCall": {"toolCallId": "delete", "title": "delete"},
                        "options": [{"optionId": "allow", "name": "Allow", "kind": "allow_once"}],
                    },
                }
            )
            response = json.loads(sys.stdin.readline())
            assert response["result"]["outcome"]["outcome"] == "cancelled"
        for delta in ["hello", "hello"]:
            update(session, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": delta}})
        if text == "mapping":
            time.sleep(10)
        update(
            session,
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "tool",
                "title": "search",
                "status": "in_progress",
                "rawInput": {"q": "partial"},
            },
        )
        update(
            session,
            {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "tool",
                "status": "completed",
                "rawInput": {"q": "final"},
                "rawOutput": "found",
            },
        )
        send({"id": request_id, "result": {"stopReason": "cancelled" if text == "cancelled" else "end_turn"}})
