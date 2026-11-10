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
import {
  type InjectionKey,
  type MaybeRefOrGetter,
  type VNode,
  hasInjectionContext,
  inject,
  provide,
  toValue,
} from 'vue';

import { Message } from 'bkui-vue';

export type ShowToastOptions = {
  delay?: number;
  dismissable?: boolean;
  extCls?: string;
  message: string | VNode;
  offsetY?: number;
  theme?: ShowToastTheme;
};

export type ShowToastTheme = 'error' | 'primary' | 'success' | 'warning';

export type ToastContainer = MaybeRefOrGetter<HTMLElement | null | undefined>;

export type ToastFn = (options: ShowToastOptions) => void;

export const TOAST_CONTAINER_TOKEN: InjectionKey<ToastContainer> = Symbol('TOAST_CONTAINER_TOKEN');

/**
 * 弹出 bkui Message。传入 container 时挂到该元素内（Message 改为 absolute 定位），否则挂 document.body。
 */
export const showToast = (options: ShowToastOptions, container?: HTMLElement | null): void => {
  Message({
    ...options,
    ...(container ? { getContainer: container } : {}),
  });
};

/**
 * 由宿主声明 toast 挂载容器，供后代组件的 useToast 使用。
 * 宿主自身处于高层叠上下文（如 fixed 浮层）时，Message 挂 body 会被挡住，需要挂进宿主内部。
 */
export const useToastContainerProvider = (container: ToastContainer): void => {
  provide(TOAST_CONTAINER_TOKEN, container);
};

export const useToastContainerInject = (): ToastContainer | undefined => {
  return hasInjectionContext() ? inject(TOAST_CONTAINER_TOKEN, undefined) : undefined;
};

/**
 * 返回绑定了注入容器的 toast 方法；须在 setup 中调用，容器在每次弹出时读取。
 */
export const useToast = (): ToastFn => {
  const container = useToastContainerInject();
  return options => showToast(options, toValue(container));
};
