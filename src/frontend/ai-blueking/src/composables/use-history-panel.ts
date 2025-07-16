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

import tippy, { type Instance } from 'tippy.js';
import { ref, h, render, onBeforeUnmount, type Ref, type Component } from 'vue';

export interface HistoryPanelOptions {
  /** 触发元素的 ref */
  triggerRef: Ref<HTMLElement | null>;
  /** 历史面板组件 */
  panelComponent: Component;
  /** 面板组件的 props */
  panelProps?: Record<string, any>;
  /** tippy 配置选项 */
  tippyOptions?: {
    placement?: 'bottom-end' | 'bottom-start' | 'bottom' | 'top-end' | 'top-start' | 'top';
    offset?: [number, number];
    appendTo?: HTMLElement | (() => HTMLElement) | 'parent';
  };
}

/**
 * 历史面板 Composable
 * 用于管理基于 tippy.js 的历史面板显示逻辑
 */
export function useHistoryPanel(options: HistoryPanelOptions) {
  const { triggerRef, panelComponent, panelProps = {}, tippyOptions = {} } = options;

  // tippy 实例
  const tippyInstance = ref<Instance | null>(null);

  // 面板挂载点，保持引用避免重复创建
  let mountPoint: HTMLElement | null = null;

  /**
   * 创建面板内容
   */
  const createPanelContent = () => {
    if (!mountPoint) {
      mountPoint = document.createElement('div');
    }

    // 每次都重新渲染组件内容，确保数据是最新的
    const vnode = h(panelComponent, {
      ...panelProps,
      onClose: hide, // 传递关闭方法给面板组件
    });
    render(vnode, mountPoint);

    return mountPoint;
  };

  /**
   * 处理文档点击事件，实现点击外部关闭功能
   */
  const handleDocumentClick = (event: Event) => {
    const target = event.target as Element;
    const triggerElement = triggerRef.value;

    // 如果点击的是触发元素，不处理（让触发元素的点击事件处理）
    if (triggerElement && triggerElement.contains(target)) {
      return;
    }

    // 查找历史面板的 tippy 元素
    const historyTippyBox = document.querySelector('.tippy-box[data-theme~="history-panel"]');

    // 如果点击的是面板内容，不关闭面板
    if (historyTippyBox && historyTippyBox.contains(target)) {
      return;
    }

    // 否则关闭面板
    if (tippyInstance.value?.state.isVisible) {
      tippyInstance.value.hide();
    }
  };

  /**
   * 创建 tippy 实例
   */
  const createTippyInstance = () => {
    if (!triggerRef.value || tippyInstance.value) return;

    const defaultOptions = {
      placement: 'bottom-end' as const,
      offset: [0, 8] as [number, number],
      appendTo: document.querySelector('.ai-blueking-container-wrapper') || document.body,
    };

    tippyInstance.value = tippy(triggerRef.value, {
      content: createPanelContent(),
      interactive: true,
      trigger: 'manual',
      theme: 'light history-panel',
      arrow: false,
      hideOnClick: false,
      animation: 'scale',
      duration: 200,
      delay: [0, 0],
      ...defaultOptions,
      ...tippyOptions,
      // 每次显示前更新内容
      onShow: () => {
        if (tippyInstance.value && mountPoint) {
          tippyInstance.value.setContent(createPanelContent());
        }
        // 添加全局点击监听器
        setTimeout(() => {
          document.addEventListener('click', handleDocumentClick, false);
        }, 0);
      },
      // 隐藏时移除全局点击监听器
      onHidden: () => {
        document.removeEventListener('click', handleDocumentClick, false);
      },
    });
  };

  /**
   * 显示面板
   */
  const show = () => {
    if (!tippyInstance.value) {
      createTippyInstance();
    }
    tippyInstance.value?.show();
  };

  /**
   * 隐藏面板
   */
  const hide = () => {
    tippyInstance.value?.hide();
  };

  /**
   * 切换面板显示状态
   */
  const toggle = () => {
    if (!tippyInstance.value) {
      createTippyInstance();
    }

    if (tippyInstance.value?.state.isVisible) {
      hide();
    } else {
      show();
    }
  };

  /**
   * 处理触发元素点击
   */
  const handleTriggerClick = (event: Event) => {
    // 阻止事件冒泡，避免触发全局点击监听器
    event.stopPropagation();
    toggle();
  };

  /**
   * 销毁 tippy 实例和清理资源
   */
  const destroy = () => {
    if (tippyInstance.value) {
      tippyInstance.value.destroy();
      tippyInstance.value = null;
    }

    // 清理挂载点
    if (mountPoint) {
      render(null, mountPoint);
      mountPoint = null;
    }

    // 移除全局监听器（防止内存泄漏）
    document.removeEventListener('click', handleDocumentClick, false);
  };

  // 组件卸载时自动清理
  onBeforeUnmount(() => {
    destroy();
  });

  return {
    show,
    hide,
    toggle,
    handleTriggerClick,
    destroy,
    isVisible: () => tippyInstance.value?.state.isVisible ?? false,
  };
}
