/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

import type { PositionAndSize, UseDraggableOptions, UseDraggableReturn } from './types';

/**
 * 可拖拽容器的逻辑 Hook
 *
 * 封装了容器的拖拽、缩放、位置管理等逻辑
 * 可独立使用，也可与 DraggableContainer 组件配合使用
 *
 * @param options 配置选项
 * @param callbacks 回调函数
 */
export function useDraggable(
  options: UseDraggableOptions = {},
  callbacks?: {
    onDragging?: (position: PositionAndSize) => void;
    onDragStop?: (position: PositionAndSize) => void;
    onResizeStop?: (position: PositionAndSize) => void;
    onResizing?: (position: PositionAndSize) => void;
  },
): UseDraggableReturn {
  // 初始化参数
  const initWidth = options.initWidth || 400;
  const minWidth = options.minWidth || 400;
  const minHeight = options.minHeight || 400;
  const maxWidthPercent = options.maxWidthPercent || 40;
  const compressedHeight = options.compressedHeight || 800;
  const compressedPadding = options.compressedPadding !== undefined ? options.compressedPadding : 0;

  // 计算初始位置
  const initialX = ref(options.defaultLeft !== undefined ? options.defaultLeft : window.innerWidth - initWidth);
  const initialTop = ref(options.defaultTop !== undefined ? options.defaultTop : 0);
  // 初始高度：如果未指定 defaultHeight，则占满窗口高度（减去 top 偏移）
  const initialHeight = ref(
    options.defaultHeight !== undefined
      ? options.defaultHeight
      : window.innerHeight - (options.defaultTop !== undefined ? options.defaultTop : 0),
  );
  const initialWidth = ref(initWidth);

  // 状态管理
  const top = ref(initialTop.value);
  const left = ref(initialX.value);
  const width = ref(initialWidth.value);
  const height = ref(initialHeight.value);
  const maxWidth = ref(Math.max(window.innerWidth * (maxWidthPercent / 100), width.value));
  const isCompressed = ref(false);
  const leftDiff = ref(0);

  // 侧面板展开状态：记忆收起/展开两种布局
  let collapsedPosition: null | PositionAndSize = null;
  let expandedPosition: null | PositionAndSize = null;
  const isSidePanelExpanded = ref(false);

  /**
   * 将目标位置和尺寸约束到视口内
   */
  const clampToViewport = (target: PositionAndSize): PositionAndSize => {
    const viewportWidth = window.innerWidth;
    const clamped = { ...target };
    if (clamped.width > viewportWidth) clamped.width = viewportWidth;
    const rightEdge = clamped.x + clamped.width;
    if (rightEdge > viewportWidth) clamped.x = viewportWidth - clamped.width;
    if (clamped.x < 0) clamped.x = 0;
    return clamped;
  };

  /**
   * 获取当前位置和大小
   */
  const getPositionAndSize = (): PositionAndSize => ({
    x: left.value,
    y: top.value,
    width: width.value,
    height: height.value,
  });

  /**
   * 处理拖拽中
   */
  const handleDragging = (x: number, y: number): void => {
    left.value = x;
    top.value = y;
    leftDiff.value = x - (window.innerWidth - width.value);

    callbacks?.onDragging?.(getPositionAndSize());
  };

  /**
   * 处理调整大小中
   */
  const handleResizing = (x: number, y: number, w: number, h: number): void => {
    left.value = x;
    top.value = y;
    // 确保宽度不超过最大值
    width.value = Math.min(w, maxWidth.value);
    height.value = h;

    callbacks?.onResizing?.(getPositionAndSize());
  };

  /**
   * 处理拖拽停止
   */
  const handleDragStop = (x: number, y: number): void => {
    left.value = x;
    top.value = y;
    leftDiff.value = x - (window.innerWidth - width.value);
    if (isSidePanelExpanded.value) {
      expandedPosition = getPositionAndSize();
    }
    callbacks?.onDragStop?.(getPositionAndSize());
  };

  /**
   * 处理调整大小停止
   */
  const handleResizeStop = (x: number, y: number, w: number, h: number): void => {
    left.value = x;
    top.value = y;
    // 确保宽度不超过最大值
    width.value = Math.min(w, maxWidth.value);
    height.value = h;
    if (isSidePanelExpanded.value) {
      expandedPosition = getPositionAndSize();
    }
    callbacks?.onResizeStop?.(getPositionAndSize());
  };

  /**
   * 窗口大小变化处理器
   */
  const handleWindowResize = (): void => {
    // 更新最大宽度
    maxWidth.value = Math.max(window.innerWidth * (maxWidthPercent / 100), width.value);

    nextTick(() => {
      if (isCompressed.value) {
        // 压缩状态下，保持容器贴在右侧，保留间距
        left.value = window.innerWidth - width.value - compressedPadding;
        top.value = window.innerHeight - compressedHeight - compressedPadding;
      } else {
        // 正常状态下，保持容器贴在右侧
        const newLeft = window.innerWidth - width.value - leftDiff.value;
        left.value = Math.max(0, newLeft);
        setTimeout(() => {
          height.value = window.innerHeight - top.value;
        }, 0);
      }

      // 检查并调整宽度，确保不会超出最大限制
      if (width.value > maxWidth.value) {
        width.value = maxWidth.value;
      }
    });
  };

  /**
   * 切换压缩状态
   */
  const toggleCompression = (): void => {
    if (isCompressed.value) {
      // 恢复到用户设置的初始位置和尺寸
      top.value = initialTop.value;
      nextTick(() => {
        height.value = initialHeight.value;
        left.value = initialX.value;
        width.value = initialWidth.value;
      });
    } else {
      // 切换到压缩状态
      top.value = window.innerHeight - compressedHeight - compressedPadding;
      left.value = initialX.value - compressedPadding;
      width.value = initWidth;
      height.value = compressedHeight;
    }
    isCompressed.value = !isCompressed.value;
  };

  /**
   * 编程式更新位置
   */
  const updatePosition = (x: number, y: number): void => {
    left.value = x;
    top.value = y;
    leftDiff.value = x - (window.innerWidth - width.value);
  };

  /**
   * 编程式更新大小
   */
  const updateSize = (w: number, h: number): void => {
    // 确保宽度不超过最大值和最小值
    width.value = Math.max(minWidth, Math.min(w, maxWidth.value));
    // 确保高度不低于最小值
    height.value = Math.max(minHeight, h);
  };

  /**
   * 同时更新位置和大小
   */
  const updatePositionAndSize = (x: number, y: number, w: number, h: number): void => {
    updatePosition(x, y);
    updateSize(w, h);
  };

  /**
   * 为侧面板展开扩展容器宽度（视觉上向左展开，右边缘保持不动）
   *
   * 策略：固定右边缘、宽度记忆、clampToViewport、两阶段 nextTick 编排
   *
   * @param extraWidth 首次展开时需要增加的宽度（像素）
   */
  const expandForSidePanel = (extraWidth: number): void => {
    if (isSidePanelExpanded.value) return;
    const current = getPositionAndSize();
    collapsedPosition = { ...current };
    isSidePanelExpanded.value = true;

    const currentRightEdge = current.x + current.width;
    const targetWidth = expandedPosition?.width ?? current.width + extraWidth;
    const targetX = currentRightEdge - targetWidth;

    const target = clampToViewport({
      x: targetX,
      y: current.y,
      width: targetWidth,
      height: current.height,
    });

    updatePosition(target.x, target.y);
    nextTick(() => {
      updateSize(target.width, target.height);
    });
  };

  /**
   * 折叠侧面板并恢复容器到收起布局（视觉上向右收缩，右边缘保持不动）
   */
  const collapseSidePanel = (): void => {
    if (!isSidePanelExpanded.value) return;
    const current = getPositionAndSize();
    expandedPosition = { ...current };
    isSidePanelExpanded.value = false;

    const currentRightEdge = current.x + current.width;
    const targetWidth = collapsedPosition?.width ?? current.width;
    const targetX = currentRightEdge - targetWidth;

    const target = clampToViewport({
      x: targetX,
      y: current.y,
      width: targetWidth,
      height: current.height,
    });

    updateSize(target.width, target.height);
    nextTick(() => {
      updatePosition(target.x, target.y);
    });
  };

  // 生命周期
  onMounted(() => {
    window.addEventListener('resize', handleWindowResize);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleWindowResize);
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
    isCompressed,
    isSidePanelExpanded,

    // 事件处理方法
    handleDragging,
    handleResizing,
    handleDragStop,
    handleResizeStop,
    toggleCompression,

    // 编程式控制方法
    updatePosition,
    updateSize,
    updatePositionAndSize,
    expandForSidePanel,
    collapseSidePanel,
  };
}
