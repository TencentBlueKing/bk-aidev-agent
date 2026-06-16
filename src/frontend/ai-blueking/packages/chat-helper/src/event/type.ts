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
import { type IMessageApi, type MessageRole, type MessageStatus } from '../message/type';
import type { JSONSchema4 } from 'json-schema';

export enum CustomEventName {
  FlowAgentEnd = 'flow_agent_end',
  FlowAgentResult = 'flow_agent_result',
  FlowAgentStart = 'flow_agent_start',
  FlowAgentUpdate = 'flow_agent_update',
  KnowledgeRagEnd = 'knowledge_rag_end',
  KnowledgeRagResult = 'knowledge_rag_result',
  KnowledgeRagStart = 'knowledge_rag_start',
  KnowledgeRagTextContent = 'knowledge_rag_text_content',
  ReferenceDocument = 'reference_document',
  TempMessage = 'temp_message',
  ApprovalResult = 'approval_result',
}

export enum EventType {
  ActivityDelta = 'ACTIVITY_DELTA',
  ActivitySnapshot = 'ACTIVITY_SNAPSHOT',
  Custom = 'CUSTOM',
  MessagesSnapshot = 'MESSAGES_SNAPSHOT',
  Raw = 'RAW',
  RunError = 'RUN_ERROR',
  RunFinished = 'RUN_FINISHED',
  RunStarted = 'RUN_STARTED',
  StateDelta = 'STATE_DELTA',
  StateSnapshot = 'STATE_SNAPSHOT',
  StepFinished = 'STEP_FINISHED',
  StepStarted = 'STEP_STARTED',
  TextMessageChunk = 'TEXT_MESSAGE_CHUNK',
  TextMessageContent = 'TEXT_MESSAGE_CONTENT',
  TextMessageEnd = 'TEXT_MESSAGE_END',
  TextMessageStart = 'TEXT_MESSAGE_START',
  ThinkingEnd = 'THINKING_END',
  ThinkingStart = 'THINKING_START',
  ThinkingTextMessageContent = 'THINKING_TEXT_MESSAGE_CONTENT',
  ThinkingTextMessageEnd = 'THINKING_TEXT_MESSAGE_END',
  ThinkingTextMessageStart = 'THINKING_TEXT_MESSAGE_START',
  ToolCallArgs = 'TOOL_CALL_ARGS',
  ToolCallChunk = 'TOOL_CALL_CHUNK',
  ToolCallEnd = 'TOOL_CALL_END',
  ToolCallResult = 'TOOL_CALL_RESULT',
  ToolCallStart = 'TOOL_CALL_START',
}

/** BKFlow 收敛后的节点状态 - task.node 的状态枚举 */
export enum FlowNodeState {
  Failed = 'failed',
  Running = 'running',
  Success = 'success',
  Suspended = 'suspended',
}

/** BKFLOW 原始状态 - task 的状态枚举 */
export enum FlowTaskState {
  Blocked = 'BLOCKED',
  Created = 'CREATED',
  Failed = 'FAILED',
  Finished = 'FINISHED',
  LoopReady = 'LOOP_READY',
  Ready = 'READY',
  Revoked = 'REVOKED',
  RollBackFailed = 'ROLL_BACK_FAILED',
  RollBackSuccess = 'ROLL_BACK_SUCCESS',
  RollingBack = 'ROLLING_BACK',
  Running = 'RUNNING',
  Suspended = 'SUSPENDED',
}

/** 运行完成结果 */
export enum RunFinishedOutcomeType {
  Success = 'success',
  Interrupt = 'interrupt',
}

/** 审批状态 */
export enum ApprovalInterruptTicketStatus {
  Abandoned = 'abandoned',
  Approved = 'approved',
  Cancelled = 'cancelled',
  Draft = 'draft',
  Expired = 'expired',
  Rejected = 'rejected',
  Pending = 'pending',
}

/** 中断原因 */
export enum InterruptReason {
  AIDevToolApproval = 'aidev:tool_approval',
  UserQuestion = 'aidev:user_question',
}

/** 恢复状态 */
export enum ResumeStatus {
  Resolved = 'resolved',
  Cancelled = 'cancelled',
}

/**
 * Activity 代表 Agent 执行过程中的活动/动作/任务，可能包含结构化数据
 * 活动状态的增量更新
 * 记录活动类型 activityType
 * 使用 JSON Patch (RFC 6902) 格式增量更新 Activity 数据
 */
export interface IActivityDeltaEvent extends IBaseEvent {
  activityType: string;
  messageId: string;
  patch: unknown[];
  type: EventType.ActivityDelta;
}

/**
 * Activity 代表 Agent 执行过程中的活动/动作/任务，可能包含结构化数据
 * 活动状态的快照
 * 记录活动类型 activityType
 * 使用 JSON 格式存储 Activity 数据
 */
export interface IActivitySnapshotEvent extends IBaseEvent {
  activityType: string;
  content: unknown;
  messageId: string;
  replace?: boolean;
  type: EventType.ActivitySnapshot;
}

export interface IBaseEvent {
  timestamp?: number;
  type: EventType;
}

/**
 * 自定义事件
 * 用于发送自定义事件到客户端
 */
export interface ICustomEvent extends IBaseEvent {
  name: CustomEventName;
  type: EventType.Custom;
  value:
    | IFlowAgentEndCustomValue
    | IFlowAgentResultCustomValue
    | IFlowAgentStartCustomValue
    | IKnowledgeRagResultCustomValue
    | IKnowledgeRagTextContentCustomValue
    | IReferenceDocumentCustomValue
    | ITempMessageCustomValue
    | IApprovalResultCustomValue;
}

export type IEvent =
  | IActivityDeltaEvent
  | IActivitySnapshotEvent
  | ICustomEvent
  | IMessagesSnapshotEvent
  | IRawEvent
  | IRunErrorEvent
  | IRunFinishedEvent
  | IRunStartedEvent
  | IStateDeltaEvent
  | IStateSnapshotEvent
  | IStepFinishedEvent
  | IStepStartedEvent
  | ITextMessageChunkEvent
  | ITextMessageContentEvent
  | ITextMessageEndEvent
  | ITextMessageStartEvent
  | IThinkingEndEvent
  | IThinkingStartEvent
  | IThinkingTextMessageContentEvent
  | IThinkingTextMessageEndEvent
  | IThinkingTextMessageStartEvent
  | IToolCallArgsEvent
  | IToolCallChunkEvent
  | IToolCallEndEvent
  | IToolCallResultEvent
  | IToolCallStartEvent;

export type IFlowAgentEndCustomValue = {
  task_outputs: string[];
}[];

export interface IFlowAgentNode {
  elapsed_time: number;
  id: string;
  name: string;
  state: FlowNodeState;
  retry: number;
  skip: boolean;
  retryable: boolean;
  skippable: boolean;
}

export type IFlowAgentResultCustomValue = {
  nodes: Record<string, IFlowAgentNode>;
  task_id: number;
  task_name: string;
  task_outputs: string[];
  task_state: FlowTaskState;
}[];

export type IFlowAgentStartCustomValue = {
  task_id: string;
}[];

export type IKnowledgeRagResultCustomValue = IReferenceDocumentCustomValue;

export interface IKnowledgeRagTextContentCustomValue {
  cover: boolean;
  chunk: {
    content: string;
  };
}

/**
 * 消息快照事件
 * 用于记录当前时刻的完整消息状态
 * 同步多端消息状态
 */
export interface IMessagesSnapshotEvent extends IBaseEvent {
  messages: IMessageApi[];
  type: EventType.MessagesSnapshot;
}

/**
 * 透传底层原始事件数据
 * 保留完整的原始事件信息，不做解析
 */
export interface IRawEvent extends IBaseEvent {
  event: unknown;
  source?: string;
  type: EventType.Raw;
}

export type IReferenceDocumentCustomValue = {
  name: string;
  originFileUrl?: string;
  url: string;
}[];

export interface IRunErrorEvent extends IBaseEvent {
  code?: string;
  message: string;
  type: EventType.RunError;
}

export interface IInterrupt<T extends InterruptReason, P extends Record<string, unknown>> {
  id: string;
  reason: T;
  message?: string;
  toolCallId?: string;
  responseSchema?: JSONSchema4;
  expiresAt?: string;
  metadata?: P;
}

export type IApprovalInterrupt = IInterrupt<
  InterruptReason.AIDevToolApproval,
  {
    ticket: {
      approvers: string[];
      sn: string;
      status: ApprovalInterruptTicketStatus;
      submit_time: string;
      title: string;
      url: string;
    };
  }
>;

export type IUserQuestionInterrupt = IInterrupt<
  InterruptReason.UserQuestion,
  {
    questions: {
      header: string;
      multiSelect?: boolean;
      options?: { description: string; label: string }[];
      question: string;
    }[];
  }
>;

export interface IResume {
  interruptId: string;
  status: ResumeStatus;
  payload?: {
    answers: {
      answer: { description: string; label: string }[];
      multiSelect?: boolean;
      question: string;
    }[];
  };
}

export type IRunFinishedOutcome =
  | {
      type: RunFinishedOutcomeType.Success;
    }
  | {
      type: RunFinishedOutcomeType.Interrupt;
      interrupts: Array<IApprovalInterrupt | IUserQuestionInterrupt>;
    };

/**
 * 标记 Agent 运行正常结束
 * 返回最终结果 result
 */
export interface IRunFinishedEvent extends IBaseEvent {
  result?: IResume;
  runId: number;
  threadId: string;
  type: EventType.RunFinished;
  outcome?: IRunFinishedOutcome;
}

/**
 * 标记一次完整的 Agent 执行开始
 * 记录本次运行的唯一标识 runId
 * 关联会话线程 threadId
 * 可以记录初始输入 input
 * 支持嵌套运行（parentRunId 用于子 Agent 调用）
 */
export interface IRunStartedEvent extends IBaseEvent {
  input?: unknown;
  parentRunId?: string;
  runId: number;
  threadId: string;
  type: EventType.RunStarted;
}

/**
 * 状态增量更新事件
 * 用于更新客户端状态
 * 以 JSON Patch 格式增量更新状态
 */
export interface IStateDeltaEvent extends IBaseEvent {
  delta: unknown;
  type: EventType.StateDelta;
}

/**
 * 状态快照事件
 * 用于初始化或重置客户端状态
 * 提供当前时刻的完整状态视图
 */
export interface IStateSnapshotEvent extends IBaseEvent {
  snapshot: unknown;
  type: EventType.StateSnapshot;
}

export interface IStepFinishedEvent extends IBaseEvent {
  stepName: string;
  type: EventType.StepFinished;
}

/**
 * 多步骤 Agent 工作流的追踪和可视化
 * 当 Agent 需要完成一个复杂任务，分成多个步骤执行时
 * StepStartedEvent { stepName: "分析需求" }
 * ... // 其他步骤
 * StepFinishedEvent { stepName: "分析需求" }
 */
export interface IStepStartedEvent extends IBaseEvent {
  stepName: string;
  type: EventType.StepStarted;
}

export interface ITempMessageCustomValue {
  message: string;
  status: MessageStatus;
}

export type IApprovalResultCustomValue = IRunFinishedEvent;

export interface ITextMessageChunkEvent extends IBaseEvent {
  delta?: string;
  messageId: string;
  role?: MessageRole;
  type: EventType.TextMessageChunk;
}

export interface ITextMessageContentEvent extends IBaseEvent {
  delta: string; // must not be an empty string
  messageId: string;
  type: EventType.TextMessageContent;
}

export interface ITextMessageEndEvent extends IBaseEvent {
  messageId: string;
  type: EventType.TextMessageEnd;
}

export interface ITextMessageStartEvent extends IBaseEvent {
  messageId: string;
  role: MessageRole;
  type: EventType.TextMessageStart;
}

/**
 * 思考结束事件
 */
export interface IThinkingEndEvent extends IBaseEvent {
  duration?: number;
  type: EventType.ThinkingEnd;
}

/**
 * 思考开始事件
 * 记录思考的标题 title
 */
export interface IThinkingStartEvent extends IBaseEvent {
  title?: string;
  type: EventType.ThinkingStart;
}

/**
 * 思考文本消息内容事件
 */
export interface IThinkingTextMessageContentEvent extends IBaseEvent {
  delta: string;
  type: EventType.ThinkingTextMessageContent;
}

/**
 * 思考文本消息结束事件
 */
export interface IThinkingTextMessageEndEvent extends IBaseEvent {
  type: EventType.ThinkingTextMessageEnd;
}

/**
 * 思考文本消息开始事件
 */
export interface IThinkingTextMessageStartEvent extends IBaseEvent {
  type: EventType.ThinkingTextMessageStart;
}

export interface IToolCallArgsEvent extends IBaseEvent {
  delta: string;
  toolCallId: string;
  type: EventType.ToolCallArgs;
}

export interface IToolCallChunkEvent extends IBaseEvent {
  delta?: string;
  parentMessageId?: string;
  toolCallId?: string;
  toolCallName?: string;
  type: EventType.ToolCallChunk;
}

export interface IToolCallEndEvent extends IBaseEvent {
  toolCallId: string;
  type: EventType.ToolCallEnd;
}

export interface IToolCallResultEvent extends IBaseEvent {
  content: string;
  duration?: number;
  messageId: string;
  toolCallId: string;
  type: EventType.ToolCallResult;
}

export interface IToolCallStartEvent extends IBaseEvent {
  description?: string;
  mcpName?: string;
  parentMessageId?: string;
  toolCallId: string;
  toolCallName: string;
  type: EventType.ToolCallStart;
}
