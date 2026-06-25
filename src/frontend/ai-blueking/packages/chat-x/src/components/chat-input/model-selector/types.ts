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

/** 模型能力标签的语义主题，决定标签配色（与设计稿语义色一一对应） */
export type ModelCapabilityTheme = 'default' | 'primary' | 'success' | 'warning';

/** 模型能力标签，如「图生文」「深度思考」「快速思考」 */
export interface IModelCapability {
  /** 语义主题，决定标签配色，缺省为 default */
  theme?: ModelCapabilityTheme;
  /** 标签文案（由调用方提供，不走内置 i18n） */
  text: string;
}

/** 模型选项 */
export interface IModelOption {
  /** 能力标签列表 */
  capabilities?: IModelCapability[];
  /** 是否禁用，禁用项不可选中 */
  disabled?: boolean;
  /** 模型图标：图片地址（string）或 Vue 组件 / VNode（由调用方按品牌提供） */
  icon?: Component | string;
  /** 模型唯一标识，作为选中值 */
  id: string;
  /** 模型展示名 */
  name: string;
}
