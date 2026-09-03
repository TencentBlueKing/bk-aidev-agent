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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

messages 历史装配链

负责把 chat_history 账本（lossless ChatPrompt 单账本）装配为 LLM 输入：LLM 视图构建
（system/空 content 过滤、末条生成中占位清理、tool_calls 配对过滤）、半成品 status 过滤、
轮数截断、角色归一与多模态转换、LangChain 消息转换、预设注入（inject_role_system）。
账本无损原则：所有过滤/改写只作用于深拷贝视图副本，绝不写回 chat_history 账本本体
（快照与 LLM 同源不同用途）。
"""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from aidev_agent.core.ag_ui.types import InterruptMessage, ReasoningLangChainMessage
from aidev_agent.core.ag_ui.utils import parse_multimodal_content, parse_reasoning_content_value
from aidev_agent.enums import PromptRole
from aidev_agent.exceptions import AgentException
from aidev_agent.pydantic_models import ChatPrompt, ModelContextSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 半成品消息的 status 放行集合（平台原值域，非 AG-UI 归一域）。
# 仅 status 命中放行集合或 role 为 interrupt 的记录才进入 LLM 输入，
# 其余（loading/streaming/pending 等半成品）在 convert 链被过滤。
_LLM_ALLOWED_STATUS = {"success", "complete", "fail", "error"}
# 前端 markdown 图片格式（USER_IMAGE 记录提取图片 URL 用）
_IMAGE_FILE_PATTERN = re.compile(r"^!\[.*\]\((http[^)]+/([^/]+?))\)")
# 不送入大模型的角色（前端引导类展示记录）
_SKIP_PROMPT_ROLE = ["guide"]


# ---------------------------------------------------------------------------
# 提取 tool_calls
# ---------------------------------------------------------------------------


def _extract_tool_calls(builtin_property: dict) -> list[dict]:
    """从 builtin_property 中提取 tool_calls 列表。

    注意：arguments 在数据库中存储为 JSON 字符串，需要解析为字典。
    """
    tool_calls = []
    for tc in builtin_property.get("tool_calls", []):
        args_str = tc.get("function", {}).get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {}

        tool_calls.append(
            {
                "id": tc.get("id", ""),
                "name": tc.get("function", {}).get("name", ""),
                "args": args,
                "type": "tool_call",
            }
        )
    return tool_calls


# ---------------------------------------------------------------------------
# 清理（思考 HTML / 知识库召回 HTML 剥离，仅 LLM 输入视图）
# ---------------------------------------------------------------------------


def _remove_think(content: str) -> str:
    """移除 HTML 中的思考部分内容（LLM 输入视图使用，账本保留原文供快照忠实展示）。"""
    _content = re.sub(
        r'<section class="think-head click-close">[\s\S]*?</section>',
        "",
        content,
        flags=re.DOTALL,
    )

    _content = re.sub(
        r'<section class="think-head click-close closed">[\s\S]*?</section>',
        "",
        _content,
        flags=re.DOTALL,
    )

    _content = re.sub(r'<section class="think-body">[\s\S]*?</section>', "", _content, flags=re.DOTALL)

    if not _content.strip():
        think_body_match = re.search(r'<section class="think-body">([\s\S]*?)</section>', content, re.DOTALL)
        if think_body_match:
            _content = think_body_match.group(1).strip()

    return _content.strip()


def _remove_reference_doc(content: str) -> str:
    """移除 HTML 中的参考资料相关段落（LLM 输入视图使用，账本保留原文供快照忠实展示）。"""
    new_content = re.sub(r'<section class="knowledge-head click-close">.*?</section>', "", content, flags=re.DOTALL)
    new_content = re.sub(r'<ul class="knowledge-body">.*?<\/ul>', "", new_content, flags=re.DOTALL)
    new_content = re.sub(r'<section class="knowledge-tips">.*?</section>', "", new_content, flags=re.DOTALL)
    return new_content


# ---------------------------------------------------------------------------
# 过滤（tool_calls 与工具结果配对过滤）
# ---------------------------------------------------------------------------


def _update_tool_calls_in_prompt(prompt: ChatPrompt, matched_tool_calls: list[dict]) -> None:
    """更新 ChatPrompt 中的 tool_calls，只保留匹配的调用。"""
    builtin_property = prompt.builtin_property or {}
    tool_calls_raw = builtin_property.get("tool_calls", [])

    matched_ids = {tc.get("id", "") for tc in matched_tool_calls}

    filtered_tool_calls = [tc for tc in tool_calls_raw if tc.get("id", "") in matched_ids]

    if builtin_property:
        builtin_property["tool_calls"] = filtered_tool_calls
    else:
        prompt.builtin_property = {"tool_calls": filtered_tool_calls}


def _filter_unmatched_tool_calls(chat_history: list[ChatPrompt]) -> list[ChatPrompt]:
    """过滤没有匹配工具结果的 assistant 消息（LLM 输入视图使用，账本保留全量）。

    当 assistant 消息包含 tool_calls 但没有对应的 tool 结果消息时，
    该 assistant 消息会导致模型调用失败（模型期望每个 tool_use 都有对应的 tool_result）。

    特殊处理：ask_user_question 等中断型工具，工具调用因 interrupt 中断没有 tool 结果，
    但账本中有对应的 role=interrupt 记录。这类 tool_call 不应被过滤，
    否则续流时 MESSAGES_SNAPSHOT 会丢失 AI(AskUser) 消息。
    """
    if not chat_history:
        return chat_history

    tool_result_ids: set[str] = set()
    # interrupt 记录的 tool_call_id（ask_user_question 中断的 tool_call 有对应 interrupt 记录）
    interrupt_tool_call_ids: set[str] = set()
    for prompt in chat_history:
        if prompt.role == "tool":
            tool_call_id = prompt.builtin_property.get("tool_call_id", "")
            if tool_call_id:
                tool_result_ids.add(tool_call_id)
        elif prompt.role == "interrupt":
            # interrupt 记录的 builtin_property 或 content 中含 tool_call_id
            tc_id = prompt.builtin_property.get("tool_call_id", "")
            if tc_id:
                interrupt_tool_call_ids.add(tc_id)

    # 过滤 assistant 消息中未匹配的 tool_calls：
    # 全部无结果 → 整条丢弃；部分有结果 → 仅保留匹配的 tool_calls。
    # 中断型 tool_call（有对应 interrupt 记录）视为已匹配，不过滤。
    filtered_history: list[ChatPrompt] = []
    for prompt in chat_history:
        if prompt.role != "assistant":
            filtered_history.append(prompt)
            continue

        tool_calls = _extract_tool_calls(prompt.builtin_property or {})

        if not tool_calls:
            filtered_history.append(prompt)
            continue

        matched_calls = [
            tc
            for tc in tool_calls
            if tc.get("id", "") in tool_result_ids or tc.get("id", "") in interrupt_tool_call_ids
        ]
        unmatched_calls = [
            tc
            for tc in tool_calls
            if tc.get("id", "") not in tool_result_ids and tc.get("id", "") not in interrupt_tool_call_ids
        ]

        if not matched_calls:
            logger.info(
                f"filtering assistant message with no matched tool_calls, "
                f"message_id=[{prompt.id}], tool_calls_count=[{len(tool_calls)}]"
            )
            continue

        if unmatched_calls:
            logger.info(
                f"removing unmatched tool_calls from assistant message, "
                f"message_id=[{prompt.id}], total_calls=[{len(tool_calls)}], "
                f"matched=[{len(matched_calls)}], unmatched=[{len(unmatched_calls)}]"
            )
            _update_tool_calls_in_prompt(prompt, matched_calls)

        filtered_history.append(prompt)

    return filtered_history


# ---------------------------------------------------------------------------
# LLM 视图构建链（视图构建 / 末条占位清理 / status 过滤 / 轮数截断）
# ---------------------------------------------------------------------------


def _build_llm_history_view(chat_history: list[ChatPrompt], *, generating_keyword: str | None) -> list[ChatPrompt]:
    """构建 LLM 输入视图：在账本深拷贝副本上做 LLM 侧过滤，绝不改动 chat_history 账本本体。

    - 剔除 system 展示类记录（system 注入由 inject_role_system 挂点在拼接期承担）
    - 剔除空 content 记录
    - 清理最后一条含生成中关键词的 assistant 占位（仅作用于视图副本，账本无损）
    - 过滤没有匹配工具结果的 tool_calls（中断型 tool_call 保留）

    账本保留全量记录供快照忠实转换，同源不同用途；深拷贝保证后续 convert 链
    （_convert_contents / _chat_history_to_langchain_messages）的原地改写不污染账本。
    思考 HTML 与知识库召回 HTML 的剥离由 ``_chat_history_to_langchain_messages`` 的
    ASSISTANT|AI 分支承担（覆盖 assistant/ai/pause 三角色）。
    """
    view = [
        each.model_copy(deep=True) for each in chat_history if each.role != PromptRole.SYSTEM.value and each.content
    ]
    view = _clean_last_generating_assistant(view, generating_keyword=generating_keyword)
    return _filter_unmatched_tool_calls(view)


def _clean_last_generating_assistant(view: list[ChatPrompt], *, generating_keyword: str | None) -> list[ChatPrompt]:
    """清理最后一条含生成中关键词的 assistant 消息（仅作用于 LLM 输入视图副本，不写回账本）"""
    if not view or not generating_keyword:
        return view
    last = view[-1]
    if last.role != PromptRole.ASSISTANT.value:
        return view
    if isinstance(last.content, str) and generating_keyword in last.content:
        logger.info("cleaning last assistant message with generating keyword from LLM input view")
        return view[:-1]
    return view


def _filter_status_for_llm(chat_history: list[ChatPrompt]) -> list[ChatPrompt]:
    """过滤半成品消息（loading/streaming/pending 非 interrupt）不进 LLM 输入。

    过滤在 convert 链上对 ChatPrompt 副本处理，绝不在 chat_history 账本上做：
    账本保留全量（供快照），LLM 输入过滤，同源不同用途。
    """
    return [
        each
        for each in chat_history
        if each.role == PromptRole.INTERRUPT.value
        or (each.builtin_property or {}).get("status", "complete") in _LLM_ALLOWED_STATUS
    ]


def _truncate_chat_history(
    chat_prompts: list[ChatPrompt], *, model_context_options: ModelContextSettings | None
) -> list[ChatPrompt]:
    """截断对话历史到指定轮数（user 消息数），保证 system 完整且 system 后第一条是 user。

    轮数上限读 ModelContextSettings.context_window（默认 16）。分离 system 与 non-system、
    只保留最后一个 system、user 超上限时从倒数第 max 条 user 起保留。
    """
    context_window = (model_context_options.context_window or 16) if model_context_options else 16
    max_rounds = max(context_window, 1)
    # 分离 system 与其他 prompts
    system_prompts = [p for p in chat_prompts if p.role == PromptRole.SYSTEM.value]
    non_system_prompts = [p for p in chat_prompts if p.role != PromptRole.SYSTEM.value]
    # 只保留最后一个 system（如有）
    system_prompt = system_prompts[-1] if system_prompts else None

    # 统计 user 消息数，未超上限则无需截断
    user_count = sum(1 for p in non_system_prompts if p.role == PromptRole.USER.value)
    if user_count <= max_rounds:
        if len(system_prompts) <= 1:
            return chat_prompts
        return [system_prompts[-1]] + non_system_prompts

    # 需要截断：找到倒数第 max_rounds 个 user 消息的位置，从该位置起保留
    user_positions = [i for i, p in enumerate(non_system_prompts) if p.role == PromptRole.USER.value]
    if len(user_positions) < max_rounds:
        return ([system_prompt] + non_system_prompts) if system_prompt else non_system_prompts

    start_idx = user_positions[-max_rounds]
    result_prompts = non_system_prompts[start_idx:]
    return ([system_prompt] + result_prompts) if system_prompt else result_prompts


# ---------------------------------------------------------------------------
# 转换（角色归一与多模态转换 / LangChain 消息转换）
# ---------------------------------------------------------------------------


def _convert_contents(
    contents: list[ChatPrompt], *, support_vision: bool, model_name: str, files: list[dict]
) -> list[ChatPrompt]:
    """将无需送到大模型处理的 content 去掉"""
    new_contents = []
    for each in contents:
        each.role = each.role.replace("hidden-", "")
        if each.role in _SKIP_PROMPT_ROLE:
            continue
        if each.role == PromptRole.HIDDEN.value:
            each.role = PromptRole.USER.value
        if each.role == PromptRole.PAUSE.value:
            each.role = PromptRole.ASSISTANT.value
        # 前端传入的预设角色提示词（hidden-role 剥前缀后为 role）按 system 语义进 LLM 视图
        if each.role == PromptRole.ROLE.value:
            each.role = PromptRole.SYSTEM.value
        if each.role == PromptRole.USER_IMAGE.value:
            if not support_vision:
                raise AgentException(message="当前模型不支持图片识别,请切换其他模型")
            each.role = PromptRole.USER.value
            match = _IMAGE_FILE_PATTERN.search(each.content)
            if match:
                file_path, _ = match.group(1), match.group(2)
                each.content = [{"type": "image_url", "image_url": {"url": file_path}}]
                # 图片不计算实际大小，但不能为 0 —— 给一个大于 0 的占位值
                files.append({"file_name": file_path, "file_size": 100})
            else:
                raise AgentException(message="图片md格式非法")
        # deepseek-r1 系列不支持 system role，需要降级为 user
        if each.role == PromptRole.SYSTEM.value and "deepseek-r1" in model_name:
            each.role = PromptRole.USER.value
        new_contents.append(each)

    return new_contents


def _chat_history_to_langchain_messages(chat_history: list[ChatPrompt]) -> list[BaseMessage]:
    """
    将 ChatPrompt 列表转换为 LangChain 消息列表
    支持从 builtin_property 中提取 tool_calls 和 tool_call_id 等协议字段，
    以支持多轮工具调用场景的历史消息透传。
    """
    messages: list[BaseMessage] = []
    for each in chat_history:
        bp = each.builtin_property or {}
        turn_kwargs = {}
        if bp.get("turn_id"):
            turn_kwargs["turn_id"] = bp["turn_id"]
        if bp.get("status"):
            turn_kwargs["status"] = bp["status"]
        if bp.get("created_at"):
            # 仅供 MESSAGES_SNAPSHOT 展示；LangChain 转 OpenAI 不会把该键写入模型 payload
            turn_kwargs["created_at"] = bp["created_at"]
        match each.role:
            case PromptRole.USER.value:
                multimodal = parse_multimodal_content(each.content)
                if multimodal is not None:
                    each.content = multimodal
                if isinstance(each.content, list):
                    new_content = []
                    for each_content in each.content:
                        if each_content.get("type") == "binary":
                            new_content.append(each_content)
                        elif each_content.get("url"):
                            new_content.append({"type": "image_url", "image_url": {"url": each_content.get("url")}})
                        else:
                            new_content.append(each_content)
                    each.content = new_content
                    messages.append(HumanMessage(id=each.id, content=each.content, additional_kwargs=turn_kwargs))
                else:
                    messages.append(HumanMessage(id=each.id, content=str(each.content), additional_kwargs=turn_kwargs))
            case PromptRole.ASSISTANT.value | PromptRole.AI.value:
                tool_calls = _extract_tool_calls(bp)
                content = each.content
                # LLM 输入清理：剥离思考 HTML 与知识库召回 HTML（账本保留原文供快照忠实展示）；
                # content 非 str（list/dict 多模态）时跳过，避免误剥结构化内容
                if isinstance(content, str):
                    content = _remove_think(content)
                    content = _remove_reference_doc(content)
                # 快照链消费：artifacts 经 builtin_property 显式读取，放入
                # AIMessage.additional_kwargs（LangChain 标准扩展位）保留产物信息；
                # 快照侧由 ag_ui 转换器的 _build_assistant_property 直接从账本
                # builtin_property 读取并还原 AGUIAssistantMessage.property.artifacts。
                # 无 artifacts 时不写 additional_kwargs，避免污染其它 AIMessage。
                additional_kwargs = dict(turn_kwargs)
                artifacts = bp.get("artifacts")
                if artifacts:
                    additional_kwargs["artifacts"] = artifacts
                messages.append(
                    AIMessage(
                        id=each.id,
                        content=content,
                        tool_calls=tool_calls,
                        additional_kwargs=additional_kwargs,
                    )
                )
            case PromptRole.SYSTEM.value:
                messages.append(SystemMessage(id=each.id, content=each.content, additional_kwargs=turn_kwargs))
            case PromptRole.TOOL.value:
                content = each.content if isinstance(each.content, str) else str(each.content)
                messages.append(
                    ToolMessage(
                        id=each.id,
                        content=content,
                        tool_call_id=bp.get("tool_call_id", ""),
                        additional_kwargs=turn_kwargs,
                    )
                )
            case PromptRole.REASONING.value:
                duration = bp.get("duration", 0)
                messages.append(
                    ReasoningLangChainMessage(
                        id=each.id,
                        content=parse_reasoning_content_value(each.content),
                        additional_kwargs={"duration": duration, **turn_kwargs},
                    )
                )
            case PromptRole.INTERRUPT.value:
                # 中断/审批卡片：content 落库为 JSON 字符串（形如
                # ``{"outcome": {"type": "interrupt"/"success", "interrupts": [...]}}``），
                # 历史回放时可能已被解析为 dict。统一还原为 dict 后封装成
                # InterruptMessage（继承 ActivityMessage），既进入 state["messages"]
                # 供 MESSAGES_SNAPSHOT 重建与前端展示，又会被 basic_middleware 的
                # isinstance(ActivityMessage) 过滤剔除，绝不进入 LLM 输入。
                interrupt_content = each.content
                if isinstance(interrupt_content, str):
                    try:
                        interrupt_content = json.loads(interrupt_content)
                    except (json.JSONDecodeError, TypeError):
                        interrupt_content = {}
                if not isinstance(interrupt_content, (dict, list)):
                    interrupt_content = {}
                messages.append(InterruptMessage(id=each.id, content=interrupt_content, additional_kwargs=turn_kwargs))
    return messages


# ---------------------------------------------------------------------------
# 注入（预设注入，公开）
# ---------------------------------------------------------------------------


def inject_role_system(messages: list[BaseMessage], *, agent_info: dict | None, model_name: str) -> list[BaseMessage]:
    """在 convert 链尾部消费 agent_info 预设，前置 system 与 few-shot 到 LLM 视图头部。

    数据源为 ``agent_info["prompt_setting"]``，按优先级取 ``collection_content`` →
    ``prompt_content`` → ``content``（遗留 agent 兼容）→ 空列表，按条目 role 域全量映射：
    hidden-system/system → SystemMessage、hidden-user → HumanMessage（few-shot）、
    pause/其他 → 忽略、空 content → 跳过；数据为空时整体透传。

    注入消息带固定 id（system 用 ``role-system-preset``，few-shot 用
    ``role-user-preset-{i}``），走 langgraph add_messages 同 id 原位替换，避免跨轮
    checkpoint 双份。多条 system 条目以 "\\n\\n".join 合并为单条。deepseek-r1 模型下
    system 域降级为 HumanMessage（id 保持固定），中间件 DeepSeekR1VariablesMiddleware
    已默认兜底，此处为双保险。

    只改 LLM 视图（返回新列表前置注入），绝不写回 chat_history，避免泄漏进快照。
    """
    agent_info = agent_info or {}
    prompt_setting = agent_info.get("prompt_setting") or {}
    preset = (
        prompt_setting.get("collection_content")
        or prompt_setting.get("prompt_content")
        or prompt_setting.get("content")
        or []
    )
    if not preset:
        return messages  # 数据为空/遗留 agent：整体透传

    inject: list[BaseMessage] = []
    system_blocks: list[str] = []
    user_index = 0
    for each in preset:
        if not isinstance(each, dict):
            continue
        role = each.get("role") or ""
        content = each.get("content")
        if not isinstance(content, str) or not content.strip():
            continue  # 空 content 或非 str content：跳过
        if role in ("hidden-system", "system"):
            system_blocks.append(content.strip())
        elif role == "hidden-user":
            inject.append(HumanMessage(id=f"role-user-preset-{user_index}", content=content.strip()))
            user_index += 1
        # pause / 其他 → 忽略

    is_r1 = "deepseek-r1" in model_name
    if system_blocks:
        system_content = "\n\n".join(system_blocks)
        if is_r1:
            inject.append(HumanMessage(id="role-system-preset", content=system_content))
        else:
            inject.append(SystemMessage(id="role-system-preset", content=system_content))
    return inject + messages  # 前置到头部；只改 LLM 视图，不写回 chat_history


# ---------------------------------------------------------------------------
# 编排（唯一公开入口）
# ---------------------------------------------------------------------------


def convert_chat_history_to_messages(
    chat_history: list[ChatPrompt],
    *,
    model_context_options: ModelContextSettings | None,
    support_vision: bool,
    model_name: str,
    agent_info: dict | None,
    generating_keyword: str | None,
    files: list[dict],
) -> list[BaseMessage]:
    """编排整条装配链：视图 → status 过滤 → 截断 → 角色归一 → LangChain 转换 → 预设注入。

    链序与 ChatCompletionAgent.execute() 的消费形态一致；``files`` 传引用，
    USER_IMAGE 记录会在链内对调用方列表原地 append。
    """
    if not chat_history:
        return []
    llm_history = _build_llm_history_view(chat_history, generating_keyword=generating_keyword)
    filtered = _filter_status_for_llm(llm_history)
    truncated = _truncate_chat_history(filtered, model_context_options=model_context_options)
    converted = _chat_history_to_langchain_messages(
        _convert_contents(truncated, support_vision=support_vision, model_name=model_name, files=files)
    )
    return inject_role_system(converted, agent_info=agent_info, model_name=model_name)
