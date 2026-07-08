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

import type { APPROVAL_STATUS, InterruptReason, MessageRole } from './constants';
import type { BaseMessage } from './messages';

/**
 * 可恢复操作（resume operation）枚举。
 *
 * 统一标识用户在「中断消息 / 活动消息」上触发的、需回传 Agent 处理的动作；
 * 业务侧通过 `onInterruptResume` 回调的 `payload.operation` 字段进行分支处理。
 * 新增操作类型只需在此扩展，回调契约与透传链路保持不变。
 */
export enum InterruptResumeOperation {
  /** 主动取消第三方工具审批：在 interrupt 记录上写入取消结果 */
  ApprovalCancel = 'approval_cancel',
  /** 刷新第三方工具审批：刷新审批单状态 */
  ApprovalRefresh = 'approval_refresh',
  /** 重试失败的流程节点：bkflow 节点状态重置为可执行 */
  FlowNodeRetry = 'flow_node_retry',
  /** 跳过失败的流程节点：bkflow 节点标记为已跳过 */
  FlowNodeSkip = 'flow_node_skip',
}

/**
 * AI Dev 第三方工具审批中断
 */
export type AIDevToolApprovalInterrupt = BaseInterrupt<
  InterruptReason.AIDevToolApproval,
  AIDevToolApprovalInterruptPayloadMetaData
>;

export type AIDevToolApprovalInterruptPayloadMetaData = {
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
  /**
   * 工具参数
   */
  toolArgs?: Record<string, any>;
};

/**
 * AI Dev 第三方工具审批中断响应（resume 后用于 outcome.success 时会话内回显审批单）。
 * payload 透传中断时的 metaData（含 ticket），以便复用 ToolApprovalCard 渲染。
 */
export type AIDevToolApprovalResume = BaseResume<
  InterruptReason.AIDevToolApproval,
  { metadata: AIDevToolApprovalInterruptPayloadMetaData }
>;

export type BaseInterrupt<T extends InterruptReason, M extends Record<string, any>> = {
  expiresAt?: string;
  id: string;
  message?: string;
  metadata?: M;
  properties?: Record<string, any>;
  reason: T;
  toolCallId: string;
};

export type BaseResume<T extends InterruptReason, P extends Record<string, any> = Record<string, any>> = {
  id?: string; // 兼容 id === interruptId
  interruptId: string;
  payload: P;
  reason: T;
  status: 'cancelled' | 'resolved';
};

/**
 * 流程节点（flow-agent）操作响应负载：重试 / 跳过失败节点。
 * 流程节点不属于 interrupt，故节点定位信息（taskId / nodeId）随 payload 一并回传，
 * 此时 `onInterruptResume` 的第二个 `interrupt` 参数为空。
 */
export type FlowNodeResume = {
  operation: InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;
  payload: {
    node_id: string; // 节点 ID
    task_id: number; // 任务 ID
  };
};

export type Interrupt =
  | AIDevToolApprovalInterrupt
  | BaseInterrupt<InterruptReason, Record<string, any>>
  | UserQuestionInterrupt;

export type InterruptItem = Interrupt;
/**
 * 中断消息
 *
 * 对应 AG-UI 协议 `RUN_FINISHED { outcome: { type: "interrupt", interrupts } }` 事件。
 * 当 Agent 需要 human-in-the-loop（审批 / 补充信息 / 策略阻断等）时，
 * 会派生此类型消息以驱动 UI 渲染等待用户响应；用户响应后通过
 * `RunAgentInput.resume = { interruptId, payload }` 把结果回传给 Agent。
 *
 * @see https://docs.ag-ui.com/drafts/interrupts
 */
export type InterruptMessage = BaseMessage<
  MessageRole.Interrupt,
  {
    message?: string;
    /** 是否已被用户响应（resume）过，用于 UI 区分"等待响应 / 已处理"两种态 */
    outcome?: RunFinishedOutcome;
    /** outcome.type === success 用户 resume 后回传/持久化的结果，用于会话内按 reason 回显 */
    result?: InterruptResult;
    runId?: string;
    threadId?: string;
  }
>;

/**
 * 中断处理结果（resume 后回传/持久化，用于 outcome.success 时会话内回显）。
 * 按 reason 区分不同结果形态，统一具备 BaseResume 的 { interruptId, reason, status }；
 * 新增中断类型的回显结果只需在此联合扩展。
 */
export type InterruptResult = AIDevToolApprovalResume | UserQuestionResume;

export type InterruptResume = FlowNodeResume | ToolApprovalResume | UserQuestionResume;

/**
 * 中断响应回调（统一约定：payload 在前，原始中断信息在后）
 * @param payload 响应负载（resume payload），通过 `payload.operation` 区分动作类型
 * @param interrupt 中断原始信息；流程节点等非中断来源的操作可不传
 * @returns
 */
export type OnInterruptResume = (payload: InterruptResume, interrupt?: Interrupt) => Promise<void> | void;

export type RunFinishedOutcome = { interrupts: Interrupt[]; type: 'interrupt' } | { type: 'success' };
/**
 * 第三方工具审批中断的响应负载（取消审批 / 刷新审批单状态）。
 * 两种操作 payload 结构一致（仅传 interrupt_id），由 operation 区分动作。
 */
export type ToolApprovalResume = {
  operation: InterruptResumeOperation.ApprovalCancel | InterruptResumeOperation.ApprovalRefresh;
  payload: { interrupt_id: number | string };
};

/**
 * 用户对单个问题的回答
 */
export type UserQuestionAnswerItem = {
  answer: UserQuestionOptionItem[]; // 用户已选择项；label 为 others 时 description 为自定义输入文本
  multiSelect?: boolean; // 回显卡片用于还原 单选/多选 Tag
  question: string; // 问题名称
};

/**
 * 用户回答问题中断
 */
export type UserQuestionInterrupt = BaseInterrupt<
  InterruptReason.UserQuestion,
  {
    questions: UserQuestionItem[];
  }
>;

/**
 * 用户回答问题中的单个问题
 */
export type UserQuestionItem = {
  header: string; // 问题框标题
  multiSelect?: boolean; // 是否多选（仅选择题语义；自定义表单类问题可不传）
  options?: UserQuestionOptionItem[]; // 选项 label 为 others 时为用户自定义输入
  question: string; // 问题名称
};

/**
 * 用户回答问题选项；label 为 `others` 时代表用户自定义输入，description 为输入文本
 */
export type UserQuestionOptionItem = { description: string; label: string };

/**
 * 用户回答问题中断响应
 */
export type UserQuestionResume = BaseResume<
  InterruptReason.UserQuestion,
  {
    answers: UserQuestionAnswerItem[];
  }
>;
