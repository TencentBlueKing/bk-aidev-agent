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

import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';

/**
 * 可调整大小容器的配置选项
 */
interface ResizableContainerOptions {
  /** 初始宽度，默认为 400px */
  initWidth?: number;
  /** 最小宽度，默认为 400px */
  minWidth?: number;
  /** 最小高度，默认为 400px */
  minHeight?: number;
  /** 屏幕最大宽度的百分比，默认为 40% */
  maxWidthPercent?: number;
  /** 最小高度，默认为 800px */
  miniHeight?: number;
}

/**
 * 使用可调整大小的容器
 * 合并了 use-main-container 和原 use-resizable-container 的功能
 * @param options 配置选项
 * @returns 容器的属性和方法
 */
export function useResizableContainer(options: ResizableContainerOptions = {}) {
  // 初始化参数
  const initWidth = options.initWidth || 400;
  const minWidth = options.minWidth || 400;
  const minHeight = options.minHeight || 400;
  const maxWidthPercent = options.maxWidthPercent || 40;
  const miniHeight = options.miniHeight || 800;
  const miniPadding = 50;

  // 状态管理
  const initialX = ref(window.innerWidth - initWidth);
  const top = ref(0);
  const left = ref(initialX.value);
  const width = ref(initWidth);
  const height = ref(window.innerHeight);
  const maxWidth = ref(window.innerWidth * (maxWidthPercent / 100));
  const isCompressionHeight = ref(false);
  const leftDiff = ref(0);

  // 事件处理
  const handleDragging = (x: number, y: number) => {
    left.value = x;
    top.value = y;
    leftDiff.value = x - (window.innerWidth - width.value);
  };

  const handleResizing = (x: number, y: number, w: number, h: number) => {
    left.value = x;
    top.value = y;
    // 确保宽度不超过最大值
    width.value = Math.min(w, maxWidth.value);
    height.value = h;
  };

  // 窗口大小变化处理器
  const handleResize = () => {
    // 更新最大宽度
    maxWidth.value = window.innerWidth * (maxWidthPercent / 100);

    nextTick(() => {
      if (isCompressionHeight.value) {
        // 压缩状态下，保持容器贴在右侧，保留间距（miniPadding)
        left.value = window.innerWidth - width.value - miniPadding;
        top.value = window.innerHeight - miniHeight - miniPadding;
      } else {
        // 正常状态下，保持容器贴在右侧
        const newLeft = window.innerWidth - width.value - leftDiff.value;
        left.value = Math.max(0, newLeft);
        height.value = window.innerHeight;
      }

      // 检查并调整宽度，确保不会超出最大限制
      if (width.value > maxWidth.value) {
        width.value = maxWidth.value;
      }
    });
  };

  // 切换压缩高度
  const toggleCompression = () => {
    if (isCompressionHeight.value) {
      top.value = 0;
      nextTick(() => {
        height.value = window.innerHeight;
        left.value = initialX.value;
        width.value = initWidth;
      });
    } else {
      top.value = window.innerHeight - miniHeight - miniPadding;
      left.value = initialX.value - miniPadding;
      width.value = initWidth;
      height.value = miniHeight;
    }
    isCompressionHeight.value = !isCompressionHeight.value;
  };

  // 生命周期钩子
  onMounted(() => {
    window.addEventListener('resize', handleResize);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize);
  });

  return {
    // 基本属性
    minWidth,
    minHeight,
    maxWidth,
    top,
    left,
    width,
    height,
    isCompressionHeight,

    // 事件处理方法
    handleDragging,
    handleResizing,
    toggleCompression,
  };
}
