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
import { AddNewSessionOptions } from '@/store/types';

// 扩展 IAgentCommandComponent 类型
// 扩展 mode 属性，用于指定指令模式：simple 简单模式，advanced 高级模式，默认为 advanced模式，在没有明确设置为 simple 模式时，视为 advanced 模式
export interface IShortcutComponent extends IAgentCommandComponent {
  /**
   * 控制指令组件中单个输入模块的展示模式：simple 简单模式，advanced 高级模式，默认为 advanced模式，在没有明确设置为 simple 模式时，视为 advanced 模式
   * simple模式：直接展示输入组件，没有label
   * @since v1.2.9
   */
  mode?: 'simple' | 'advanced';
}

// 扩展 IAgentCommand 类型，添加 iconRender 支持
export interface IShortcut extends Omit<IAgentCommand, 'components'> {
  /**
   * 重写 components 属性，使用扩展的 IShortcutComponent 类型
   */
  components?: IShortcutComponent[];

  /**
   * 自定义 icon 渲染函数
   * @param h - Vue 的 h 函数,用于创建 VNode
   * @returns VNode
   */
  iconRender?: (h: typeof import('vue').h) => VNode;

  /**
   * 指定指令模式：simple 简单模式，advanced 高级模式，默认为 advanced模式，在没有明确设置为 simple 模式时，视为 advanced 模式
   * 这里会添加mode到指令组件class中，用于样式控制
   * simple模式：直接展示指令组件，没有外层 header 和 footer，右下角只有单个提交icon，适合简单的指令
   * advanced模式：展示指令组件，有外层 header 和 footer，适合复杂的指令
   * @since v1.2.9
   */
  mode?: 'simple' | 'advanced';

  /**
   * 是否隐藏底部按钮区域，默认为 false
   * @since v1.2.9
   */
  hideFooter?: boolean;

  /**
   * 用于强制重新渲染组件的唯一键值
   * 每次快捷指令更新时都会生成新的时间戳
   * @since v1.3.0
   */
  bindKey?: string;

  /**
   * 用于显示的别名
   * @since v1.3.2
   */
  alias?: string;
}

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
  handleShow: (sessionCode?: string, options?: AddNewSessionOptions) => Promise<void>;
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

// 导出组件 Props 和 Emits 类型
export type {
  AiBluekingProps,
  AiBluekingEmits,
  DropdownMenuConfig,
  PositionInfo,
} from './ai-blueking-props';
