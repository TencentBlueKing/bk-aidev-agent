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
import { onMounted, onBeforeUnmount, Ref } from 'vue';

import { isTogglePanelShortcut } from '../utils/platform';

export interface KeyboardShortcutOptions {
  /** 是否启用快捷键 */
  enabled?: Ref<boolean> | boolean;
  /** 面板是否显示 */
  isShow?: Ref<boolean>;
  /** 显示面板的回调 */
  onShow?: () => void;
  /** 隐藏面板的回调 */
  onHide?: () => void;
}

/**
 * 键盘快捷键管理 Composable
 *
 * @description
 * 管理全局键盘快捷键，目前支持：
 * - Cmd/Ctrl + I: 切换面板显示/隐藏
 *
 * @example
 * ```ts
 * const { registerTogglePanelShortcut } = useKeyboardShortcut({
 *   enabled: computed(() => !props.hideNimbus),
 *   isShow,
 *   onShow: handleShow,
 *   onHide: handleClose,
 * });
 * ```
 */
export function useKeyboardShortcut(options: KeyboardShortcutOptions = {}) {
  const { enabled = true, isShow, onShow, onHide } = options;

  /**
   * 处理切换面板的快捷键
   */
  const handleTogglePanelShortcut = (event: KeyboardEvent) => {
    // 检查是否启用
    const isEnabled = typeof enabled === 'boolean' ? enabled : enabled.value;
    if (!isEnabled) return;

    // 检测 Cmd/Ctrl + I 快捷键
    if (isTogglePanelShortcut(event)) {
      event.preventDefault(); // 阻止默认行为（如浏览器斜体）
      event.stopPropagation(); // 阻止事件冒泡

      // 切换面板显示状态
      const currentShowState = isShow ? isShow.value : false;
      if (currentShowState) {
        onHide?.();
      } else {
        onShow?.();
      }
    }
  };

  /**
   * 注册快捷键监听
   */
  const registerTogglePanelShortcut = () => {
    window.addEventListener('keydown', handleTogglePanelShortcut);
  };

  /**
   * 注销快捷键监听
   */
  const unregisterTogglePanelShortcut = () => {
    window.removeEventListener('keydown', handleTogglePanelShortcut);
  };

  // 自动注册和注销
  onMounted(() => {
    registerTogglePanelShortcut();
  });

  onBeforeUnmount(() => {
    unregisterTogglePanelShortcut();
  });

  return {
    registerTogglePanelShortcut,
    unregisterTogglePanelShortcut,
    handleTogglePanelShortcut,
  };
}
