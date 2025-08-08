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
import type { ISessionContent, ShortCut, IAgentCommand } from '@blueking/ai-ui-sdk/types';
import type { Ref } from 'vue';

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
  handleShow: () => void;
  handleStop: () => void;
  reGenerateChat: () => void;
  reSendChat: () => void;
  deleteChat: () => void;
  currentSessionLoading: () => boolean;
}

// 使用 ai-ui-sdk 中的 IAgentCommand 类型作为 IShortcut 的别名
export type IShortcut = IAgentCommand;

export type IShortcutComponentType = 'text' | 'textarea' | 'number' | 'select';

export type IShortcutComponent = {
  name: string;
  key: string;
  type: IShortcutComponentType;
  default?: string | number;
  placeholder?: string;
  required?: boolean;
  fillBack?: boolean;
  fillRegx?: string; // 改为字符串类型，避免 JSON 序列化问题
  min?: number;
  max?: number;
  rows?: number;
  selectedText?: string | null;
  options?: { label: string; value: string }[];
};

// 扩展 IAgentCommandComponent 类型，添加 selectedText 属性
export interface IAgentCommandComponentWithSelectedText extends IShortcutComponent {
  selectedText?: string | null;
}

export type { ShortCut, ISessionContent };

type IContext = Record<string, string> | Record<string, string>[];

export interface IRequestOptions {
  headers?: Record<string, string>;
  data?: Record<string, string>;
  context?: IContext | (() => IContext);
}

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
