import type { SourceGuideSection } from './source-guide';

export interface TraceSample {
  duration: string;
  id: string;
  page: string;
  service: string;
  status: 'error' | 'slow';
  summary: string;
}

export interface VersionRequirement {
  minVersion: string;
  note: string;
  pkg: string;
  recommended: string;
}

export interface DataFlowStep {
  actor: '前端宿主' | '小鲸组件' | '后台接口' | 'Agent 二开';
  detail: string;
  step: string;
  title: string;
}

export const TRACE_SAMPLES: TraceSample[] = [
  {
    id: 'trace-9f8a1c02',
    service: 'order-payment-svc',
    page: 'trace-detail',
    status: 'error',
    duration: '5,120ms',
    summary: '支付回调超时 504（上游渠道未响应）',
  },
  {
    id: 'trace-4b7d2e19',
    service: 'api-gateway-prod',
    page: 'trace-detail',
    status: 'error',
    duration: '1,840ms',
    summary: '下游 Pod 摘除触发 502 Bad Gateway',
  },
  {
    id: 'trace-7c1e5a88',
    service: 'inventory-query-svc',
    page: 'trace-detail',
    status: 'slow',
    duration: '3,460ms',
    summary: '全表扫描导致 MySQL 慢查询告警',
  },
];

export const VERSION_REQUIREMENTS: VersionRequirement[] = [
  {
    pkg: '@blueking/ai-blueking',
    minVersion: '>= 2.1.4（2.1.4-beta.15 引入）',
    recommended: '3.1.1',
    note: '提供 requestOptions.context 与 #welcome 插槽；正式版 2.1.4 已包含后续修复，不建议停留在 beta.15~beta.24',
  },
  {
    pkg: '@blueking/chat-helper',
    minVersion: 'v2 任意版本',
    recommended: '3.1.0',
    note: '负责将用户消息的 property 原样 POST 至 session_content/',
  },
  {
    pkg: '@blueking/chat-x',
    minVersion: '与小鲸配套',
    recommended: '3.1.2-beta.2',
    note: '提供 ChatContainer #welcome 插槽承载动态欢迎区',
  },
];

export const DATA_FLOW_DIAGRAM = `┌─────────────────────────┐
│ 业务页面（Trace 详情）    │  1. 用户切换 Trace → traceId.value 更新
│ traceId = trace-9f8a1c02│     computed requestOptions.context 同步更新
└───────────┬─────────────┘
            │ :request-options="requestOptions"
            │ #welcome="{ welcomeTitle, openingRemark }"
            ▼
┌─────────────────────────┐
│ 小鲸欢迎区（方案 A）      │  2. 打开空会话即见按钮「分析 trace-9f8a1c02 的日志」
│ 点击按钮 / 手输「日志分析」│     点击调用 botRef.sendMessage('日志分析')
└───────────┬─────────────┘
            │ 3. applyRequestOptionsContext() 自动转成结构化数组
            │    写入 property.extra.context
            ▼
┌─────────────────────────┐
│ POST session_content/   │  4. 落库用户消息：
│                         │     content = "日志分析"（气泡原文，不含 trace_id）
│                         │     property.extra.context = [
│                         │       { trace_id, __key: "trace_id", __value: "trace-9f8a1c02", ... }
│                         │     ]
└───────────┬─────────────┘
            │ 5.紧接着 POST chat_completion/（仅带 session_code，不再重复传 context）
            ▼
┌─────────────────────────┐
│ 后台 Agent 二次开发      │  6. 读取本轮最后一条 user 消息的 extra.context
│                         │     按 __key / __value 取出 trace_id
│                         │     仅在送给 LLM 的输入中拼接 Prompt（不改落库 content）
│                         │     调用日志 / Trace 查询工具 → SSE 流式返回分析结论
└─────────────────────────┘`;

export const DATA_FLOW_STEPS: DataFlowStep[] = [
  {
    step: '01',
    actor: '前端宿主',
    title: '页面对象写入 computed requestOptions.context',
    detail: '把整个 requestOptions 写成 computed，让 context 本身是普通对象（注意：context 传函数会被静默忽略）。',
  },
  {
    step: '02',
    actor: '小鲸组件',
    title: '欢迎区 #welcome 渲染动态快捷按钮',
    detail: '空会话时展示「分析 {{ traceId }} 的日志」按钮，随页面选中项实时刷新；点击直接调用 sendMessage("日志分析")。',
  },
  {
    step: '03',
    actor: '小鲸组件',
    title: 'POST session_content/ 携带 property.extra.context',
    detail: '发消息时小鲸自动把 context 转为 [{ [key]: value, context_type: "input", __label, __key, __value }] 并写入消息属性。',
  },
  {
    step: '04',
    actor: '后台接口',
    title: 'POST chat_completion/ 仅传 session_code',
    detail: '流式对话请求本身不重复携带 context；服务端通过 session_code 拉取会话历史时即可拿到用户消息的 property.extra。',
  },
  {
    step: '05',
    actor: 'Agent 二开',
    title: '抽取 __key / __value 并组装本轮 LLM Prompt',
    detail: '从本轮最后一条 user 消息取出 trace_id，仅在送给模型前拼装上下文 Prompt（不要覆盖落库 content），触发工具查日志。',
  },
];

export const FRONTEND_VUE3_CODE = `<template>
  <AIBlueking
    ref="aiRef"
    :url="apiUrl"
    :always-create-new-session="true"
    :request-options="requestOptions"
  >
    <!-- 方案 A：利用 #welcome 插槽在空会话展示页面动态快捷按钮 -->
    <template #welcome="{ welcomeTitle, openingRemark }">
      <div class="trace-welcome">
        <h3>{{ welcomeTitle || '你好，我是小鲸' }}</h3>
        <p v-if="openingRemark">{{ openingRemark }}</p>

        <button
          v-if="currentTrace"
          type="button"
          class="trace-quick-btn"
          @click="handleAnalyzeTrace"
        >
          分析 {{ currentTrace.id }} 的日志
        </button>
        <p v-else class="trace-empty-tip">
          当前页面未选中 Trace，打开任意 Trace 详情即可一键分析
        </p>
      </div>
    </template>
  </AIBlueking>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { AIBlueking, type AIBluekingExpose, type IRequestOptions } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '/api/ai/';
const aiRef = ref<AIBluekingExpose>();
const currentTrace = ref<{ id: string; service: string } | null>({
  id: 'trace-9f8a1c02',
  service: 'order-payment-svc',
});

// 关键：整份 requestOptions 用 computed，确保 context 本身是普通对象
// （context 字段直接传函数形态当前会被静默忽略）
const requestOptions = computed<IRequestOptions>(() => ({
  context: currentTrace.value
    ? {
        trace_id: currentTrace.value.id,
        service: currentTrace.value.service,
        page: 'trace-detail',
      }
    : undefined,
}));

// 用户气泡只展示「日志分析」，trace_id 自动写入 property.extra.context
const handleAnalyzeTrace = async () => {
  await aiRef.value?.sendMessage('日志分析');
};
</script>`;

export const SESSION_CONTENT_PAYLOAD_JSON = `// POST {urlPrefix}/session_content/
{
  "session_code": "session_xxx",
  "role": "user",
  "content": "日志分析",
  "property": {
    "extra": {
      "context": [
        {
          "trace_id": "trace-9f8a1c02",
          "context_type": "input",
          "__label": "trace_id",
          "__key": "trace_id",
          "__value": "trace-9f8a1c02"
        },
        {
          "service": "order-payment-svc",
          "context_type": "input",
          "__label": "service",
          "__key": "service",
          "__value": "order-payment-svc"
        },
        {
          "page": "trace-detail",
          "context_type": "input",
          "__label": "page",
          "__key": "page",
          "__value": "trace-detail"
        }
      ]
    }
  }
}`;

export const BACKEND_EXTRACT_AND_PROMPT_PY = `# 1. 抽取工具（与 aidev_agent/services/command_handler.py 协议一致）
def extract_context_vars(context: list[dict] | None) -> dict[str, object]:
    """优先使用 __key / __value 取值，不要扫任意顶层键。"""
    variables: dict[str, object] = {}
    for item in context or []:
        if "__key" in item and "__value" in item:
            variables[str(item["__key"])] = item["__value"]
    return variables


# 2. 从本轮最后一条 user 消息中读取 context
#    兼容平铺的 extra（ChatPrompt）和原始 property.extra（session_content）
def get_last_user_context(session_context_data: list[dict]) -> tuple[dict | None, dict[str, object]]:
    last_user = next(
        (msg for msg in reversed(session_context_data) if msg.get("role") == "user"),
        None,
    )
    if not last_user:
        return None, {}
    extra = last_user.get("extra") or (last_user.get("property") or {}).get("extra") or {}
    return last_user, extract_context_vars(extra.get("context"))


# 3. 场景一：普通对话（「日志分析」，无 extra.command）
#    仅在送给模型的内存消息里拼接 Prompt，不要修改落库的 session_content.content！
def build_prompt_for_llm(session_context_data: list[dict]) -> list[dict]:
    last_user, ctx = get_last_user_context(session_context_data)
    if not last_user:
        return session_context_data

    trace_id = ctx.get("trace_id")
    if not trace_id:
        # 缺页面上下文时直接让模型按系统提示词说明缺少 Trace ID
        return session_context_data

    user_text = last_user.get("content") or ""
    enriched = (
        "【当前页面上下文（对用户不可见）】\\n"
        f"- trace_id: {trace_id}\\n"
        f"- service: {ctx.get('service', '')}\\n"
        f"- page: {ctx.get('page', '')}\\n\\n"
        f"【用户原始指令】\\n{user_text}\\n\\n"
        "请优先查询该 trace_id 的调用链与错误日志，给出根因定位与排查建议。"
    )

    # 浅拷贝列表与最后一条 user 消息，避免污染持久化记录
    cloned = list(session_context_data)
    idx = cloned.index(last_user)
    cloned[idx] = {**last_user, "content": enriched}
    return cloned`;

export const BACKEND_COMMAND_HANDLER_PY = `# 场景二：若前端走快捷指令（携带 extra.command + extra.context）
# requestOptions.context 会自动追加到快捷指令 context 后，__key 冲突时页面 context 覆盖表单值
from aidev_agent.services.command_handler import CommandHandler, CommandProcessor


class AnalyzeTraceLogHandler(CommandHandler):
    command = "analyze_trace_log"

    def get_template(self) -> str:
        return """
请分析 Trace {{ trace_id }}（服务：{{ service }}）的日志与调用链。
用户补充说明：{{ input }}
请按「现象 → 根因定位 → 修复建议」输出结论。
"""


# 注意：CommandProcessor 默认未注册到 ChatAgentBuilder，二开时按需显式注册并调用
CommandProcessor.register_handler("analyze_trace_log", AnalyzeTraceLogHandler)

# 调用示例：
# extra = last_user.get("extra") or {}
# if extra.get("command"):
#     rendered_prompt = CommandProcessor().process_command(extra)
#     # 可写入内存消息 content；若写入 extra.rendered_content 并落库，后续轮次也会沿用渲染后文本`;

export const SYSTEM_PROMPT_TEMPLATE = `你是一名蓝鲸可观测性排障助手。

用户消息可能携带隐藏的页面上下文（extra.context，结构为 __key / __value）：
1. 若上下文中包含 trace_id，视为「用户当前正在查看的 Trace」，分析时必须直接使用该 trace_id 调用日志 / Trace 查询工具，禁止再反问用户提供 Trace ID。
2. 若用户只说「日志分析」「帮我看看」且存在 trace_id，直接针对该 trace_id 执行日志与链路分析。
3. 若上下文中缺少 trace_id 且用户未在文本中给出，明确告知「当前未获取到页面 Trace ID，请打开具体 Trace 详情或手动输入 Trace ID」，不要编造排查结果。`;

export const PITFALL_ITEMS: Array<{ doNot: string; why: string }> = [
  {
    doNot: '不要从 POST chat_completion/ 的顶层 body 读 trace_id',
    why: 'context 随 POST session_content/ 写入用户消息 property.extra.context，chat_completion 只传 session_code。',
  },
  {
    doNot: '不要把 trace_id 放进 requestOptions.data 或 HTTP Header',
    why: 'data 会附加到所有 GET/POST（含会话列表），且不会挂到消息上，刷新后上下文丢失；Header 只适合认证与租户。',
  },
  {
    doNot: '不要把整段原始日志塞进 requestOptions.context',
    why: 'context 只传轻量业务标识（如 trace_id / service / page），后台拿到 ID 后再实时查日志接口。',
  },
  {
    doNot: '不要覆写落库的 session_content.content 来拼 Trace ID',
    why: '覆盖落库原文会导致聊天界面气泡被改写；只在送给 LLM 前的内存装配阶段改写，或谨慎使用 rendered_content。',
  },
  {
    doNot: '不要把 requestOptions.context 写成函数 () => ({ ... })',
    why: '当前版本函数形态的 context 会被静默忽略，必须把整个 requestOptions 写成 computed，让 context 本身是普通对象。',
  },
];

export const welcomeContextGuideSections: SourceGuideSection[] = [
  {
    id: 'flow',
    label: '数据流与版本',
    notes: [
      '小鲸最低要求 @blueking/ai-blueking >= 2.1.4（2.1.4-beta.15 引入 requestOptions.context），推荐直接锁 3.1.1 + chat-helper 3.1.0 + chat-x 3.1.2-beta.2。',
      '欢迎区 #welcome 插槽仅在空会话（无消息）时渲染；如需打开小鲸必见欢迎按钮，可结合 alwaysCreateNewSession 或新建空会话。',
      '有历史消息后按钮消失，用户直接在输入框说「日志分析」依然会自动带上最新 requestOptions.context。',
    ],
    blocks: [
      {
        title: '端到端数据流',
        desc: 'Trace 切换 → computed requestOptions.context → POST session_content/ → 后台二开组装 Prompt',
        code: DATA_FLOW_DIAGRAM,
      },
      {
        title: 'POST session_content/ 请求体（后台实际读取）',
        fileHint: 'Network -> session_content/',
        desc: 'context 由前端自动转换为结构化数组并合并到 property.extra.context。',
        code: SESSION_CONTENT_PAYLOAD_JSON,
      },
    ],
  },
  {
    id: 'frontend',
    label: '前端接入（方案 A）',
    notes: [
      '整份 requestOptions 必须用 computed 包裹，context 字段本身保持普通对象，不要传函数。',
      '点击按钮调用 sendMessage("日志分析")，用户气泡保持简洁，trace_id 通过 property.extra.context 透传。',
    ],
    blocks: [
      {
        title: 'Vue3 完整接入代码',
        fileHint: 'TraceDetailPage.vue',
        desc: '#welcome 动态按钮 + computed requestOptions.context',
        code: FRONTEND_VUE3_CODE,
      },
    ],
  },
  {
    id: 'backend',
    label: '后端二次开发',
    notes: [
      '官方 Chat Agent 不会自动用 extra.context 改写 Prompt，这是后台二次开发的核心落点。',
      '优先用 __key / __value 从 extra.context 取数，与 aidev_agent/services/command_handler.py 保持一致。',
      '只改送给模型的内存消息，不要修改落库 content。',
    ],
    blocks: [
      {
        title: '普通提问（「日志分析」）抽取上下文并组装 Prompt',
        fileHint: 'aidev_agent / 插件二开',
        desc: '兼容 ChatPrompt.extra 与原始 property.extra，仅在 LLM 输入侧注入当前页 Trace 信息。',
        code: BACKEND_EXTRACT_AND_PROMPT_PY,
      },
      {
        title: '快捷指令（CommandHandler）二开参考',
        fileHint: 'aidev_agent/services/command_handler.py',
        desc: '当同时使用快捷指令（extra.command）时，按 command 路由并渲染 Jinja2 模板。',
        code: BACKEND_COMMAND_HANDLER_PY,
      },
      {
        title: 'AIDev 系统提示词模板',
        fileHint: 'AIDev 平台 · 系统提示词',
        desc: '配合后台拼装逻辑，确保模型明确遵守「直接使用 trace_id、缺失时说明缺上下文」规则。',
        code: SYSTEM_PROMPT_TEMPLATE,
      },
    ],
  },
];
