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
import { onBeforeUnmount, ref, Ref } from 'vue';

import tippy, { Instance, Props } from 'tippy.js';

import 'tippy.js/dist/tippy.css';

export type TooltipOptions = Partial<Props>;

export interface TooltipTarget {
  element: Element | string;
  content: string;
  options?: TooltipOptions;
}

// 添加返回类型接口
interface TooltipAPI {
  instances: Ref<Instance[]>;
  createTooltip: (element: Element | string, content: string, options?: TooltipOptions) => Instance | null;
  createTooltipsForSelector: (selector: string, content: string, options?: TooltipOptions) => Instance[];
  createMultipleTooltips: (targets: TooltipTarget[]) => Instance[];
  destroyAll: () => void;
  updateContent: (instance: Instance, content: string) => void;
  destroyInstance: (instance: Instance) => void;
}

/**
 * Composable for managing tippy tooltips
 * @param defaultOptions - Default options for all tooltips
 * @returns Tooltip utility functions
 */
export function useTooltip(defaultOptions: TooltipOptions = {}): TooltipAPI {
  // 添加默认的类名
  const defaultThemeClass = 'ai-blueking-tooltip';

  // 确保在页面中添加自定义样式
  const addCustomStyles = () => {
    if (!document.getElementById('ai-blueking-tooltip-styles')) {
      const styleEl = document.createElement('style');
      styleEl.id = 'ai-blueking-tooltip-styles';
      styleEl.textContent = `
        .ai-blueking-tooltip {
          font-size: 12px !important;
        }
        .tippy-box {
          font-size: 12px !important;
        }
      `;
      document.head.appendChild(styleEl);
    }
  };

  // 添加自定义样式
  addCustomStyles();

  const instances = ref<Instance[]>([]);

  /**
   * Create a tooltip for a single element
   * @param element - DOM element or selector
   * @param content - Tooltip content
   * @param options - Tooltip options
   * @returns Tooltip instance
   */
  const createTooltip = (element: Element | string, content: string, options: TooltipOptions = {}): Instance | null => {
    try {
      // 如果传入的是选择器字符串，获取对应的元素
      const targetElement = typeof element === 'string' ? document.querySelector(element) : element;

      if (!targetElement) {
        console.warn(`Tooltip target not found: ${element}`);
        return null;
      }

      // 合并默认选项和自定义选项
      const mergedOptions: TooltipOptions = {
        content,
        placement: 'top',
        arrow: true,
        delay: [300, 0],
        theme: defaultThemeClass, // 使用自定义主题
        ...defaultOptions,
        ...options,
      };

      const instance = tippy(targetElement, mergedOptions);
      instances.value.push(instance);
      return instance;
    } catch (error) {
      console.error('Failed to create tooltip:', error);
      return null;
    }
  };

  /**
   * Create tooltips for multiple elements
   * @param selector - CSS selector for target elements
   * @param content - Tooltip content
   * @param options - Tooltip options
   * @returns Array of tooltip instances
   */
  const createTooltipsForSelector = (selector: string, content: string, options: TooltipOptions = {}): Instance[] => {
    const elements = document.querySelectorAll(selector);
    const newInstances: Instance[] = [];

    elements.forEach(el => {
      const instance = createTooltip(el, content, options);
      if (instance) {
        newInstances.push(instance);
      }
    });

    return newInstances;
  };

  /**
   * Create multiple tooltips with different configurations
   * @param targets - Array of tooltip targets with content and options
   * @returns Array of tooltip instances
   */
  const createMultipleTooltips = (targets: TooltipTarget[]): Instance[] => {
    const newInstances: Instance[] = [];

    targets.forEach(({ element, content, options }) => {
      const instance = createTooltip(element, content, options);
      if (instance) {
        newInstances.push(instance);
      }
    });

    return newInstances;
  };

  /**
   * Destroy all tooltip instances
   */
  const destroyAll = () => {
    instances.value.forEach(instance => {
      instance.destroy();
    });
    instances.value = [];
  };

  /**
   * Update tooltip content
   * @param instance - Tooltip instance
   * @param content - New content
   */
  const updateContent = (instance: Instance, content: string) => {
    instance.setContent(content);
  };

  const destroyInstance = (instance: Instance) => {
    instance.destroy();
  };

  // 组件卸载时自动清理所有工具提示实例
  onBeforeUnmount(() => {
    destroyAll();
  });

  return {
    instances,
    createTooltip,
    createTooltipsForSelector,
    createMultipleTooltips,
    destroyAll,
    updateContent,
    destroyInstance,
  };
}
