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
// use-select.ts
import { ref, onMounted, onBeforeUnmount } from 'vue';

const selectedText = ref('');
const citeText = ref('');
const lockSelectedText = ref(false); // 外面组件比如输入框组件 focus 时需要锁定，防止引用被清空
// 添加类型定义和常量配置

interface Position {
  top: string;
  left: string;
}

const POPUP_CONFIG = {
  width: 80,
  height: 34,
  offset: 15,
  debounceTime: 300,
} as const;

export function useSelect(enablePopup: boolean) {
  const isIconVisible = ref(false);
  const iconPosition = ref<Position>({ top: '0px', left: '0px' });
  let debounceTimeout: ReturnType<typeof setTimeout>;
  let lastMouseUpEvent: MouseEvent | null = null;
  const popupRef = ref<HTMLElement | null>(null);

  // 增加的变量
  let isTextSelected = false;
  let mouseDownPosition: { x: number; y: number } | null = null;

  const handleMouseDown = (event: MouseEvent) => {
    mouseDownPosition = { x: event.clientX, y: event.clientY };
  };

  const handleMouseUp = (event: MouseEvent) => {
    lastMouseUpEvent = event;
    if (mouseDownPosition) {
      // 比较 mousedown 和 mouseup 的位置
      const distance = Math.sqrt(
        Math.pow(event.clientX - mouseDownPosition.x, 2) + Math.pow(event.clientY - mouseDownPosition.y, 2),
      );
      // 如果距离大于一个阈值（例如 5px），则认为是文本选择
      isTextSelected = distance > 5;
    }
    mouseDownPosition = null; // 清理
  };

  const calculatePopupPositionFromMouse = (clientX: number, clientY: number): Position => {
    const viewportWidth = window.innerWidth;
    const { width: popupWidth, height: popupHeight, offset } = POPUP_CONFIG;

    let left = clientX + window.scrollX - popupWidth / 2;
    left = Math.max(offset, Math.min(left, viewportWidth - popupWidth - offset));

    let top = clientY + window.scrollY - popupHeight - offset;
    if (clientY <= popupHeight + offset) {
      top = clientY + window.scrollY + offset;
    }

    return {
      top: `${top}px`,
      left: `${left}px`,
    };
  };

  // 计算弹窗位置的通用函数（基于 Range）
  const calculatePopupPositionFromRange = (rect: DOMRect): Position => {
    const viewportWidth = window.innerWidth;
    const { width: popupWidth, height: popupHeight, offset } = POPUP_CONFIG;

    let left = rect.left + window.scrollX + rect.width / 2 - popupWidth / 2;
    left = Math.max(offset, Math.min(left, viewportWidth - popupWidth - offset));

    let top = rect.top + window.scrollY - popupHeight - offset;
    if (rect.top <= popupHeight + offset) {
      top = rect.bottom + window.scrollY + offset;
    }

    return {
      top: `${top}px`,
      left: `${left}px`,
    };
  };

  const handleSelectionChange = () => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      const selection = window.getSelection();
      if (!selection?.toString().trim()) {
        hideIcon();
        return;
      }

      const range = selection.getRangeAt(0);
      if (range.commonAncestorContainer.parentElement?.closest('.ai-blueking-wrapper')) {
        hideIcon();
        return;
      }

      lockSelectedText.value = false;
      selectedText.value = selection.toString().trim();
      // 判断是否在 textarea 内
      const activeElement = document.activeElement;
      if (activeElement?.tagName === 'TEXTAREA') {
        // textarea 内，使用鼠标位置
        if (!lastMouseUpEvent) {
          hideIcon();
          return;
        }

        const { clientX, clientY } = lastMouseUpEvent;
        iconPosition.value = calculatePopupPositionFromMouse(clientX, clientY);
        isIconVisible.value = true;
        lastMouseUpEvent = null; // 清理
      } else {
        // 非 textarea，使用 Range 计算位置
        const rect = range.getBoundingClientRect();
        if (!rect.width || !rect.height) {
          hideIcon();
          return;
        }
        iconPosition.value = calculatePopupPositionFromRange(rect);
        isIconVisible.value = true;
      }
    }, POPUP_CONFIG.debounceTime);
  };

  const hideIcon = () => {
    isIconVisible.value = false;
    if (!lockSelectedText.value) {
      selectedText.value = ''; // 不能使用 clearSelection， 会导致 input框无法 focus
    }
  };

  const handleClickOutside = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    const isTargetTagText =
      target.classList?.contains('ai-blueking-tag-text') || target.classList?.contains('shortcut-btn');
    const isPopupContainsTarget = popupRef.value?.contains(target);

    // 处理标签文本的点击
    if (isTargetTagText || !isTextSelected) {
      return;
    }

    // 处理文本选择
    if (isTextSelected) {
      event.preventDefault();
      event.stopPropagation();
      isTextSelected = false;
      return;
    }

    // 处理点击弹窗外部
    if (!isPopupContainsTarget) {
      hideIcon();
      clearSelection();
    }
  };

  const clearSelection = () => {
    const selection = window.getSelection();
    if (selection) {
      selection.removeAllRanges();
    }
    selectedText.value = '';
  };
  const setSelection = (text: string) => {
    selectedText.value = text;
  };
  const setCiteText = (text: string) => {
    citeText.value = text;
  };

  onMounted(() => {
    if (enablePopup) {
      document.addEventListener('selectionchange', handleSelectionChange);
      document.addEventListener('mousedown', handleMouseDown);
      document.addEventListener('mouseup', handleMouseUp);
      document.addEventListener('click', handleClickOutside, true); // 捕获阶段
    }
  });

  onBeforeUnmount(() => {
    if (enablePopup) {
      document.removeEventListener('selectionchange', handleSelectionChange);
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('click', handleClickOutside, true);
    }
    clearTimeout(debounceTimeout);
  });

  return {
    isIconVisible,
    iconPosition,
    selectedText,
    citeText,
    hideIcon,
    clearSelection,
    setSelection,
    setCiteText,
    lockSelectedText,
    popupRef,
  };
}
