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

import { t } from '../../../lang/lang';

import type { IModelCapability, IModelOption, IModelProperty, ModelCapabilityTheme } from './types';

/** property 能力开关 → 展示标签的映射定义（数组顺序即标签展示顺序） */
const CAPABILITY_DEFS: {
  key: keyof IModelProperty;
  label: () => string;
  theme: ModelCapabilityTheme;
}[] = [
  { key: 'support_thinking', label: () => t('深度思考'), theme: 'primary' },
  { key: 'support_thinking_quick', label: () => t('快速思考'), theme: 'success' },
  { key: 'support_vision', label: () => t('图生文'), theme: 'warning' },
];

/** 根据模型 property 派生能力标签列表（仅保留已开启的能力，文案走 i18n） */
export const resolveModelCapabilities = (model: IModelOption): IModelCapability[] =>
  CAPABILITY_DEFS.filter(def => model.property?.[def.key]).map(def => ({
    text: def.label(),
    theme: def.theme,
  }));
