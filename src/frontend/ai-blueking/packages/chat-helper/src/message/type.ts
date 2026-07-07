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

import type { IFlowAgentResultCustomValue, IRunFinishedEvent } from '../event/type';

export enum ActivityType {
  FlowAgent = 'flow_agent',
  KnowledgeRag = 'knowledge_rag',
  ReferenceDocument = 'reference_document',
  Interrupt = 'interrupt',
}

export enum MessageRole {
  Activity = 'activity',
  Assistant = 'assistant',
  Developer = 'developer',
  Guide = 'guide',
  Hidden = 'hidden',
  HiddenAssistant = 'hidden-assistant',
  HiddenGuide = 'hidden-guide',
  HiddenSystem = 'hidden-system',
  HiddenUser = 'hidden-user',
  Info = 'info',
  Pause = 'pause',
  Placeholder = 'placeholder',
  Reasoning = 'reasoning',
  System = 'system',
  TemplateAssistant = 'template-assistant',
  TemplateGuide = 'template-guide',
  TemplateHidden = 'template-hidden',
  TemplateSystem = 'template-system',
  TemplateUser = 'template-user',
  Tool = 'tool',
  User = 'user',
  Interrupt = 'interrupt',
}

export enum MessageStatus {
  Complete = 'complete',
  Error = 'error',
  Pending = 'pending',
  Stop = 'stop',
  Streaming = 'streaming',
}

export enum MessageType {
  Binary = 'binary',
  Function = 'function',
  Text = 'text',
}

export enum UserOperation {
  FlowNodeRetry = 'flow_node_retry',
  FlowNodeSkip = 'flow_node_skip',
  ApprovalCancel = 'approval_cancel',
}

export type IUserOperationPayload =
  | {
      node_id: string;
      task_id: string;
    }
  | {
      interrupt_id: number | string;
    };

export interface IActivityMessage extends IBaseMessage {
  activityType: ActivityType;
  content: IFlowAgentResultCustomValue | IKnowledgeRag | IReferenceDocument;
  role: MessageRole.Activity;
}

export interface IActivityMessageApi extends IBaseMessageApi {
  activity_type: ActivityType;
  content: IFlowAgentResultCustomValue | IKnowledgeRagApi | IReferenceDocumentApi;
  role: MessageRole.Activity;
}

export interface IAssistantMessage extends IBaseMessage {
  content?: string;
  property?: IMessageProperty;
  role: MessageRole.Assistant;
  toolCalls?: IToolCall[];
}

export interface IAssistantMessageApi extends IBaseMessageApi {
  content?: string;
  property?: IMessageProperty;
  role: MessageRole.Assistant;
  tool_calls?: IToolCallApi[];
}

export interface IBaseMessage {
  id?: string;
  messageId?: string;
  name?: string;
  role: MessageRole;
  sessionCode?: string;
  status: MessageStatus;
}

export interface IBaseMessageApi {
  id?: string;
  message_id?: string;
  name?: string;
  role: MessageRole;
  session_code?: string;
  status: MessageStatus;
}

export interface IBinaryInputContent {
  data?: string;
  filename?: string;
  id?: string;
  mimeType: string;
  type: MessageType.Binary;
  url?: string;
}

export interface IBinaryInputContentApi {
  data?: string;
  filename?: string;
  id?: string;
  mime_type: string;
  type: MessageType.Binary;
  url?: string;
}

export interface IContext {
  description: string;
  value: string;
}

export interface IContextApi {
  description: string;
  value: string;
}

export interface IDeveloperMessage extends IBaseMessage {
  content: string;
  role: MessageRole.Developer;
}

export interface IDeveloperMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.Developer;
}

export interface IInterruptMessage extends IBaseMessage {
  content: IRunFinishedEvent;
  role: MessageRole.Interrupt;
}

export interface IInterruptMessageApi extends IBaseMessageApi {
  content: IRunFinishedEvent;
  role: MessageRole.Interrupt;
}

export interface IFlowAgentTaskNodeInfo {
  inputs: Record<string, unknown>;
  node_id: string;
  task_id: number;
  basic_info: {
    always_use_latest: boolean | null;
    auto_retry: {
      enable: boolean;
      interval: number;
      times: number;
    };
    error_ignorable: boolean;
    node_name: string;
    optional: boolean;
    retryable: boolean;
    skippable: boolean;
    stage_name: string;
    template_name: string;
    timeout_config: {
      action: string;
      enable: boolean;
      seconds: number;
    };
  };
  outputs: {
    key: string;
    preset: boolean;
    value: unknown;
  }[];
  plugin_output: {
    key: string;
    name: string;
    schema: {
      description: string;
      enum: unknown[];
      properties?: Record<string, unknown>;
      type: string;
    };
    type: string;
  }[];
}

export interface IFunctionCall {
  arguments: string;
  description?: string;
  mcpName?: string;
  name: string;
}

export interface IFunctionCallApi {
  arguments: string;
  description?: string;
  mcp_name?: string;
  name: string;
}

export interface IGuideMessage extends IBaseMessage {
  content: string;
  role: MessageRole.Guide;
}

export interface IGuideMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.Guide;
}

export interface IHiddenAssistantMessage extends IBaseMessage {
  content: string;
  role: MessageRole.HiddenAssistant;
}

export interface IHiddenAssistantMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.HiddenAssistant;
}

export interface IHiddenGuideMessage extends IBaseMessage {
  content: string;
  role: MessageRole.HiddenGuide;
}

export interface IHiddenGuideMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.HiddenGuide;
}

export interface IHiddenMessage extends IBaseMessage {
  content: string;
  role: MessageRole.Hidden;
}

export interface IHiddenMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.Hidden;
}

export interface IHiddenSystemMessage extends IBaseMessage {
  content: string;
  role: MessageRole.HiddenSystem;
}

export interface IHiddenSystemMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.HiddenSystem;
}

export interface IHiddenUserMessage extends IBaseMessage {
  content: string;
  role: MessageRole.HiddenUser;
}

export interface IHiddenUserMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.HiddenUser;
}

export interface IInfoMessage extends IBaseMessage {
  content: string;
  role: MessageRole.Info;
}

export interface IInfoMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.Info;
}

export type IInputContent = IBinaryInputContent | ITextInputContent;

export type IInputContentApi = IBinaryInputContentApi | ITextInputContentApi;

export interface IKnowledgeRag {
  content: string;
  referenceDocument: IReferenceDocument;
}

export interface IKnowledgeRagApi {
  content: string;
  reference_document: IReferenceDocumentApi;
}

export type IMessage =
  | IActivityMessage
  | IAssistantMessage
  | IDeveloperMessage
  | IGuideMessage
  | IHiddenAssistantMessage
  | IHiddenGuideMessage
  | IHiddenMessage
  | IHiddenSystemMessage
  | IHiddenUserMessage
  | IInfoMessage
  | IPauseMessage
  | IPlaceholderMessage
  | IReasoningMessage
  | ISystemMessage
  | ITemplateAssistantMessage
  | ITemplateGuideMessage
  | ITemplateHiddenMessage
  | ITemplateSystemMessage
  | ITemplateUserMessage
  | IToolMessage
  | IUserMessage
  | IInterruptMessage;

export type IMessageApi =
  | IActivityMessageApi
  | IAssistantMessageApi
  | IDeveloperMessageApi
  | IGuideMessageApi
  | IHiddenAssistantMessageApi
  | IHiddenGuideMessageApi
  | IHiddenMessageApi
  | IHiddenSystemMessageApi
  | IHiddenUserMessageApi
  | IInfoMessageApi
  | IPauseMessageApi
  | IPlaceholderMessageApi
  | IReasoningMessageApi
  | ISystemMessageApi
  | ITemplateAssistantMessageApi
  | ITemplateGuideMessageApi
  | ITemplateHiddenMessageApi
  | ITemplateSystemMessageApi
  | ITemplateUserMessageApi
  | IToolMessageApi
  | IUserMessageApi
  | IInterruptMessageApi;

/**
 * 消息属性 - 用于传递引用内容或快捷键相关信息
 * 该类型设计为灵活的结构，由外部调用方决定具体内容
 */
export interface IMessageProperty {
  /** 其他扩展字段 */
  [key: string]: unknown;
  extra?: {
    /** 其他扩展字段 */
    [key: string]: unknown;
    /** 引用内容，可以是字符串或结构化对象 */
    cite?:
      | string
      | {
          data: Array<{
            key: string;
            value: string;
          }>;
          title: string;
          type: string;
        };
    /** 快捷键命令 */
    command?: string;
    /** 上下文信息 */
    context?: Array<Record<string, unknown>>;
    /** 用户通过 @ 选择的资源列表 */
    resources?: Array<Record<string, unknown>>;
  };
}

export interface IPauseMessage extends IBaseMessage {
  content: string;
  role: MessageRole.Pause;
}

export interface IPauseMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.Pause;
}

export interface IPlaceholderMessage extends IBaseMessage {
  content: string;
  role: MessageRole.Placeholder;
}

export interface IPlaceholderMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.Placeholder;
}

export interface IReasoningMessage extends IBaseMessage {
  content: string[];
  duration?: number;
  role: MessageRole.Reasoning;
}

export interface IReasoningMessageApi extends IBaseMessageApi {
  content: string[];
  duration?: number;
  role: MessageRole.Reasoning;
}

export type IReferenceDocument = {
  name: string;
  originFileUrl?: string;
  url: string;
}[];

export type IReferenceDocumentApi = {
  name: string;
  origin_file_url?: string;
  url: string;
}[];

export interface IRunAgentInput {
  context: IContext[];
  forwardedProps: unknown;
  messages: IMessage[];
  parentRunId?: string;
  runId: string;
  state: unknown;
  threadId: string;
  tools: ITool[];
}

export interface IRunAgentInputApi {
  context: IContextApi[];
  forwarded_props: unknown;
  messages: IMessageApi[];
  parent_run_id?: string;
  run_id: string;
  state: unknown;
  thread_id: string;
  tools: IToolApi[];
}

export interface ISystemMessage extends IBaseMessage {
  content: string;
  role: MessageRole.System;
}

export interface ISystemMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.System;
}

export interface ITemplateAssistantMessage extends IBaseMessage {
  content: string;
  role: MessageRole.TemplateAssistant;
}

export interface ITemplateAssistantMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.TemplateAssistant;
}

export interface ITemplateGuideMessage extends IBaseMessage {
  content: string;
  role: MessageRole.TemplateGuide;
}

export interface ITemplateGuideMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.TemplateGuide;
}

export interface ITemplateHiddenMessage extends IBaseMessage {
  content: string;
  role: MessageRole.TemplateHidden;
}

export interface ITemplateHiddenMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.TemplateHidden;
}

export interface ITemplateSystemMessage extends IBaseMessage {
  content: string;
  role: MessageRole.TemplateSystem;
}

export interface ITemplateSystemMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.TemplateSystem;
}

export interface ITemplateUserMessage extends IBaseMessage {
  content: string;
  role: MessageRole.TemplateUser;
}

export interface ITemplateUserMessageApi extends IBaseMessageApi {
  content: string;
  role: MessageRole.TemplateUser;
}

export interface ITextInputContent {
  text: string;
  type: MessageType.Text;
}

export interface ITextInputContentApi {
  text: string;
  type: MessageType.Text;
}

export interface ITool {
  description: string;
  name: string;
  parameters: unknown; // JSON Schema for the tool parameters
}

export interface IToolApi {
  description: string;
  name: string;
  parameters: unknown; // JSON Schema for the tool parameters
}

export interface IToolCall {
  function: IFunctionCall;
  id: string;
  type: MessageType.Function;
}

export interface IToolCallApi {
  function: IFunctionCallApi;
  id: string;
  type: MessageType.Function;
}

export interface IToolMessage extends IBaseMessage {
  content: string;
  duration?: number;
  error?: string;
  role: MessageRole.Tool;
  toolCallId: string;
}

export interface IToolMessageApi extends IBaseMessageApi {
  content: string;
  duration?: number;
  error?: string;
  role: MessageRole.Tool;
  tool_call_id: string;
}

export interface IUserMessage extends IBaseMessage {
  content: IInputContent[] | string;
  /** 消息属性，用于传递引用内容或快捷键相关信息 */
  property?: IMessageProperty;
  role: MessageRole.User;
}

export interface IUserMessageApi extends IBaseMessageApi {
  content: IInputContentApi[] | string;
  /** 消息属性，用于传递引用内容或快捷键相关信息 */
  property?: IMessageProperty;
  role: MessageRole.User;
}
