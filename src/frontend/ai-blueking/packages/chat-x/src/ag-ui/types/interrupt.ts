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
  /** 是否已被用户响应（resume）过，用于 UI 区分"等待响应 / 已处理"两种态 */
  outcome?: RunFinishedOutcome;
  /** outcome === success 用户 resume 时回传给 Agent 的 payload，便于回放与持久化 */
  result?: any; // eslint-disable-line @typescript-eslint/no-explicit-any
  runId?: string;
  threadId?: string;
  /** outcome === interrupt 时，中断消息内容 */
  interrupt?: {
    id: string;
    /** UI 渲染所需的任意 JSON，例如待审批的提案、表单 schema、diff 等 */
    payload: UserChoicePayload<'multi' | 'single'>;
    /** 中断原因，例如 'human_approval' | 'user_multi_choice' | 'user_single_choice' 等 */
    reason: InterruptReason;
  };
}

/**
 * 用户响应中断时上报给上层的 payload
 */
export type InterruptResumePayload = {
  /** 对应 message.interrupt.id，便于上层定位与回放 */
  interruptId: string;
  /** 单选返回 string；多选返回 string[]，与 payload.type 对齐 */
  selected: string | string[];
  /** 选中项完整对象，便于上层做 label 展示与日志 */
  selectedChoices: UserChoice[];
};

/**
 * 中断消息的 resume 回调签名
 * @param message 当前 InterruptMessage
 * @param payload 用户选择的结果
 */
export type OnInterruptResume = (message: InterruptMessage, payload: InterruptResumePayload) => Promise<void> | void;

export type UserChoice = {
  description?: string;
  disabled?: boolean;
  id?: string;
  label?: string;
  value: string;
};

export type UserChoicePayload<T extends 'multi' | 'single'> = {
  choices: UserChoice[];
  selected?: T extends 'multi' ? string[] : string;
  title?: string;
  type: T extends 'multi' ? InterruptReason.UserMultiChoice : InterruptReason.UserSingleChoice;
};
