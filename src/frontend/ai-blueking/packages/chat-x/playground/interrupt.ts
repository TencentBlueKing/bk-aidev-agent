/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { APPROVAL_STATUS, InterruptReason, MessageRole, MessageStatus } from '../src';

import type {
  AIDevToolApprovalInterrupt,
  AIDevToolApprovalResume,
  Interrupt,
  InterruptMessage,
  InterruptResult,
  Message,
  RunFinishedOutcome,
  UserQuestionInterrupt,
  UserQuestionResume,
} from '../src';

type ApprovalInterruptOptions = {
  id: string;
  message?: string;
  sn: string;
  status: APPROVAL_STATUS;
  title?: string;
  toolArgs?: Record<string, unknown>;
  toolCallId?: string;
};

/** 短参数：JSON ≤3 行，参数区不出现展开/收起 */
const MOCK_TOOL_ARGS_SHORT: Record<string, unknown> = {
  a: 1,
  b: 2,
};

/** 长参数：JSON >3 行，用于验证参数区折叠/展开 */
const MOCK_TOOL_ARGS_LONG: Record<string, unknown> = {
  algorithm: 'bubble_sort',
  language: 'typescript',
  optimization: {
    early_exit: true,
    cocktail: false,
  },
  dataset: {
    size: 10000,
    distribution: 'partially_sorted',
    seed: {
      size: 10000,
      distribution: 'partially_sorted',
      seed: {
        size: 10000,
        distribution:
          'partially_sortedpartially_sortedpartially_sortedpartially_sortedpartially_sortedpartially_sortedpartially_sortedpartially_sortedpartially_sorted',
        seed: 42,
      },
    },
  },
  benchmarks: [
    { name: 'random', expected_ms: 120 },
    { name: 'nearly_sorted', expected_ms: 30 },
    { name: 'reversed', expected_ms: 200 },
  ],
  notes: '请重点评审提前终止标志位与边界条件处理是否正确',
};

/** 构造 AI Dev 工具审批类 Interrupt */
const createApprovalInterrupt = (options: ApprovalInterruptOptions): AIDevToolApprovalInterrupt => ({
  id: options.id,
  reason: InterruptReason.AIDevToolApproval,
  toolCallId: options.toolCallId ?? `tool_call_${options.id}`,
  message: options.message ?? '算法方案评审单需要您关注',
  metadata: {
    ticket: {
      approvers: ['张三', '李四', '王五'],
      sn: options.sn,
      status: options.status,
      submit_time: '2026-04-24 14:30:15',
      title: options.title ?? '算法方案评审单',
      url: `https://example.com/review-tickets/${options.sn}`,
    },
    // 未传 toolArgs 时不写入字段，方便覆盖「无参数不渲染」场景
    ...(options.toolArgs ? { toolArgs: options.toolArgs } : {}),
  },
});

type InterruptMessageContent = InterruptMessage['content'];

/** 构造 InterruptMessage.content，字段与 InterruptMessage 类型对齐 */
const createInterruptContent = (
  interrupt: Interrupt,
  outcome: RunFinishedOutcome,
  extras?: Pick<InterruptMessageContent, 'result' | 'runId' | 'threadId'>,
): InterruptMessageContent => ({
  message: interrupt.message,
  runId: extras?.runId ?? `run_${interrupt.id}`,
  threadId: extras?.threadId ?? `thread_${interrupt.id}`,
  outcome,
  result: extras?.result,
});

/** 单场景：[引导 Assistant, InterruptMessage] */
const createInterruptScenario = (params: {
  interrupt: Interrupt;
  intro: string;
  outcome: RunFinishedOutcome;
  result?: InterruptResult;
  scenarioId: string;
  status?: MessageStatus;
}): Message[] => {
  const { scenarioId, intro, interrupt, outcome, status = MessageStatus.Complete, result } = params;

  return [
    {
      id: `msg_${scenarioId}_intro`,
      messageId: `msg_${scenarioId}_intro`,
      role: MessageRole.Assistant,
      content: intro,
      status: MessageStatus.Complete,
    },
    {
      id: `msg_${scenarioId}_interrupt`,
      messageId: `msg_${scenarioId}_interrupt`,
      role: MessageRole.Interrupt,
      status,
      content: createInterruptContent(interrupt, outcome, { result }),
    },
  ];
};

// —— 场景 1：待审批 + 长参数（可展开/收起）——
const pendingInterrupt = createApprovalInterrupt({
  id: 'interrupt_pending',
  sn: 'REV-2026-04-24-001',
  status: APPROVAL_STATUS.PENDING,
  message: '算法方案评审单正在评审中',
  toolArgs: MOCK_TOOL_ARGS_LONG,
});
const pendingScenario = createInterruptScenario({
  scenarioId: 'interrupt_pending',
  intro: '【待审批 · 长参数】已生成算法方案，关联评审单待您处理：',
  interrupt: pendingInterrupt,
  outcome: { type: 'interrupt', interrupts: [pendingInterrupt] },
  status: MessageStatus.Pending,
});

// —— 场景 2：草稿（与 pending 同属待审批交互）+ 长参数 ——
const draftInterrupt = createApprovalInterrupt({
  id: 'interrupt_draft',
  sn: 'REV-2026-04-24-000',
  status: APPROVAL_STATUS.DRAFT,
  message: '算法方案评审单草稿待提交审批',
  toolArgs: MOCK_TOOL_ARGS_LONG,
});
const draftScenario = createInterruptScenario({
  scenarioId: 'interrupt_draft',
  intro: '【草稿 · 长参数】评审单处于草稿态，交互同待审批：',
  interrupt: draftInterrupt,
  outcome: { type: 'interrupt', interrupts: [draftInterrupt] },
  status: MessageStatus.Pending,
});

// —— 场景 3：已批准 + 短参数（无展开）——
const approvedInterrupt = createApprovalInterrupt({
  id: 'interrupt_approved',
  sn: 'REV-2026-04-24-002',
  status: APPROVAL_STATUS.APPROVED,
  message: '算法方案评审单已通过',
  toolArgs: MOCK_TOOL_ARGS_SHORT,
});
const approvedScenario = createInterruptScenario({
  scenarioId: 'interrupt_approved',
  intro: '【已批准 · 短参数】评审单已通过，可继续后续流程：',
  interrupt: approvedInterrupt,
  outcome: { type: 'interrupt', interrupts: [approvedInterrupt] },
});

// —— 场景 4：已拒绝 + 短参数 ——
const rejectedInterrupt = createApprovalInterrupt({
  id: 'interrupt_rejected',
  sn: 'REV-2026-04-24-003',
  status: APPROVAL_STATUS.REJECTED,
  message: '算法方案评审单已被拒绝',
  toolArgs: MOCK_TOOL_ARGS_SHORT,
});
const rejectedScenario = createInterruptScenario({
  scenarioId: 'interrupt_rejected',
  intro: '【已拒绝 · 短参数】评审单未通过，请根据意见调整后重提：',
  interrupt: rejectedInterrupt,
  outcome: { type: 'interrupt', interrupts: [rejectedInterrupt] },
});

// —— 场景 5：已取消 + 短参数 ——
const cancelledInterrupt = createApprovalInterrupt({
  id: 'interrupt_cancelled',
  sn: 'REV-2026-04-24-004',
  status: APPROVAL_STATUS.CANCELLED,
  message: '算法方案评审单已取消',
  toolArgs: MOCK_TOOL_ARGS_SHORT,
});
const cancelledScenario = createInterruptScenario({
  scenarioId: 'interrupt_cancelled',
  intro: '【已取消 · 短参数】该评审单已被发起人取消：',
  interrupt: cancelledInterrupt,
  outcome: { type: 'interrupt', interrupts: [cancelledInterrupt] },
});

// —— 场景 6：已撤销 · 无参数（不渲染参数区）——
const revokedInterrupt = createApprovalInterrupt({
  id: 'interrupt_revoked',
  sn: 'REV-2026-04-24-005',
  status: APPROVAL_STATUS.REVOKED,
  message: '算法方案评审单已撤销',
});
if (revokedInterrupt.metadata) {
  revokedInterrupt.metadata.ticket.approvers = [];
}
const revokedScenario = createInterruptScenario({
  scenarioId: 'interrupt_revoked',
  intro: '【已撤销 · 无参数】该评审单已由发起人自行撤销：',
  interrupt: revokedInterrupt,
  outcome: { type: 'interrupt', interrupts: [revokedInterrupt] },
});

// —— 场景 7：已过期 + 短参数 ——
const expiredInterrupt = createApprovalInterrupt({
  id: 'interrupt_expired',
  sn: 'REV-2026-04-24-007',
  status: APPROVAL_STATUS.EXPIRED,
  message: '算法方案评审单已过期',
  toolArgs: MOCK_TOOL_ARGS_SHORT,
});
const expiredScenario = createInterruptScenario({
  scenarioId: 'interrupt_expired',
  intro: '【已过期 · 短参数】评审单已超过审批时效：',
  interrupt: expiredInterrupt,
  outcome: { type: 'interrupt', interrupts: [expiredInterrupt] },
});

// —— 场景 8：已废弃 + 短参数 ——
const abandonedInterrupt = createApprovalInterrupt({
  id: 'interrupt_abandoned',
  sn: 'REV-2026-04-24-008',
  status: APPROVAL_STATUS.ABANDONED,
  message: '算法方案评审单已废弃',
  toolArgs: MOCK_TOOL_ARGS_SHORT,
});
const abandonedScenario = createInterruptScenario({
  scenarioId: 'interrupt_abandoned',
  intro: '【已废弃 · 短参数】评审单已被废弃，无法继续流转：',
  interrupt: abandonedInterrupt,
  outcome: { type: 'interrupt', interrupts: [abandonedInterrupt] },
});

// —— 场景 9：outcome.success 回显审批单（短参数）——
const resumedScenario = createInterruptScenario({
  scenarioId: 'interrupt_resumed',
  intro: '【已处理 · success 回显】您已确认关注该评审单，Agent 将继续执行：',
  interrupt: createApprovalInterrupt({
    id: 'interrupt_resumed',
    sn: 'REV-2026-04-24-006',
    status: APPROVAL_STATUS.PENDING,
    toolArgs: MOCK_TOOL_ARGS_SHORT,
  }),
  outcome: { type: 'success' },
  result: {
    interruptId: 'interrupt_resumed',
    reason: InterruptReason.AIDevToolApproval,
    status: 'resolved',
    payload: {
      metadata: {
        ticket: {
          approvers: ['张三', '李四', '王五'],
          sn: 'REV-2026-04-24-006',
          status: APPROVAL_STATUS.APPROVED,
          submit_time: '2026-04-24 14:30:15',
          title: '算法方案评审单',
          url: 'https://example.com/review-tickets/REV-2026-04-24-006',
        },
        toolArgs: MOCK_TOOL_ARGS_SHORT,
      },
    },
  } satisfies AIDevToolApprovalResume,
});

// —— 场景 7：不支持的中断类型（走兜底文案）——
const unsupportedInterrupt: Interrupt = {
  id: 'interrupt_unsupported',
  reason: 'unknown_reason' as InterruptReason,
  toolCallId: 'tool_call_unsupported',
  message: '暂不支持的中断类型示例',
};
const unsupportedScenario = createInterruptScenario({
  scenarioId: 'interrupt_unsupported',
  intro: '【兜底】以下中断类型暂未实现专用卡片：',
  interrupt: unsupportedInterrupt,
  outcome: { type: 'interrupt', interrupts: [unsupportedInterrupt] },
});

// —— 场景 8：用户回答问题（待回答，outcome.interrupt，渲染在 chat-input 上方）——
const userQuestionInterrupt: UserQuestionInterrupt = {
  id: 'interrupt_user_question',
  reason: InterruptReason.UserQuestion,
  toolCallId: 'tool_call_user_question',
  message: '选择冒泡排序方案',
  metadata: {
    // 注意：不在 mock 中放 others 选项，由前端为每题自动追加 Others 输入项
    questions: [
      {
        header: '选择冒泡排序方案',
        multiSelect: false,
        question: '请选择你想要的冒泡排序算法方案',
        options: [
          { label: 'A', description: '方案1：基础冒泡排序 - 最经典实现，易于理解，适合教学演示' },
          { label: 'B', description: '方案2：优化版冒泡排序 - 加入标志位提前终止，适合部分有序数据' },
          { label: 'C', description: '方案3：双向冒泡排序（鸡尾酒排序）- 正向反向交替，适合数据分布在两端' },
        ],
      },
      {
        header: '选择冒泡排序方案',
        multiSelect: true,
        question: '请选择语言（可多选）',
        options: [
          { label: 'Java', description: 'Java' },
          { label: 'Python', description: 'Python' },
          { label: 'Go', description: 'Go' },
        ],
      },
      {
        header: '选择冒泡排序方案',
        multiSelect: false,
        question: '请选择实现方式',
        options: [{ label: 'best', description: '最佳方案' }],
      },
    ],
  },
};
const userQuestionScenario = createInterruptScenario({
  scenarioId: 'interrupt_user_question',
  intro: '【待回答】请完成以下问题后继续：',
  interrupt: userQuestionInterrupt,
  outcome: { type: 'interrupt', interrupts: [userQuestionInterrupt] },
  status: MessageStatus.Pending,
});

// —— 场景 9：用户回答问题（已回答，outcome.success，会话内回显）——
// 与场景 8 的问题对齐，覆盖单选 / 多选 / Others 自定义输入三种回答形态
const userQuestionAnsweredResult: UserQuestionResume = {
  interruptId: 'interrupt_user_question_answered',
  reason: InterruptReason.UserQuestion,
  status: 'resolved',
  payload: {
    answers: [
      // 单选：命中预设选项
      {
        question: '请选择你想要的冒泡排序算法方案',
        multiSelect: false,
        answer: [{ label: 'B', description: '方案2：优化版冒泡排序 - 加入标志位提前终止，适合部分有序数据' }],
      },
      // 多选：命中多个预设选项
      {
        question: '请选择语言（可多选）',
        multiSelect: true,
        answer: [
          { label: 'Java', description: 'Java' },
          { label: 'Python', description: 'Python' },
        ],
      },
      // Others：用户自定义输入，label 为 others，description 为输入文本
      {
        question: '请选择实现方式',
        multiSelect: false,
        answer: [{ label: 'others', description: '希望提供 TypeScript 泛型版本，并附带单元测试' }],
      },
    ],
  },
};
const userQuestionAnsweredScenario = createInterruptScenario({
  scenarioId: 'interrupt_user_question_answered',
  intro: '【已处理】您已回答以下问题：',
  interrupt: {
    id: 'interrupt_user_question_answered',
    reason: InterruptReason.UserQuestion,
    toolCallId: 'tool_call_user_question_answered',
    message: '回答内容',
    metadata: { questions: [] },
  } as UserQuestionInterrupt,
  outcome: { type: 'success' },
  result: userQuestionAnsweredResult,
});

/** playground 审批单据专用 mock：覆盖全状态 + 长/短/无参数展示 */
export const MOCK_APPROVAL_MESSAGES: Message[] = [
  ...pendingScenario,
  ...draftScenario,
  ...approvedScenario,
  ...rejectedScenario,
  ...cancelledScenario,
  ...revokedScenario,
  ...expiredScenario,
  ...abandonedScenario,
  ...resumedScenario,
];

/** playground 全量中断 mock：审批 + resume + 兜底 + 用户回答问题 */
export const MOCK_INTERRUPT_MESSAGES: Message[] = [
  ...MOCK_APPROVAL_MESSAGES,
  ...unsupportedScenario,
  ...userQuestionScenario,
  ...userQuestionAnsweredScenario,
];
