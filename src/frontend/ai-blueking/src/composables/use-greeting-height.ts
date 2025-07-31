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
import { ref, nextTick } from 'vue';
import type { ComponentPublicInstance } from 'vue';

interface GreetingSectionInstance extends ComponentPublicInstance {
  getGreetingHeight: () => number;
}

interface UseGreetingHeightOptions {
  greetingMaxHeight: number;
}

/**
 * 问候语高度计算的组合式函数
 *
 * @param options 配置选项
 * @returns 相关的状态和方法
 */
export function useGreetingHeight(options: UseGreetingHeightOptions) {
  const { greetingMaxHeight } = options;

  // 问候语文本高度
  const greetingTextHeight = ref(0);

  // 问候语组件引用
  const greetingSectionRef = ref<GreetingSectionInstance>();

  /**
   * 更新问候语文本高度
   */
  const updateGreetingTextHeight = () => {
    nextTick(() => {
      if (greetingSectionRef.value) {
        greetingTextHeight.value = greetingSectionRef.value.getGreetingHeight();
      }
    });
  };

  /**
   * 计算输入框的动态位置样式
   */
  const getInputContainerStyle = (hasSessionContents: boolean) => {
    if (!hasSessionContents) {
      // 当没有消息时，根据 greeting text 的高度动态调整位置
      const baseTop = 188; // 原始的 top 值
      const greetingHeight = greetingTextHeight.value;

      // 如果 greeting text 超过了基础高度，需要向下调整输入框位置
      const additionalOffset = Math.min(greetingHeight - 22, greetingMaxHeight - 22); // 22 是单行高度
      const dynamicTop = baseTop + Math.max(0, additionalOffset);

      return {
        top: `${dynamicTop}px`,
      };
    }
    return {};
  };

  return {
    greetingTextHeight,
    greetingSectionRef,
    updateGreetingTextHeight,
    getInputContainerStyle,
  };
}
