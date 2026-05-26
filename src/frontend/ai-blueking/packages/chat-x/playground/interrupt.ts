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

import type { Interrupt, InterruptMessage, Message, RunFinishedOutcome } from '../src';

type ApprovalInterruptOptions = {
  id: string;
  message?: string;
  sn: string;
  status: APPROVAL_STATUS;
  title?: string;
  toolCallId?: string;
};

/** 构造 AI Dev 工具审批类 Interrupt */
const createApprovalInterrupt = (options: ApprovalInterruptOptions): Interrupt => ({
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
  result?: unknown;
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

// —— 场景 1：待审批（outcome.interrupt，消息 Pending，等待 resume）——
const pendingInterrupt = createApprovalInterrupt({
  id: 'interrupt_pending',
  sn: 'REV-2026-04-24-001',
  status: APPROVAL_STATUS.PENDING,
  message: '算法方案评审单正在评审中',
});
const pendingScenario = createInterruptScenario({
  scenarioId: 'interrupt_pending',
  intro: '【待审批】已生成算法方案，关联评审单待您处理：',
  interrupt: pendingInterrupt,
  outcome: { type: 'interrupt', interrupts: [pendingInterrupt] },
  status: MessageStatus.Pending,
});

// —— 场景 2：已批准（单据 approved，仍展示审批卡片）——
const approvedInterrupt = createApprovalInterrupt({
  id: 'interrupt_approved',
  sn: 'REV-2026-04-24-002',
  status: APPROVAL_STATUS.APPROVED,
  message: '算法方案评审单已通过',
});
const approvedScenario = createInterruptScenario({
  scenarioId: 'interrupt_approved',
  intro: '【已批准】评审单已通过，可继续后续流程：',
  interrupt: approvedInterrupt,
  outcome: { type: 'interrupt', interrupts: [approvedInterrupt] },
});

// —— 场景 3：已拒绝 ——
const rejectedInterrupt = createApprovalInterrupt({
  id: 'interrupt_rejected',
  sn: 'REV-2026-04-24-003',
  status: APPROVAL_STATUS.REJECTED,
  message: '算法方案评审单已被拒绝',
});
const rejectedScenario = createInterruptScenario({
  scenarioId: 'interrupt_rejected',
  intro: '【已拒绝】评审单未通过，请根据意见调整后重提：',
  interrupt: rejectedInterrupt,
  outcome: { type: 'interrupt', interrupts: [rejectedInterrupt] },
});

// —— 场景 4：已取消 ——
const cancelledInterrupt = createApprovalInterrupt({
  id: 'interrupt_cancelled',
  sn: 'REV-2026-04-24-004',
  status: APPROVAL_STATUS.CANCELLED,
  message: '算法方案评审单已取消',
});
const cancelledScenario = createInterruptScenario({
  scenarioId: 'interrupt_cancelled',
  intro: '【已取消】该评审单已被发起人撤销：',
  interrupt: cancelledInterrupt,
  outcome: { type: 'interrupt', interrupts: [cancelledInterrupt] },
});

// —— 场景 5：已撤销 ——
const revokedInterrupt = createApprovalInterrupt({
  id: 'interrupt_revoked',
  sn: 'REV-2026-04-24-005',
  status: APPROVAL_STATUS.REVOKED,
  message: '算法方案评审单已撤销',
});
revokedInterrupt.metadata!.ticket.approvers = [];
const revokedScenario = createInterruptScenario({
  scenarioId: 'interrupt_revoked',
  intro: '【已撤销】该评审单已由发起人自行撤销：',
  interrupt: revokedInterrupt,
  outcome: { type: 'interrupt', interrupts: [revokedInterrupt] },
});

// —— 场景 6：用户已 resume（outcome.success + result，不渲染中断卡片）——
const resumedScenario = createInterruptScenario({
  scenarioId: 'interrupt_resumed',
  intro: '【已处理】您已确认关注该评审单，Agent 将继续执行：',
  interrupt: createApprovalInterrupt({
    id: 'interrupt_resumed',
    sn: 'REV-2026-04-24-006',
    status: APPROVAL_STATUS.PENDING,
  }),
  outcome: { type: 'success' },
  result: {
    interruptId: 'interrupt_resumed',
    status: 'acknowledged',
    payload: { action: 'view_ticket' },
  },
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

/** playground 全量中断 mock：覆盖审批态 + resume 态 + 兜底态 */
export const MOCK_INTERRUPT_MESSAGES: Message[] = [
  ...pendingScenario,
  ...approvedScenario,
  ...rejectedScenario,
  ...cancelledScenario,
  ...revokedScenario,
  ...resumedScenario,
  ...unsupportedScenario,
];
