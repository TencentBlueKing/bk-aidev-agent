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

/**
 * 问候语高度计算的组合式函数
 * 管理问候语组件的引用和高度状态
 *
 * @returns 问候语高度相关的状态和方法
 */
export function useGreetingHeight() {
  // 问候语文本高度
  const greetingTextHeight = ref(0);

  // 问候语组件引用
  const greetingSectionRef = ref<GreetingSectionInstance>();

  /**
   * 更新问候语文本高度
   * 从 greeting-section 组件获取实际的 DOM 高度
   */
  const updateGreetingTextHeight = () => {
    nextTick(() => {
      if (greetingSectionRef.value) {
        greetingTextHeight.value = greetingSectionRef.value.getGreetingHeight();
      }
    });
  };

  return {
    greetingTextHeight,
    greetingSectionRef,
    updateGreetingTextHeight,
  };
}
