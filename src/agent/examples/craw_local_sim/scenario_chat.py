# -*- coding: utf-8 -*-
"""场景 1：agent --localhost--> craw（对话转发链路）。

在 agent 容器内执行：健康探测 → 非流式 chat → 流式 chat（AG-UI 事件），
三步全过打印 ``SCENARIO-1 PASS``，任一步失败以非零码退出。
"""

import os
import sys

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import CrawCompletionAgent, get_backend
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent.registry import AgentBuildContext


class EnvTokenResourceManager:
    """示例用 resource_manager stub：按 env 解析用户 access_token。

    生产路径由平台 resource_manager 按 username 解析 token；本地仿真里
    token 经 agent.env 注入 ``BKAI_ACCESS_TOKEN``，身份装配走与生产一致的
    ``build()`` 链路（fail-closed：token 缺失在 build 期即报错，绝不降级
    为无身份请求）。token 经 ``X-Bkai-Access-Token`` 头透传，craw 前置
    反代据此做每用户隔离。
    """

    def resolve_access_token(self, username: str) -> str:
        return os.getenv("BKAI_ACCESS_TOKEN", "")


def build_agent(prompt: str) -> CrawCompletionAgent:
    ctx = AgentBuildContext(
        agent_code="craw-local-sim",
        agent_type=AgentType.CHAT,
        resource_manager=EnvTokenResourceManager(),
        session_code="craw-sim-session",
        username=os.getenv("SIM_USERNAME", "demo-user"),
        session_context_data=[{"role": "user", "content": prompt}],
    )
    return CrawCompletionAgent().build(ctx)


def main() -> None:
    backend = get_backend()
    health = backend.health()
    print(f"[1/3] health: {health}")
    assert health["ok"], f"craw 服务不健康: {health}"

    result = build_agent("请只回复一个单词：pong").execute()
    content = result["choices"][0]["delta"]["content"]
    print(f"[2/3] non-stream content: {content[:200]!r}")
    assert content.strip(), "非流式返回为空"

    agent = build_agent("请用一句话介绍你自己")
    events = []
    agent.event_handler = events.append
    sse_lines = list(agent.execute(ExecuteKwargs(stream=True)))
    types = [event.type.value for event in events]
    text = "".join(e.delta for e in events if e.type.value == "TEXT_MESSAGE_CONTENT")
    print(f"[3/3] stream events: {types}")
    print(f"      stream text: {text[:200]!r} (sse_lines={len(sse_lines)})")
    assert "RUN_STARTED" in types and "RUN_FINISHED" in types, "流式事件不完整"
    assert "RUN_ERROR" not in types, f"流式链路报错: {types}"
    assert text.strip(), "流式文本为空"

    print("SCENARIO-1 PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"SCENARIO-1 FAIL: {exc}")
        sys.exit(1)
