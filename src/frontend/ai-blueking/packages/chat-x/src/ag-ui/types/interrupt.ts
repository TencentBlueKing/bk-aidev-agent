/* eslint-disable @typescript-eslint/no-explicit-any */
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

import type { InterruptReason, MessageRole, RunFinishedOutcome } from './constants';
import type { BaseMessage } from './messages';

export enum APPROVAL_STATUS {
  ABANDONED = 'abandoned', // 已废弃
  APPROVED = 'approved', // 已批准
  CANCELLED = 'cancelled', // 已取消
  EXPIRED = 'expired', // 已过期
  PENDING = 'pending', // 待审批
  REJECTED = 'rejected', // 已拒绝
}

export type AIDevToolApprovalInterrupt = BaseInterrupt<
  InterruptReason.AIDevToolApproval,
  {
    ticket: {
      // approvers 审批人
      approvers: string[];
      // 单据编号
      sn: string;
      // 单据状态
      status: APPROVAL_STATUS;
      // 提交时间
      submit_time: string;
      // 单据标题
      title: string;
      // 单据链接
      url: string;
    };
  }
>;

export type BaseInterrupt<T extends InterruptReason, M extends Record<string, any>> = {
  message?: string;
  metadata?: M;
  properties?: Record<string, any>;
  reason: T;
  toolCallId: string;
};

export type InterruptItem = AIDevToolApprovalInterrupt | BaseInterrupt<InterruptReason, Record<string, any>>;

/**
 * 中断消息
 *
 * 对应 AG-UI 协议 `RUN_FINISHED { outcome: "interrupt", interrupt }` 事件。
 * 当 Agent 需要 human-in-the-loop（审批 / 补充信息 / 策略阻断等）时，
 * 会派生此类型消息以驱动 UI 渲染等待用户响应；用户响应后通过
 * `RunAgentInput.resume = { interruptId, payload }` 把结果回传给 Agent。
 *
 * @see https://docs.ag-ui.com/drafts/interrupts
 */
export interface InterruptMessage extends BaseMessage<MessageRole.Interrupt, string> {
  /** outcome === interrupt 时，中断消息内容 */
  interrupt?: InterruptItem[];
  message?: string;
  /** 是否已被用户响应（rsume）过，用于 UI 区分"等待响应 / 已处理"两种态 */
  outcome?: RunFinishedOutcome;
  /** outcome === success 用户 resume 时回传给 Agent 的 payload，便于回放与持久化 */
  result?: any;
  runId?: string;
  threadId?: string;
}
export type OnInterruptResume = (interrupt: InterruptItem, payload?: Record<string, any>) => Promise<void> | void;
