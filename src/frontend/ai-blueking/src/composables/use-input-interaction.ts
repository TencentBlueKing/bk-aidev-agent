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

import { ref, Ref } from 'vue';

/**
 * 输入交互配置选项
 */
interface InputInteractionOptions {
  /** 发送消息的函数 */
  onSend?: (text: string) => void;
  /** 停止生成的函数 */
  onStop?: () => void;
  /** 是否处于加载状态 */
  isLoading?: Ref<boolean>;
  /** 输入内容获取函数 */
  getInputValue?: () => string;
  /** 清空输入内容的函数 */
  clearInput?: () => void;
}

/**
 * 使用输入交互
 * 处理文本输入的交互逻辑，包括Enter键处理和输入法组合输入状态
 */
export function useInputInteraction(options: InputInteractionOptions = {}) {
  // 组合输入状态（用于处理中文、日文等输入法）
  const isComposing = ref(false);

  /**
   * 处理输入法组合开始
   */
  const handleCompositionStart = () => {
    isComposing.value = true;
  };

  /**
   * 处理输入法组合结束
   */
  const handleCompositionEnd = () => {
    isComposing.value = false;
  };

  /**
   * 处理Enter键按下事件
   * @param e 键盘事件
   */
  const handleEnter = (e: KeyboardEvent) => {
    // 获取当前配置
    const { isLoading, onSend, getInputValue = () => '', clearInput = () => {} } = options;

    // Shift + Enter 换行，保持默认行为
    if (e.shiftKey) return;

    // 阻止默认的换行行为
    e.preventDefault();

    // 如果正在组合输入、加载中或输入为空，不执行发送操作
    const inputValue = getInputValue();
    if (isLoading?.value || !inputValue.trim() || isComposing.value) return;

    // 发送消息
    onSend?.(inputValue);
    clearInput();
  };

  /**
   * 处理发送事件
   */
  const handleSend = () => {
    // 获取当前配置
    const { onSend, getInputValue = () => '', clearInput = () => {} } = options;

    const inputValue = getInputValue();
    if (!inputValue.trim()) return;

    onSend?.(inputValue);
    clearInput();
  };

  /**
   * 处理停止事件
   */
  const handleStop = () => {
    const { onStop } = options;
    onStop?.();
  };

  return {
    isComposing,
    handleCompositionStart,
    handleCompositionEnd,
    handleEnter,
    handleSend,
    handleStop,
  };
}
