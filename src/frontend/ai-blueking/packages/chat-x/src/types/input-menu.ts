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

import type { Component } from 'vue';

import type { lang } from '../lang/lang';

/**
 * 输入框菜单可选项类型。
 *
 * `file` 是组件内置的动作项（触发本地文件上传），不由业务方通过 `menuSources` 提供。
 */
export const MENU_ITEM_TYPES = ['file', 'skill', 'mcp', 'tool', 'knowledgebase', 'doc', 'artifact', 'prompt'] as const;

/** 面板渲染用的分组（已应用关键字过滤与折叠阈值） */
export interface IInputMenuGroup {
  /** 分组下方是否需要分隔线 */
  divided: boolean;
  /** 是否已展开全部条目 */
  expanded: boolean;
  /** 当前可见条目 */
  items: IInputMenuItem[];
  key: string;
  /** 分组标题的文案 key，渲染时经 t() 转换 */
  name: keyof typeof lang;
  /** 被折叠隐藏的条数，为 0 表示无需折叠 */
  restCount: number;
}

/** 输入框菜单的统一可选项模型 */
export interface IInputMenuItem {
  /** Prompt 全文；选中 prompt 时用它整体替换输入框内容 */
  content?: string;
  /** 描述文案，有值时 hover 弹出气泡说明 */
  description?: string;
  disabled?: boolean;
  /**
   * 图标：URL 字符串或 Vue 组件；缺省时按 type 回退到内置图标，artifact 按文件名后缀推导。
   *
   * 注意：选中后插入输入框的标签会把图标序列化到 DOM 属性上（文档需脱离数据源独立还原），
   * 因此只有字符串形式能被保留，传组件时标签内会回退为类型默认图标。
   */
  icon?: Component | string;
  id: string;
  name: string;
  type: MenuItemType;
}

export type MenuItemType = (typeof MENU_ITEM_TYPES)[number];

/**
 * 菜单触发方式。字符触发在编辑器中输入对应字符唤起，`plus` 由左下角 + 号按钮唤起。
 */
export type MenuTrigger = '/' | '@' | '\\' | 'plus';
