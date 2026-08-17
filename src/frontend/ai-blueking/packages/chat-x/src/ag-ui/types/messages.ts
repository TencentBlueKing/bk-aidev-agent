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

import type { OldShortcut, Shortcut } from '../../types';
import type { MessageContentType, MessageRole, MessageStatus } from './constants';
import type { ContentMap, InputContent } from './contents';
import type { AIFileInfo } from './file';
import type { InterruptMessage } from './interrupt';

export interface ActivityMessage extends BaseMessage<
  MessageRole.Activity,
  | ContentMap[MessageContentType.FlowAgent]
  | ContentMap[MessageContentType.KnowledgeRag]
  | ContentMap[MessageContentType.ReferenceDocument]
> {
  activityType:
    | MessageContentType.FlowAgent
    | MessageContentType.KnowledgeRag
    | MessageContentType.ReferenceDocument
    | string;
}

export interface AssistantMessage extends BaseMessage<MessageRole.Assistant> {
  toolCalls?: ToolCall[];
}

// 类型扩展机制
declare global {
  // eslint-disable-next-line @typescript-eslint/no-empty-interface, @typescript-eslint/no-empty-object-type
  interface AIBluekingMessageMap {}
}

export interface BaseMessage<T extends MessageType, C = string> {
  content: C;
  /** 消息创建时间，ISO 字符串或毫秒时间戳，由消息层（chat-helper）写入 */
  createdAt?: number | string;
  id: number | string;
  messageId: number | string;
  name?: string;
  role: T;
  status: MessageStatus;
  uid?: string;
  property?: {
    /* 附件 */
    artifacts?: AIFileInfo[];
    extra?: {
      cite:
        | {
            data: {
              key: string;
              value: string;
            }[];
            title: string;
            type: 'structured'; // 唯一值
          } // 代表快捷指令 结构化 表单值数据
        | string; // 代表点击引用的内容 文本
      command: string; // 代表快捷指令名称
      context: Partial<
        {
          [key: string]: string;
          __key: string;
          __label: string; // 对应 cite_data 的 key
          __value: string; // 对应 cite_data 的 value
          context_type: 'checkbox' | 'input' | 'number' | 'radioGroup' | 'select' | 'switcher' | 'text' | 'textarea'; // 快捷指令 components type 类型
        } & Partial<OldShortcut>
      >[];
      pause?: boolean; // 用于判断是否显示 message tools
      shortcut?: Partial<Shortcut>; // 用于 UserMessage 的快捷指令
    };
  };
}

export interface Context {
  description: string;
  value: string;
}

export type DeveloperMessage = BaseMessage<MessageRole.Developer, string>;

export type FunctionCall = {
  arguments: string;
  description?: string;
  mcpName?: string;
  name: string;
};

export type GuideMessage = BaseMessage<MessageRole.Guide, string>;

export type HiddenAssistantMessage = BaseMessage<MessageRole.HiddenAssistant, string>;

export type HiddenGuideMessage = BaseMessage<MessageRole.HiddenGuide, string>;

export type HiddenMessage = BaseMessage<MessageRole.Hidden, string>;

export type HiddenSystemMessage = BaseMessage<MessageRole.HiddenSystem, string>;

export type HiddenUserMessage = BaseMessage<MessageRole.HiddenUser, string>;

export type InfoMessage = BaseMessage<MessageRole.Info, string>;

export type LoadingMessage = BaseMessage<MessageRole.Loading, string>;
export type Message = MessageMap[MessageType];
export type MessageMap = AIBluekingMessageMap & {
  [MessageRole.Activity]: ActivityMessage;
  [MessageRole.Assistant]: AssistantMessage;
  [MessageRole.Developer]: DeveloperMessage;
  [MessageRole.Guide]: GuideMessage;
  [MessageRole.Hidden]: HiddenMessage;
  [MessageRole.HiddenAssistant]: HiddenAssistantMessage;
  [MessageRole.HiddenGuide]: HiddenGuideMessage;
  [MessageRole.HiddenSystem]: HiddenSystemMessage;
  [MessageRole.HiddenUser]: HiddenUserMessage;
  [MessageRole.Info]: InfoMessage;
  [MessageRole.Interrupt]: InterruptMessage;
  [MessageRole.Loading]: LoadingMessage;
  [MessageRole.Pause]: PauseMessage;
  [MessageRole.Placeholder]: PlaceholderMessage;
  [MessageRole.Reasoning]: ReasoningMessage;
  [MessageRole.System]: SystemMessage;
  [MessageRole.TemplateAssistant]: TemplateAssistantMessage;
  [MessageRole.TemplateGuide]: TemplateGuideMessage;
  [MessageRole.TemplateHidden]: TemplateHiddenMessage;
  [MessageRole.TemplateSystem]: TemplateSystemMessage;
  [MessageRole.TemplateUser]: TemplateUserMessage;
  [MessageRole.Tool]: ToolMessage;
  [MessageRole.User]: UserMessage;
};

export type MessageType = keyof MessageMap;
export type PauseMessage = BaseMessage<MessageRole.Pause, string>;
export type PlaceholderMessage = BaseMessage<MessageRole.Placeholder, string>;

export interface ReasoningMessage extends BaseMessage<MessageRole.Reasoning, string[]> {
  duration?: number;
}
export type SystemMessage = BaseMessage<MessageRole.System, string>;

export type TemplateAssistantMessage = BaseMessage<MessageRole.TemplateAssistant, string>;

export type TemplateGuideMessage = BaseMessage<MessageRole.TemplateGuide, string>;

export type TemplateHiddenMessage = BaseMessage<MessageRole.TemplateHidden, string>;

export type TemplateSystemMessage = BaseMessage<MessageRole.TemplateSystem, string>;

export type TemplateUserMessage = BaseMessage<MessageRole.TemplateUser, string>;

export type Tool = {
  description: string;
  name: string;
  parameters: unknown; // JSON Schema for the tool parameters
};

export type ToolCall = {
  function: FunctionCall;
  id: string;
  toolMessage?: Partial<ToolMessage>;
  type: MessageContentType.Function;
};

export interface ToolMessage extends BaseMessage<MessageRole.Tool, string> {
  duration: number;
  error?: boolean | string;
  toolCallId: string;
}

export type UserMessage = BaseMessage<MessageRole.User, InputContent[] | string>;
