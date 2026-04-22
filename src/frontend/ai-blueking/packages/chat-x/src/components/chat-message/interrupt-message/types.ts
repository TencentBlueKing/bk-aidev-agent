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

import { InterruptReason } from '../../../ag-ui/types/constants';

import type { UserChoice, UserChoicePayload } from '../../../ag-ui/types/interrupt';

export interface InterruptChoiceListProps {
  disabled?: boolean;
  onSubmit: InterruptChoiceSubmit;
  payload: UserChoicePayload<'multi' | 'single'>;
}

/** InterruptChoiceList 提交回调：返回 Promise 用于 loading 与异常恢复 */
export type InterruptChoiceSubmit = (selected: string[], selectedChoices: UserChoice[]) => Promise<void> | void;

export interface InterruptOptionBtnProps {
  description?: string;
  disabled?: boolean;
  label: string;
  selected: boolean;
}

export interface InterruptResultProps {
  selectedLabels: string[];
  title: string;
}

/**
 * 本期支持渲染的 reason 集合；其余 reason（如 HumanApproval）由顶层组件兜底为 null
 * 后续扩展时只需在此追加一行
 */
export const SUPPORTED_INTERRUPT_REASONS: InterruptReason[] = [
  InterruptReason.UserSingleChoice,
  InterruptReason.UserMultiChoice,
];
