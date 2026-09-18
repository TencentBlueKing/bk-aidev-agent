# -*- coding: utf-8 -*-
"""亲手对话：在 agent 容器内与 craw 交互式多轮聊天（流式吐字）。

用法（在 craw_local_sim 目录）：
  # 交互多轮（需 tty，不加 -T）：
  docker compose --env-file <凭据文件> exec agent \
      /app/.venv/bin/python /sdk-src/examples/craw_local_sim/chat.py
  # 单发一问：
  docker compose --env-file <凭据文件> exec -T agent \
      /app/.venv/bin/python /sdk-src/examples/craw_local_sim/chat.py "你是谁"

多轮上下文在本进程内累积、整段重放（api_server 形态语义）；session_code
固定 → craw 侧（OpenClaw session / Hermes 会话+沙箱）保持粘滞。
"""

import os
import sys
import uuid

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import CrawCompletionAgent, get_backend
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent.registry import AgentBuildContext


class EnvTokenResourceManager:
    """示例用 resource_manager stub：按 env 解析用户 access_token。

    token 经 agent.env 注入 ``BKAI_ACCESS_TOKEN``，身份装配走与生产一致的
    ``build()`` 链路（fail-closed：token 缺失在 build 期即报错）。
    """

    def resolve_access_token(self, username: str) -> str:
        return os.getenv("BKAI_ACCESS_TOKEN", "")


def ask(history: list[dict], session_code: str) -> str:
    """发一轮对话，流式打印回复并返回全文。"""
    ctx = AgentBuildContext(
        agent_code="craw-local-chat",
        agent_type=AgentType.CHAT,
        resource_manager=EnvTokenResourceManager(),
        session_code=session_code,
        username=os.getenv("SIM_USERNAME", "demo-user"),
        session_context_data=list(history),
    )
    agent = CrawCompletionAgent().build(ctx)

    reply: list[str] = []

    def on_event(event) -> None:
        kind = getattr(getattr(event, "type", None), "value", "")
        if kind == "TEXT_MESSAGE_CONTENT":
            print(event.delta, end="", flush=True)
            reply.append(event.delta)
        elif kind == "RUN_ERROR":
            print(f"\n[RUN_ERROR] {event.message}", file=sys.stderr)

    agent.event_handler = on_event
    # 生产路径：execute(stream=True) 经 GeneratorStreamingHelper 队列消费
    for _ in agent.execute(ExecuteKwargs(stream=True)):
        pass
    print()
    return "".join(reply)


def main() -> None:
    backend = get_backend()
    session_code = f"craw-chat-{uuid.uuid4().hex[:8]}"
    history: list[dict] = []

    def turn(question: str) -> None:
        history.append({"role": "user", "content": question})
        print("craw> ", end="", flush=True)
        answer = ask(history, session_code)
        history.append({"role": "assistant", "content": answer})

    if len(sys.argv) > 1:  # 单发模式
        question = " ".join(sys.argv[1:])
        print(f"你> {question}")
        turn(question)
        return

    print(f"craw 交互对话 | backend={backend.name} api_url={backend.api_url} session={session_code}")
    print("（exit / Ctrl-D 退出；多轮上下文自动携带）")
    while True:
        try:
            question = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question or question.lower() in ("exit", "quit"):
            break
        turn(question)


if __name__ == "__main__":
    main()
