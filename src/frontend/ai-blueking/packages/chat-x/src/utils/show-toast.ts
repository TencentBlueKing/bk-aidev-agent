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
import { Message } from 'bkui-vue';
import type { VNode } from 'vue';

import { TOAST_HOST_CLASS, TOAST_MESSAGE_CLASS } from '../common/constants';

export type ShowToastTheme = 'primary' | 'success' | 'warning' | 'error';

export type ShowToastOptions = {
  delay?: number;
  dismissable?: boolean;
  extCls?: string;
  message: string | VNode;
  offsetY?: number;
  theme?: ShowToastTheme;
};

/**
 * 解析 AIBlueking 浮层内的 toast 挂载点。
 * 存在时 Message 会以 absolute 挂入浮层层叠上下文（z-index 10000），避免默认挂 body（约 6000）被挡住。
 */
const resolveToastContainer = (): HTMLElement | undefined => {
  if (typeof document === 'undefined') {
    return undefined;
  }
  const host = document.querySelector(`.${TOAST_HOST_CLASS}`);
  return host instanceof HTMLElement ? host : undefined;
};

const mergeExtCls = (...classNames: Array<string | undefined>): string =>
  classNames
    .flatMap(name => (name ? name.split(/\s+/) : []))
    .filter(Boolean)
    .join(' ');

/**
 * 统一 toast 入口：优先挂到 AIBlueking 浮层 toast host，否则回退 document.body。
 * 组件内禁止再直接调用 bkui-vue `Message()`。
 */
export const showToast = (options: ShowToastOptions): void => {
  const getContainer = resolveToastContainer();
  Message({
    ...options,
    extCls: mergeExtCls(TOAST_MESSAGE_CLASS, options.extCls),
    ...(getContainer ? { getContainer } : {}),
  });
};
