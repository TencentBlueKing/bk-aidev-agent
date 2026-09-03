/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

import type { PositionAndSize, SidePanelGeometryHooks, UseDraggableOptions, UseDraggableReturn } from './types';

/** 小于该像素的位移视为点击抖动，而非用户主动挪窗 */
const USER_MOVE_EPSILON = 3;

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
  let lastExtraWidth = 0;
  let sequenceId = 0;
  /** 本次展开是否因右侧空间不足而挪动了窗口 */
  let shiftedForSidePanel = false;
  /** 最近一次编程式布局的落点，用于识别「用户真的挪了窗」 */
  let committedLayout: null | PositionAndSize = null;
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
   * 用户真的挪窗才让展开前快照失效。
   *
   * 侧栏开关画在 Header 上，而 Header 就是拖拽手柄：点开关时鼠标抖动几像素，
   * vue-draggable-resizable 也会发出真实的 dragging / dragStop。用与上次编程式落点的
   * 偏移量区分「抖动」和「真的挪窗」，否则收起时会误判成用户已选好位置而不再归位。
   */
  const noteUserAdjustment = (x: number, w: number): void => {
    if (!isSidePanelExpanded.value) return;
    const isJitter =
      committedLayout !== null &&
      Math.abs(x - committedLayout.x) <= USER_MOVE_EPSILON &&
      Math.abs(w - committedLayout.width) <= USER_MOVE_EPSILON;
    if (isJitter) return;
    collapsedPosition = null;
    shiftedForSidePanel = false;
  };

  /**
   * 处理拖拽中
   */
  const handleDragging = (x: number, y: number): void => {
    left.value = x;
    top.value = y;
    leftDiff.value = x - (window.innerWidth - width.value);
    noteUserAdjustment(x, width.value);

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
    noteUserAdjustment(x, width.value);

    callbacks?.onResizing?.(getPositionAndSize());
  };

  /**
   * 处理拖拽停止
   */
  const handleDragStop = (x: number, y: number): void => {
    left.value = x;
    top.value = y;
    leftDiff.value = x - (window.innerWidth - width.value);
    noteUserAdjustment(x, width.value);
    if (isSidePanelExpanded.value) {
      expandedPosition = getPositionAndSize();
    } else {
      expandedPosition = null;
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
    noteUserAdjustment(x, width.value);
    if (isSidePanelExpanded.value) {
      expandedPosition = getPositionAndSize();
    } else {
      expandedPosition = null;
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

  const syncLeftDiff = (): void => {
    leftDiff.value = left.value - (window.innerWidth - width.value);
  };

  /**
   * vue-draggable-resizable 的 changeWidth 用当前 left 计算宽度。
   * 同帧改 x+w 时宽度会被钳在贴边旧位置上（窗口加不宽，侧栏叠在主栏上）。
   * 展开必须先 x 后 width；收起必须先 width 后 x。CSS 同时过渡 transform/width 做成推开。
   */
  const commitLayout = async (
    current: PositionAndSize,
    target: PositionAndSize,
    id: number,
    hooks?: SidePanelGeometryHooks,
    order: 'collapse' | 'expand' = 'expand',
  ): Promise<void> => {
    const xChanged = target.x !== current.x;
    const sizeChanged = target.width !== current.width;

    const applyX = async (): Promise<void> => {
      if (!xChanged) return;
      updatePosition(target.x, target.y);
      await nextTick();
    };
    const applyWidth = async (): Promise<void> => {
      hooks?.onBeforeSizeChange?.();
      if (!sizeChanged) return;
      updateSize(target.width, target.height);
      await nextTick();
    };

    try {
      if (order === 'expand') {
        await applyX();
        if (id !== sequenceId) return;
        await applyWidth();
        return;
      }

      await applyWidth();
      if (id !== sequenceId) return;
      await applyX();
    } finally {
      syncLeftDiff();
      committedLayout = getPositionAndSize();
    }
  };

  /**
   * 为侧面板展开扩展容器宽度。
   * 已能放下主栏+侧栏时不改几何；贴边则先写入 x，再与侧栏同帧加宽。
   */
  const expandForSidePanel = async (extraWidth: number, hooks?: SidePanelGeometryHooks): Promise<void> => {
    if (isSidePanelExpanded.value) return;
    const current = getPositionAndSize();
    collapsedPosition = { ...current };
    isSidePanelExpanded.value = true;
    const id = ++sequenceId;

    const viewportWidth = window.innerWidth;
    const minExpandedWidth = minWidth + extraWidth;

    if (current.width >= minExpandedWidth) {
      lastExtraWidth = 0;
      shiftedForSidePanel = false;
      expandedPosition = { ...current };
      committedLayout = { ...current };
      hooks?.onBeforeSizeChange?.();
      return;
    }

    let targetWidth = expandedPosition?.width ?? current.width + extraWidth;
    targetWidth = Math.min(targetWidth, maxWidth.value, viewportWidth);
    targetWidth = Math.max(targetWidth, minExpandedWidth, minWidth);

    const needed = Math.max(0, targetWidth - current.width);
    const rightSpace = viewportWidth - (current.x + current.width);
    const shift = Math.max(0, needed - rightSpace);
    const nextX = Math.max(0, current.x - shift);
    targetWidth = Math.min(targetWidth, viewportWidth - nextX);
    lastExtraWidth = Math.max(0, targetWidth - current.width);

    const target = clampToViewport({
      x: nextX,
      y: current.y,
      width: targetWidth,
      height: current.height,
    });
    shiftedForSidePanel = target.x !== current.x;

    await commitLayout(current, target, id, hooks, 'expand');
    if (id !== sequenceId) return;
    expandedPosition = getPositionAndSize();
  };

  /**
   * 折叠侧面板：先从右侧缩宽；若展开时因右侧空间不足挪过窗，再移回挪窗前的位置。
   * 展开态被用户拖动/缩放过（快照已失效）时保持左边缘不动，只缩宽。
   */
  const collapseSidePanel = async (hooks?: SidePanelGeometryHooks): Promise<void> => {
    if (!isSidePanelExpanded.value) return;
    const current = getPositionAndSize();
    expandedPosition = { ...current };
    isSidePanelExpanded.value = false;
    const id = ++sequenceId;

    const snapshot = collapsedPosition;
    const shouldRestoreShift = shiftedForSidePanel && snapshot !== null;
    const targetWidth = snapshot?.width ?? Math.max(minWidth, current.width - lastExtraWidth);
    const target = clampToViewport({
      x: shouldRestoreShift && snapshot ? snapshot.x : current.x,
      y: current.y,
      width: targetWidth,
      height: current.height,
    });
    shiftedForSidePanel = false;

    await commitLayout(current, target, id, hooks, 'collapse');
    if (id !== sequenceId) return;
  };

  /**
   * 中止进行中的展开/收起，恢复本次序列开始时的收起布局
   */
  const abortSidePanelSequence = (): void => {
    sequenceId += 1;
    isSidePanelExpanded.value = false;
    shiftedForSidePanel = false;
    if (collapsedPosition) {
      updatePosition(collapsedPosition.x, collapsedPosition.y);
      updateSize(collapsedPosition.width, collapsedPosition.height);
    }
    syncLeftDiff();
    committedLayout = getPositionAndSize();
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
    abortSidePanelSequence,
  };
}
