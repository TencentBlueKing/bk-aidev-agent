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
import { APPROVAL_STATUS, InterruptReason, MessageRole, MessageStatus, RunFinishedOutcome } from '../src';

import type { Message } from '../src';

export const MOCK_INTERRUPT_MESSAGES: Message[] = [
  {
    id: 'msg_ai_dev_tool_approval_intro',
    role: MessageRole.Assistant,
    content: '我已经为您生成了5个冒泡排序算法方案。同时，我注意到有一个相关的技术评审单据需要您关注：',
    status: MessageStatus.Complete,
    messageId: 'msg_ai_dev_tool_approval_intro',
  },
  {
    id: 'msg_ai_dev_tool_approval_interrupt',
    messageId: 'msg_ai_dev_tool_approval_interrupt',
    role: MessageRole.Interrupt,
    status: MessageStatus.Complete,
    content: '',
    outcome: RunFinishedOutcome.Interrupt,
    runId: 'run_ai_dev_tool_approval',
    threadId: 'thread_ai_dev_tool_approval',
    interrupt: [
      {
        reason: InterruptReason.AIDevToolApproval,
        toolCallId: 'tool_call_review_ticket',
        message: '算法方案评审单正在评审中',
        metadata: {
          ticket: {
            approvers: ['张三', '李四', 'xddddssss', 'ddd'],
            sn: 'REV-2026-04-24-001',
            status: APPROVAL_STATUS.PENDING,
            submit_time: '2026-04-24 14:30:15',
            title: '算法方案评审单',
            url: 'https://example.com/review-tickets/REV-2026-04-24-001',
          },
        },
      },
    ],
  },
];
