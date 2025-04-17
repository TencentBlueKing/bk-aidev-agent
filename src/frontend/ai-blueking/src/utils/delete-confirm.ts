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
import { h, render } from 'vue';

import tippy, { type Instance as TippyInstance, type Props as TippyProps } from 'tippy.js';

import DeleteConfirmVue from '../components/delete-confirm.vue';

import 'tippy.js/dist/tippy.css';

// 删除确认实例集合
const confirmInstances: Map<Element, TippyInstance> = new Map();

/**
 * 创建删除确认框
 * @param target 目标元素
 * @param options 配置选项
 * @returns Tippy实例
 */
export function createDeleteConfirm(
  target: Element | null | string,
  options: {
    onConfirm: () => void;
    onCancel?: () => void;
    placement?: TippyProps['placement'];
    title?: string;
    content?: string;
    appendTo?: TippyProps['appendTo'];
  },
): TippyInstance | undefined {
  // 如果target是选择器字符串，则获取对应元素
  const element = typeof target === 'string' ? document.querySelector(target) : target;

  if (!element) {
    console.error('Target element not found');
    return undefined;
  }

  // 如果该元素已有删除确认框，则返回已有实例
  if (confirmInstances.has(element)) {
    const instance = confirmInstances.get(element);
    instance?.show();
    return instance;
  }

  // 创建props
  const compProps = {
    onConfirm: () => {
      // 执行回调
      options.onConfirm();
      // 关闭并删除tippy实例
      instance?.hide();
      confirmInstances.delete(element);
    },
    onCancel: () => {
      // 关闭并删除tippy实例
      instance?.hide();
      confirmInstances.delete(element);
      options.onCancel?.();
    },
    title: options.title,
    content: options.content,
  };

  // 创建挂载点
  const mountPoint = document.createElement('div');

  // 渲染组件
  const vnode = h(DeleteConfirmVue, compProps);
  render(vnode, mountPoint);

  // 创建tippy实例
  const instance = tippy(element, {
    content: mountPoint,
    interactive: true,
    trigger: 'manual', // 手动触发，避免点击时多次触发
    theme: 'white',
    placement: options.placement || 'top',
    arrow: true,
    appendTo: options.appendTo || document.body,
    hideOnClick: true,
    animation: 'scale',
    duration: 200,
    delay: [0, 0],
    // 隐藏时销毁组件
    onHidden: () => {
      // 在完全隐藏后销毁组件内容，避免过早清理导致动画不流畅
      setTimeout(() => {
        confirmInstances.delete(element);
        render(null, mountPoint);
      }, 200);
    },
  });

  // 存储实例
  confirmInstances.set(element, instance);

  // 关闭函数，优化实例的隐藏和清理过程
  const close = () => {
    instance.hide();
  };

  // 修改props中的回调，优化关闭流程
  compProps.onConfirm = () => {
    options.onConfirm();
    close();
  };

  compProps.onCancel = () => {
    options.onCancel?.();
    close();
  };

  // 显示
  instance.show();

  return instance;
}

/**
 * 关闭所有删除确认框
 */
export function closeAllDeleteConfirms(): void {
  confirmInstances.forEach(instance => {
    instance.hide();
  });
}
