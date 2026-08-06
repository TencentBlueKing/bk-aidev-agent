# HITL 人机协同（中断与恢复）

> 适用版本：ai-blueking `2.2.0-beta.4+` / chat-x `0.0.46-beta.3+` / chat-helper `0.0.12-beta.2+`

Human-in-the-loop（HITL）让 Agent 在流式执行过程中**暂停**，把控制权交回用户，等用户处理后再**恢复**执行。当前覆盖三类场景：

| 场景 | 中断原因 / 操作 | 用户动作 | UI 组件（chat-x） |
|------|-----------------|----------|-------------------|
| **工具审批** | `InterruptReason.AIDevToolApproval`（`'aidev:tool_approval'`） | 等待审批 / 取消审批 | `ToolApprovalCard`（内部，经 `InterruptMessageRender` 渲染） |
| **用户提问** | `InterruptReason.UserQuestion`（`'aidev:user_question'`） | 回答问题 / 跳过 / 直接在输入框作答 | `UserQuestionCard` / `UserQuestionAnsweredCard` |
| **流程节点失败** | `InterruptResumeOperation.FlowNodeRetry` / `FlowNodeSkip` | 重试 / 跳过失败节点 | Flow-agent 节点操作（`useFlowNodeActions`） |

**核心结论**：ChatBot / AIBlueking 已内置完整 HITL 能力，**开箱即用**。唯一需要业务方注意的是——**自定义 `#message` 插槽时必须透传 `onInterruptResume`**（见下方 [关键陷阱](#关键陷阱message-插槽必须透传-oninterruptresume)），否则所有恢复动作失效。原子组件模式则需自行接线。

> 📂 **可运行范例**（当前唯一的 HITL 示例集中在 chat-x playground）：
> - `packages/chat-x/playground/chat-bot-new.vue` — `ChatContainer` 全量接线，注释中给出 `#message` / `#group` / `#interruptQuestion` 三个插槽的参考实现（含 `InterruptMessageRender`、`UserQuestionChoice`）
> - `packages/chat-x/playground/interrupt.ts` — 工具审批 / 用户提问中断消息的真实数据构造（对齐 `AIDevToolApprovalInterrupt` / `InterruptMessage.content`）
> - 生产恢复逻辑：`packages/ai-blueking/src/components/composables/use-interrupt-resume.ts`（playground 的 `handleInterruptResume` 仅打印日志）
>
> 见 [Playground 实例索引](playground-examples.md)。

---

## 一、协议数据模型（chat-helper 层）

中断不是独立的 SSE 事件类型，而是标准 `RUN_FINISHED` 事件的一种**结果（outcome）**。

```typescript
import {
  InterruptReason,          // AIDevToolApproval / UserQuestion
  ResumeStatus,             // Resolved / Cancelled
  UserOperation,            // FlowNodeRetry / FlowNodeSkip / ApprovalCancel
  RunFinishedOutcomeType,   // Success / Interrupt
  ApprovalInterruptTicketStatus,
  type IResume,
  type IInterrupt,
  type IApprovalInterrupt,
  type IUserQuestionInterrupt,
  type IRunFinishedEvent,
  type IInterruptMessage,
} from '@blueking/chat-helper';
```

### 中断结构

```typescript
interface IInterrupt<T extends InterruptReason, P extends Record<string, unknown>> {
  id: string;
  reason: T;
  message?: string;
  toolCallId?: string;
  responseSchema?: JSONSchema4;
  expiresAt?: string;
  metadata?: P;
}

// 工具审批中断：metadata.ticket 描述审批单
type IApprovalInterrupt = IInterrupt<InterruptReason.AIDevToolApproval, {
  ticket: { approvers: string[]; sn: string; status: ApprovalInterruptTicketStatus;
            submit_time: string; title: string; url: string };
}>;

// 用户提问中断：metadata.questions 描述问题列表
type IUserQuestionInterrupt = IInterrupt<InterruptReason.UserQuestion, {
  questions: { header: string; question: string; multiSelect?: boolean;
               options?: { label: string; description: string }[] }[];
}>;
```

### 恢复负载

```typescript
interface IResume {
  interruptId: string;
  status: ResumeStatus;               // 'resolved' | 'cancelled'
  payload?: {
    answers: { question: string; multiSelect?: boolean;
               answer: { label: string; description: string }[] }[];
  };
}
```

### 中断消息（会话内持久化 / 回显）

```typescript
// RUN_FINISHED 事件同时承载 outcome（中断信息）与 result（恢复结果）
interface IRunFinishedEvent {
  type: EventType.RunFinished;
  runId: number;
  threadId: string;
  result?: IResume;
  outcome?:
    | { type: RunFinishedOutcomeType.Success }
    | { type: RunFinishedOutcomeType.Interrupt;
        interrupts: Array<IApprovalInterrupt | IUserQuestionInterrupt> };
}

// 中断被建模为一条 MessageRole.Interrupt 消息，content 即上面的事件
interface IInterruptMessage {
  role: MessageRole.Interrupt;
  content: IRunFinishedEvent;
  // ...BaseMessage 其余字段
}
```

### 事件流转（AGUIProtocol 内部）

1. 流式中收到 `RUN_FINISHED` 且 `outcome.type === Interrupt` → `handleRunFinishedEvent` 追加一条 `MessageRole.Interrupt`、`status: Pending` 的消息。
2. 后续针对同一中断的 `RUN_FINISHED(Success)`、`handleToolCallResultEvent` 或 `CustomEventName.ApprovalResult` 自定义事件 → 就地更新该消息的 `content.result`，把 `outcome.type` 翻成 `Success`、状态置 `Complete`。这样中断卡片会从「待处理」变成「只读回显」。

### 中断消息数据示例（可直接构造 mock 调试）

**工具审批中断**（`status: Pending`，等待 resume）：

```javascript
{
  id: 'msg_interrupt', messageId: 'msg_interrupt',
  role: MessageRole.Interrupt,
  status: MessageStatus.Pending,
  content: {
    message: '算法方案评审单需要您关注',
    runId: 'run_x', threadId: 'thread_x',
    outcome: {
      type: 'interrupt',
      interrupts: [{
        id: 'interrupt_pending',
        reason: InterruptReason.AIDevToolApproval,   // 'aidev:tool_approval'
        toolCallId: 'tool_call_interrupt_pending',
        message: '算法方案评审单正在评审中',
        metadata: {
          ticket: {
            approvers: ['张三', '李四'],
            sn: 'REV-2026-04-24-001',
            status: 'pending',                        // APPROVAL_STATUS
            submit_time: '2026-04-24 14:30:15',
            title: '算法方案评审单',
            url: 'https://example.com/review-tickets/REV-2026-04-24-001',
          },
        },
      }],
    },
    // result: 未 resume 时为空；resume 后置入 IResume 且 outcome.type 变 'success'
  },
}
```

**用户提问中断**（含单选 / 多选，前端会为每题自动追加「其他」输入项）：

```javascript
{
  id: 'interrupt_user_question',
  reason: InterruptReason.UserQuestion,               // 'aidev:user_question'
  toolCallId: 'tool_call_user_question',
  message: '选择冒泡排序方案',
  metadata: {
    questions: [
      { header: '选择冒泡排序方案', multiSelect: false,
        question: '请选择你想要的冒泡排序算法方案',
        options: [
          { label: 'A', description: '方案1：基础冒泡排序' },
          { label: 'B', description: '方案2：优化版冒泡排序' },
        ] },
      { header: '选择冒泡排序方案', multiSelect: true,
        question: '请选择语言（可多选）',
        options: [{ label: 'Java', description: 'Java' }, { label: 'Python', description: 'Python' }] },
    ],
  },
}
```

**用户已作答的回显结果**（`outcome.type: 'success'`，`content.result` 为下列 `UserQuestionResume`）：

```javascript
{
  interruptId: 'interrupt_user_question',
  reason: InterruptReason.UserQuestion,
  status: 'resolved',                                 // 'resolved' | 'cancelled'
  payload: {
    answers: [
      { question: '请选择你想要的冒泡排序算法方案', multiSelect: false,
        answer: [{ label: 'B', description: '方案2：优化版冒泡排序' }] },
      { question: '请选择语言（可多选）', multiSelect: true,
        answer: [{ label: 'Java', description: 'Java' }, { label: 'Python', description: 'Python' }] },
      // 「其他」自定义输入：label 为 others，description 为用户输入文本
    ],
  },
}
```

---

## 二、恢复契约（chat-x / ai-blueking 层）

chat-helper **本身没有 `onInterruptResume` 方法**——它只暴露底层原语 `agent.streamRequest` / `agent.userOperationStreamRequest` 与 `IResume` 结构。真正给 UI 用的统一恢复回调 `OnInterruptResume` 定义在 chat-x：

```typescript
import {
  InterruptReason,
  InterruptResumeOperation,   // ApprovalCancel / FlowNodeRetry / FlowNodeSkip
  type OnInterruptResume,
  type InterruptResume,
  type ToolApprovalResume,
  type FlowNodeResume,
  type UserQuestionResume,
} from '@blueking/chat-x';

type OnInterruptResume = (payload: InterruptResume, interrupt?: Interrupt) => Promise<void> | void;

type InterruptResume = FlowNodeResume | ToolApprovalResume | UserQuestionResume;

// 取消工具审批
type ToolApprovalResume = {
  operation: InterruptResumeOperation.ApprovalCancel;
  payload: { interrupt_id: number | string };
};

// 流程节点重试 / 跳过
type FlowNodeResume = {
  operation: InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;
  payload: { node_id: string; task_id: number };
};

// 用户提问作答（BaseResume + answers）
type UserQuestionResume = BaseResume<InterruptReason.UserQuestion, {
  answers: UserQuestionAnswerItem[];
}>;
```

`OnInterruptResume` 是所有恢复动作的唯一入口：审批卡片的「取消审批」、用户提问卡片的「完成 / 跳过」、流程节点的「重试 / 跳过」都调用它。ChatBot / AIBlueking 内部（`use-interrupt-resume.ts`）把这个回调翻译成 chat-helper 的原语：

- `FlowNode*` / `ApprovalCancel` → `agent.userOperationStreamRequest(sessionCode, operation, payload)`（POST `user_operation/`）
- 用户提问作答 → `agent.streamRequest({ sessionCode, resume: IResume, input? })`（把 `resume` 放进 `chat_completion/` 的 `execute_kwargs.resume`）

---

## 三、UI 组件（chat-x）

> ⚠️ 命名注意：**不存在**名为 `AIDevToolApproval` 或 `UserQuestion` 的导出。真实组件是 `ToolApprovalCard`（内部，不单独 re-export）与 `UserQuestionCard` 系列。

| 导出 | 说明 |
|------|------|
| `InterruptMessageRender` | 中断消息渲染器（`interrupt-message` 默认导出）。`MessageRender` 遇到 `MessageRole.Interrupt` 时自动调用。props：`Partial<InterruptMessage> & { onInterruptResume? }`，slot：`answeredQuestion` |
| `ToolApprovalCard` | 工具审批卡片（内部）。展示审批单、`isPendingApproval && !readonly && !isShareContext` 时显示「取消审批」；`cancelling` 标志防重复提交 |
| `UserQuestionCard` | 用户提问卡片。「完成」走 `buildResolvePayload()`（`status: resolved`），「跳过」走 `buildSkipPayload()`（`status: cancelled`）。slot：`question({ question, qIndex, answer, setAnswer, confirm })` |
| `UserQuestionAnsweredCard` | 已作答只读回显。props：`{ answers; status?: 'cancelled' \| 'resolved' }`，slot：`answer({ index, item, status })` |
| `UserQuestionChoice` / `UserQuestionOption` | 选项子组件 |
| `useUserQuestion` | 聚合每题答案：`{ questions, answeredCount, totalCount, completed, getAnswer, setAnswer, buildResolvePayload, buildSkipPayload }`；`completed` 要求所有问题都已作答 |
| `buildSkipResumePayload(interrupt?)` | 生成「跳过 / 直接输入」恢复负载（`status: cancelled, payload:{ answers: [] }`），供输入框旁路作答使用 |
| `OTHERS_OPTION_LABEL` / `toLetter` | 「其他」选项文案 / 序号转字母工具 |

**渲染位置差异**：工具审批中断在**会话流内**内联渲染；用户提问中断**不在流内**渲染，而是作为**浮层卡片**出现在输入框上方（由 `useMessageGroup` 的 `activeUserQuestionInterrupt` 定位最新未答的提问）。

---

## 四、集成方式

### 4.1 ChatBot / AIBlueking —— 开箱即用

无需任何额外代码，HITL 全链路已接好：

```vue
<AIBlueking :url="apiUrl" />
<!-- 或 -->
<ChatBot :url="apiUrl" />
```

审批卡片、提问浮层、流程节点重试/跳过按钮会自动出现并可交互。

#### 关键陷阱：`#message` 插槽必须透传 `onInterruptResume`

自定义 `#message` 插槽后，插槽作用域**新增了第三个参数 `onInterruptResume`**（除既有的 `message`、`messageToolsStatus`）。必须把它透传给 `MessageRender`，否则中断卡片渲染出来但**所有恢复动作失效**（审批无法取消、提问无法作答、节点无法重试/跳过）。

```vue
<!-- ❌ 错误：HITL 恢复动作全部失效 -->
<template #message="{ message, messageToolsStatus }">
  <MessageRender :message="message" :message-tools-status="messageToolsStatus" />
</template>

<!-- ✅ 正确：透传 onInterruptResume（连同用户消息工具回调一并透传） -->
<template #message="{ message, messageToolsStatus, onInterruptResume }">
  <MessageRender
    :message="message"
    :message-tools-status="messageToolsStatus"
    :on-interrupt-resume="onInterruptResume"
    :on-action="tool => handleUserAction(tool, message)"
    :on-input-confirm="(content, docSchema) => handleUserInputConfirm(message, content, docSchema)"
    :on-shortcut-confirm="formModel => handleUserShortcutConfirm(message, formModel)"
    :tippy-options="messageToolsTippyOptions"
  />
</template>
```

> 这是既有「[`#message` 插槽透传](../SKILL.md)」陷阱的延伸——用户消息工具回调 + `onInterruptResume` 都走 `#message` 插槽，缺一不可。

### 4.2 原子组件模式（chat-x + chat-helper 自行组装）

需要自己把 `onInterruptResume` 接到 `MessageContainer` / `ChatContainer`，并实现恢复逻辑。

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-groups="messageGroups"
    :on-interrupt-resume="handleInterruptResume"
    v-model:selected-user-messages="selectedUserMessages"
  />
  <ChatInput
    v-model="userInput"
    :message-status="messageStatus"
    :on-send-message="handleSend"
  />
</template>

<script setup lang="ts">
import {
  InterruptReason,
  InterruptResumeOperation,
  buildSkipResumePayload,
  type OnInterruptResume,
  type InterruptResume,
  type Interrupt,
} from '@blueking/chat-x';
import { ResumeStatus, UserOperation } from '@blueking/chat-helper';

const { agent, session } = chatHelper;

// 统一恢复入口：把 chat-x 的 InterruptResume 翻译成 chat-helper 原语
const handleInterruptResume: OnInterruptResume = async (payload, interrupt) => {
  const sessionCode = session.current.value?.sessionCode;
  if (!sessionCode) return;

  // 1) 工具审批取消 / 流程节点重试 / 跳过 → user_operation
  if (
    payload.operation === InterruptResumeOperation.ApprovalCancel ||
    payload.operation === InterruptResumeOperation.FlowNodeRetry ||
    payload.operation === InterruptResumeOperation.FlowNodeSkip
  ) {
    const opMap = {
      [InterruptResumeOperation.ApprovalCancel]: UserOperation.ApprovalCancel,
      [InterruptResumeOperation.FlowNodeRetry]: UserOperation.FlowNodeRetry,
      [InterruptResumeOperation.FlowNodeSkip]: UserOperation.FlowNodeSkip,
    } as const;
    await agent.userOperationStreamRequest(sessionCode, opMap[payload.operation], payload.payload);
    return;
  }

  // 2) 用户提问作答 → streamRequest 携带 resume
  await agent.streamRequest({
    sessionCode,
    resume: {
      interruptId: interrupt?.id ?? '',
      status: ResumeStatus.Resolved,
      payload: { answers: payload.payload.answers },
    },
  });
};
</script>
```

### 4.3 插槽自定义参考实现（原子组件 / 深度定制）

以下三段是 `ChatContainer` 层做深度定制时的标准写法（与仓库 `chat-x/playground/chat-bot-new.vue` 一致）。**要点**：任何自渲染分支都要透传 `onInterruptResume`；用户提问中断（`InterruptReason.UserQuestion`）走 `InterruptMessageRender`。

```vue
<!-- ① #message：完全接管单条消息渲染（含中断消息分支） -->
<template #message="{ message, messageToolsStatus, onInterruptResume }">
  <MessageRender v-if="message.role === MessageRole.User" :message="message" />
  <template
    v-else-if="message.role === MessageRole.Interrupt
      && message.content.result?.reason === InterruptReason.UserQuestion"
  >
    <InterruptMessageRender v-bind="message" :on-interrupt-resume="onInterruptResume">
      <template #answeredQuestion="{ item }">{{ item }}</template>
    </InterruptMessageRender>
  </template>
  <MessageRender
    v-else
    :message="message"
    :message-tools-status="messageToolsStatus"
    :on-interrupt-resume="onInterruptResume"
  />
</template>

<!-- ② #group：按分组渲染（每组含多条消息），逐条透传回调 -->
<template #group="{ group }">
  <MessageRender
    v-for="(message, i) in group.messages"
    :key="i"
    :message="message"
    :on-interrupt-resume="handleInterruptResume"
    :on-input-confirm="(content, docSchema) => handleUserInputConfirm(message, content, docSchema)"
    :on-shortcut-confirm="formModel => handleUserShortcutConfirm(message, formModel)"
  />
</template>

<!-- ③ #interruptQuestion：自定义用户提问的作答 UI（用下拉替代默认选项列表） -->
<template #interruptQuestion="{ question, setAnswer, answer }">
  <MySelect
    v-if="question.multiSelect"
    :model-value="answer?.answer.at(0)?.label"
    @change="value => setAnswer(value
      ? { question: question.question, multiSelect: question.multiSelect,
          answer: [{ label: value, description: value }] }
      : undefined)"
    :options="question.options ?? []"
  />
  <UserQuestionChoice v-else :question="question" :on-answer="setAnswer" />
</template>
```

> `#interruptQuestion` 作用域参数：`{ question, qIndex, answer, setAnswer, confirm }`（`UserQuestionCardSlots['question']`）。`setAnswer(item | undefined)` 回传/清除某题答案，`UserQuestionChoice` 是内置选项组件。

---

## 五、工具审批流程

1. Agent 请求调用需审批的工具 → 后端返回 `RUN_FINISHED(outcome=Interrupt)`，含 `IApprovalInterrupt`（`metadata.ticket`）。
2. 会话流内出现 `ToolApprovalCard`，展示审批单标题、审批人、单号、状态、跳转链接。
3. 审批中（`status: PENDING/DRAFT`）时，SDK 通过 `agent.pollResumeSession()` 轮询 `GET session/{code}/is_resume/`：
   - 返回 `true` → 自动以 `resume: { interruptId, status: Resolved }` 重新发起 `streamRequest`，恢复执行。
   - 返回 `false` → 30 秒后重试（仅当会话仍为当前会话）。
4. 用户点「取消审批」→ `onInterruptResume({ operation: ApprovalCancel, payload: { interrupt_id } })` → `user_operation/`，随后停止轮询。
5. **分享 / 只读态**（`RenderMode.Share`）下取消按钮被禁用（`isShareContext`）。

---

## 六、用户提问流程

后端返回 `IUserQuestionInterrupt`（`metadata.questions`）。用户有两种作答方式：

**方式 A：在提问浮层卡片作答** —— 逐题选择/填写后点「完成」（`buildResolvePayload` → `status: resolved`）或「跳过」（`buildSkipPayload` → `status: cancelled`）。

**方式 B：直接在输入框输入** —— 用户不点卡片、直接在 `ChatInput` 打字发送。此时利用 `onSendMessage` 的**第三个参数**把普通发送转成一次「用自由文本作答」的恢复：

```typescript
// ChatInput 的 onSendMessage 现在支持第三参数
onSendMessage?: (
  message: UserMessage['content'],
  docSchema: TagSchema,
  options?: { interrupt?: Interrupt; payload?: InterruptResume },
) => Promise<void>;

// buildSkipResumePayload(interrupt) 生成 status:'cancelled' 的空答案负载，
// ChatBot 内部据此在发送用户输入的同时恢复被中断的提问。
```

⚠️ **自由文本不进 `answers`**：用户没有选择任何选项，`payload.answers` 必须保持 `[]`、`status` 保持 `'cancelled'`（等同跳过），文本只通过 `input` 传给后端。ChatBot 原样透传 chat-x 给的 skip payload，不做改写：

```typescript
// use-interrupt-resume.ts —— 自由文本恢复的最终负载
{ interruptId, reason: InterruptReason.UserQuestion, status: 'cancelled', payload: { answers: [] } }
// 同时 streamRequest({ sessionCode, resume, input: '用户输入的文本' })
```

后端据是否携带 `input` 区分「自由文本作答」与「纯跳过」。**不要**把自由文本包装成 `label:'others'` 的答案项——`others` 仅用于用户在卡片里主动选择「其他」并填写的场景。

ChatBot / AIBlueking 已内置该旁路逻辑，业务无需处理；原子模式下如需支持「输入框作答」，在 `handleSend` 中检测当前是否有活跃 UserQuestion 中断（`useMessageGroup().activeUserQuestionInterrupt`），有则携带 `buildSkipResumePayload` 结果调用恢复。

---

## 七、流程化智能体（Flow Agent）节点重试 / 跳过

BKFlow 流程节点失败后，可在节点上重试或跳过。逻辑在 chat-x 的 `useFlowNodeActions`（`components/chat-content/flow-agent-content/use-flow-node-actions.ts`）：

| 动作 | 触发条件 | 恢复调用 |
|------|----------|----------|
| **重试** | `node.convergedState === 'failed' && node.retryable` | `onInterruptResume({ operation: FlowNodeRetry, payload: { node_id, task_id } })` |
| **跳过** | `failed && node.skippable` | `onInterruptResume({ operation: FlowNodeSkip, payload: { node_id, task_id } })` |
| **详情** | 始终显示 | 打开节点详情（见 `onCustomTabChange` / `getFlowAgentTaskNodeInfo`） |

- 去重键 `task_id:node_id:retry`——重试计数变化会自动作废旧的 pending 态，节点再次失败可再次操作。
- 一个操作进行中时，另一个被禁用并提示「任务正在跳过中，不可重试」（反之亦然），进行中的按钮显示「重试中 / 跳过中」loading。
- **分享 / 只读态**（`hideResumeActions` 为真，通常由 `RenderMode.Share` 触发）：重试 / 跳过被过滤，仅保留「详情」——即「分享态开放流程智能体查看能力」。

节点详情数据默认经 `chatHelper.message.getFlowAgentTaskNodeInfo(task_id, node_id)` 获取；通过 AIBlueking / ChatBot 的 `onCustomTabChange(tab) => Promise` prop 可自定义该获取逻辑（返回值渲染进侧栏自定义 Tab）。相关 SDK 方法：`getFlowAgentTaskInfo`、`getFlowAgentTaskNodeInfo`、`retryFlowAgentTaskNode`、`skipFlowAgentTaskNode`、`userOperation`。

---

## 八、只读回显与分享态

- 中断被 `Resolved`/`Cancelled` 后，`InterruptMessageRender` 的 `resultRenderers` 会**只读回显**结果：工具审批 → `ToolApprovalCard readonly`；用户提问 → `UserQuestionAnsweredCard`（携带 `answers` + `status`）。
- `RenderMode.Share` 下：隐藏输入与交互元素、禁用审批取消、流程节点仅保留「详情」。因此分享出去的会话既能完整回看 HITL 过程，又不能误触发恢复动作。

---

## 参考

- [chat-helper SDK API](chat-helper-api.md) — `agent.streamRequest` / `userOperationStreamRequest` / `pollResumeSession`、`session.isResumeSession`、中断/恢复类型
- [chat-x 组件 API](chat-x-api.md) — `InterruptMessageRender` / `UserQuestionCard` / `useUserQuestion`、`OnInterruptResume`、`RenderMode`
- [ChatBot 组件 API](chatbot-api.md) — `#message` 插槽的 `onInterruptResume` 作用域参数
- [集成模式与示例](integration-patterns.md) — 渲染模式、侧栏自定义、standalone-mount
