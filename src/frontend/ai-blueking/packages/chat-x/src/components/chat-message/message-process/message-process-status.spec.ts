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
import { APPROVAL_STATUS, InterruptReason, MessageContentType, MessageRole, MessageStatus } from '../../../ag-ui/types/constants';
import {
  isMessageGenerating,
  resolveProcessCollapseIndex,
  resolveProcessLabelKey,
  shouldShowMessageProcess,
} from './message-process-status';

import type { ActivityMessage, AssistantMessage, InterruptMessage, Message } from '../../../ag-ui/types';

const assistant: AssistantMessage = {
  id: 'assistant',
  messageId: 'assistant',
  role: MessageRole.Assistant,
  content: '回答',
  status: MessageStatus.Complete,
};
const reasoning: Message = { ...assistant, role: MessageRole.Reasoning, content: ['思考'] };
const info: Message = { ...assistant, role: MessageRole.Info };
const tool: Message = { ...assistant, role: MessageRole.Tool, toolCallId: 'call-1', duration: 0 };
const flow: ActivityMessage = {
  ...assistant,
  role: MessageRole.Activity,
  activityType: MessageContentType.FlowAgent,
  content: [],
};
const approval: InterruptMessage = {
  ...assistant,
  role: MessageRole.Interrupt,
  content: {
    outcome: {
      type: 'interrupt',
      interrupts: [{ id: 'approval', toolCallId: 'call-1', reason: InterruptReason.AIDevToolApproval }],
    },
  },
};

describe('message-process-status', () => {
  it('Streaming / StopLoading / Fetching / Pending 应该视为生成中', () => {
    expect(isMessageGenerating(MessageStatus.Streaming)).toBe(true);
    expect(isMessageGenerating(MessageStatus.StopLoading)).toBe(true);
    expect(isMessageGenerating(MessageStatus.Fetching)).toBe(true);
    expect(isMessageGenerating(MessageStatus.Pending)).toBe(true);
  });

  it('其余状态和空状态不应该视为生成中', () => {
    expect(isMessageGenerating(MessageStatus.Complete)).toBe(false);
    expect(isMessageGenerating(MessageStatus.Success)).toBe(false);
    expect(isMessageGenerating(MessageStatus.Error)).toBe(false);
    expect(isMessageGenerating(MessageStatus.Stop)).toBe(false);
    expect(isMessageGenerating(undefined)).toBe(false);
  });

  it('生成中应该显示处理中，终态文案应该看最后一条', () => {
    expect(resolveProcessLabelKey([{ status: MessageStatus.Complete }], true)).toBe('处理中');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Success }], false)).toBe('已完成');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Streaming }], false)).toBe('已完成');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Error }], false)).toBe('失败');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Stop }], false)).toBe('已停止');
    expect(resolveProcessLabelKey([{ status: MessageStatus.Disabled }], false)).toBe('已禁用');
  });

  it('中途工具失败但最终正常完成时应显示已完成', () => {
    expect(
      resolveProcessLabelKey(
        [{ status: MessageStatus.Complete }, { status: MessageStatus.Error }, { status: MessageStatus.Complete }],
        false,
      ),
    ).toBe('已完成');
  });

  it('助手组只要有消息就显示状态栏，其他组不显示', () => {
    expect(shouldShowMessageProcess({ type: MessageRole.Assistant, messages: [{}] })).toBe(true);
    expect(shouldShowMessageProcess({ type: MessageRole.Assistant, messages: [{}, {}] })).toBe(true);
    expect(shouldShowMessageProcess({ type: MessageRole.Assistant, messages: [] })).toBe(false);
    expect(shouldShowMessageProcess({ type: MessageRole.User, messages: [{}] })).toBe(false);
    expect(shouldShowMessageProcess({ type: MessageRole.Loading, messages: [{}] })).toBe(false);
  });

  it('终态应该以最后一条 assistant 为折叠边界，生成中不折叠', () => {
    const messages = [assistant, reasoning, assistant, tool, info];

    expect(resolveProcessCollapseIndex(messages, false)).toBe(2);
    expect(resolveProcessCollapseIndex(messages, true)).toBe(0);
  });

  it('空组、没有 assistant 或最后一条 assistant 位于首位时不应折叠', () => {
    expect(resolveProcessCollapseIndex([], false)).toBe(0);
    expect(resolveProcessCollapseIndex([assistant], false)).toBe(0);
    expect(resolveProcessCollapseIndex([reasoning, info], false)).toBe(0);
    expect(resolveProcessCollapseIndex([assistant, info], false)).toBe(0);
  });

  it.each([
    { name: 'flow_agent 在最后一条 assistant 之前', messages: [reasoning, flow, tool, assistant, info], expected: 1 },
    { name: '第三方审批在最后一条 assistant 之前', messages: [reasoning, approval, tool, assistant], expected: 1 },
    { name: '多个特殊消息中 flow_agent 最先出现', messages: [reasoning, flow, assistant, approval, flow, assistant], expected: 1 },
    { name: '多个特殊消息中第三方审批最先出现', messages: [reasoning, approval, assistant, flow, approval, assistant], expected: 1 },
    { name: '最后一条 assistant 早于特殊消息', messages: [reasoning, assistant, flow, approval], expected: 1 },
    { name: '特殊消息位于首位', messages: [flow, approval, assistant], expected: 0 },
    { name: '有特殊消息但没有 assistant', messages: [reasoning, flow, approval], expected: 0 },
  ])('$name 时应该从最早需要保留的位置展示', ({ messages, expected }) => {
    expect(resolveProcessCollapseIndex(messages, false)).toBe(expected);
    expect(resolveProcessCollapseIndex(messages, true)).toBe(0);
  });

  it.each(['resolved', 'cancelled'] as const)('第三方审批回显为 %s 时仍应保留审批及后续消息', status => {
    const resolvedApproval: InterruptMessage = {
      ...approval,
      content: {
        outcome: { type: 'success' },
        result: {
          interruptId: 'approval',
          reason: InterruptReason.AIDevToolApproval,
          status,
          payload: {
            metadata: {
              ticket: {
                approvers: [],
                sn: 'approval-1',
                status: status === 'resolved' ? APPROVAL_STATUS.APPROVED : APPROVAL_STATUS.CANCELLED,
                submit_time: '2026-01-01T00:00:00Z',
                title: '工具审批',
                url: 'https://example.com/approval-1',
              },
            },
          },
        },
      },
    };

    expect(resolveProcessCollapseIndex([reasoning, resolvedApproval, tool, assistant], false)).toBe(1);
  });

  it('其他活动和用户提问中断不应改变最后一条 assistant 的折叠边界', () => {
    const messages: Message[] = [
      reasoning,
      { ...flow, activityType: MessageContentType.ReferenceDocument },
      {
        ...approval,
        content: {
          outcome: {
            type: 'interrupt',
            interrupts: [{ id: 'question', toolCallId: 'call-2', reason: InterruptReason.UserQuestion }],
          },
        },
      },
      {
        ...approval,
        content: {
          outcome: { type: 'success' },
          result: {
            interruptId: 'question',
            reason: InterruptReason.UserQuestion,
            status: 'resolved',
            payload: { answers: [] },
          },
        },
      },
      assistant,
    ];

    expect(resolveProcessCollapseIndex(messages, false)).toBe(4);
  });
});
