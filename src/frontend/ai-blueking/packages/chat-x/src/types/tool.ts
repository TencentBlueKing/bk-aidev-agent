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

import type { Component, VNode } from 'vue';

import type { ToolIcons } from '../icons/tools';
import type { TippyOptions } from 'vue-tippy';

export enum MessageToolsStatus {
  Disabled = 'disabled', // 禁用
  Hidden = 'hidden', // 隐藏
}

export type AITippyProps = Partial<Pick<TippyOptions, 'appendTo' | 'placement' | 'zIndex'>>;

export interface IToolBtn {
  description?: string;
  // 隐藏该按钮：配合按 id 合并使用，如 { id: 'share', hidden: true } 可移除内置项
  hidden?: boolean;
  // 自定义图标（组件或 VNode），优先级高于内置 ToolIconsMap；配合自定义 id 使用
  icon?: Component | VNode;
  // 内置 id 保留自动补全，同时允许业务自定义任意字符串（如 'save'）
  id?: (string & {}) | ToolIcons;
  name?: string;
  // 标记该按钮点击后进入多选态（复用 share 的选择流程），确认走 confirmShare
  triggerSelection?: boolean;
}
