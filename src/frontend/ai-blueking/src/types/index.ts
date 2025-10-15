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

import type {
  ISessionContent,
  ShortCut,
  IAgentCommand,
  IAgentCommandComponent,
} from '@blueking/ai-ui-sdk/types';
import type { useChat } from '@blueking/ai-ui-sdk/hooks';
import type { Ref, VNode } from 'vue';

export interface AIBluekingExpose {
  sessionContents: Ref<ISessionContent[]>;
  sendChat: ({
    message,
    cite,
    shortcut,
  }: {
    message: string;
    cite?: string;
    shortcut?: ShortCut;
  }) => void;
  handleShow: (sessionCode?: string, forceNewSession?: boolean) => Promise<void>;
  handleClose: () => void;
  handleStop: () => void;
  handleSendMessage: (message: string) => void;
  handleShortcutClick: (data: { shortcut: IShortcut; source: 'popup' | 'main' }) => void;
  handleDelete: (index: number) => void;
  handleRegenerate: (index: number) => void;
  handleResend: (index: number, { message }: { message: string }) => void;
  updateRequestOptions: (options: any) => void;
  currentSessionLoading: Ref<boolean>;
  isLoadingSessionContents: Ref<boolean>;
  updateGreetingTextHeight: () => void;
  setCurrentSession: (sessionCode: string) => void;
  focusInput: () => void;
  addNewSession: (sessionCode?: string) => Promise<any>;
  updateSessionName: (sessionCode: string, newName: string) => Promise<any>;
  switchToSession: (sessionCode: string) => Promise<boolean>;
  getSessionList: () => Promise<any[]>;
  sessionList: Ref<any[]>;
  enableChatSession: Ref<boolean>;
  updatePosition: (x: number, y: number) => void;
  updateSize: (w: number, h: number) => void;
  updatePositionAndSize: (x: number, y: number, w: number, h: number) => void;
}

// 扩展 IAgentCommand 类型，添加 iconRender 支持
export interface IShortcut extends IAgentCommand {
  /**
   * 自定义 icon 渲染函数
   * @param h - Vue 的 h 函数，用于创建 VNode
   * @returns VNode
   */
  iconRender?: (h: typeof import('vue').h) => VNode;
}

// 扩展 IAgentCommandComponent 类型，添加 hide 和 selectedText 属性
export interface IShortcutComponent extends IAgentCommandComponent {
  selectedText?: string | null;
}

// 保持与旧版本的兼容性
export type IAgentCommandComponentWithSelectedText = IShortcutComponent;

export type { ShortCut, ISessionContent };

type IContext = Record<string, string> | Record<string, string>[];
export type UseChatParams = typeof useChat extends (...args: infer R) => any ? R[0] : never;

export type IRequestOptions = Partial<UseChatParams['requestOptions']> & {
  context?: IContext | (() => IContext);
};

export type IDocument = {
  metadata: {
    file_path: string;
    path: string;
    preview_path?: string;
  };
};

export interface FormItem {
  name: string;
  key: string;
  type: 'text' | 'textarea' | 'number' | 'select';
  default?: any;
  placeholder?: string;
  required?: boolean;
  // 特殊属性（如 select 的 options）
  options?: string[]; // select 专用
  min?: number; // number 专用
  max?: number; // number 专用
  rows?: number; // textarea 专用
}

// 表单规则类型定义
export interface FormRule {
  required?: boolean;
  type?: string;
  min?: number;
  max?: number;
  message: string;
  trigger: string;
}

// 验证策略接口
export interface ValidationStrategy {
  (component: IShortcutComponent): FormRule | FormRule[] | null;
}
