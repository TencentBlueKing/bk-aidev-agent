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
import { ref } from 'vue';

interface TextareaHeightOptions {
  minHeight?: number;
  maxHeight?: number;
  defaultHeight?: number;
  debounceTime?: number;
}

/**
 * 文本区域高度自适应的组合式函数
 *
 * @param options 配置选项
 * @returns 相关的状态和方法
 */
export function useTextareaHeight(options: TextareaHeightOptions = {}) {
  const { minHeight = 68, maxHeight = 248, defaultHeight = 68 } = options;

  // 响应式的高度值
  const textareaHeight = ref(defaultHeight);

  // 文本区域元素引用
  const textareaRef = ref<HTMLTextAreaElement>();

  /**
   * 更新文本区域高度
   */
  const updateHeight = () => {
    if (!textareaRef.value) return;

    // 重置高度以获取实际内容高度
    textareaRef.value.style.height = `${minHeight}px`;

    // 计算内容实际高度
    const scrollHeight = textareaRef.value.scrollHeight;

    // 设置新高度，确保在最小值和最大值之间
    textareaHeight.value = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
  };

  /**
   * 重置高度到默认值
   */
  const resetHeight = () => {
    textareaHeight.value = defaultHeight;
  };

  /**
   * 监听文本区域内容变化以更新高度
   * @param textareaElement 文本区域元素
   */
  const bindTextarea = (textareaElement: HTMLTextAreaElement) => {
    textareaRef.value = textareaElement;

    // 初始更新一次高度
    updateHeight();
  };

  return {
    textareaHeight,
    textareaRef,
    updateHeight,
    resetHeight,
    bindTextarea,
  };
}
