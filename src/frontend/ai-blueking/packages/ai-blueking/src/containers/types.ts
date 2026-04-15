/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { ComputedRef, Ref } from 'vue';

/**
 * 可拖拽容器 Emits
 */
export interface DraggableContainerEmits {
  /** 拖拽中 */
  (e: 'dragging', position: PositionAndSize): void;

  /** 调整大小中 */
  (e: 'resizing', position: PositionAndSize): void;

  /** 拖拽停止 */
  (e: 'drag-stop', position: PositionAndSize): void;

  /** 调整大小停止 */
  (e: 'resize-stop', position: PositionAndSize): void;

  /** 压缩状态变化 */
  (e: 'compression-change', isCompressed: boolean): void;
}

/**
 * 可拖拽容器 Expose
 */
export interface DraggableContainerExpose {
  /** 是否压缩状态 */
  isCompressed: Ref<boolean>;

  /** 侧面板是否已展开 */
  isSidePanelExpanded: Ref<boolean>;

  /** 当前位置和大小 */
  positionAndSize: ComputedRef<PositionAndSize>;

  /** 折叠侧面板并恢复容器原始宽度 */
  collapseSidePanel: () => void;

  /** 为侧面板展开扩展容器宽度 */
  expandForSidePanel: (extraWidth: number) => void;

  /** 切换压缩状态 */
  toggleCompression: () => void;

  /** 更新位置 */
  updatePosition: (x: number, y: number) => void;

  /** 同时更新位置和大小 */
  updatePositionAndSize: (x: number, y: number, width: number, height: number) => void;

  /** 更新大小 */
  updateSize: (width: number, height: number) => void;
}

/**
 * 可拖拽容器 Props
 */
export interface DraggableContainerProps {
  /** 自定义类名 */
  className?: string;

  /** 压缩状态下的高度 */
  compressedHeight?: number;

  /** 压缩状态下的边距 */
  compressedPadding?: number;

  /** 初始高度 */
  defaultHeight?: number;

  /** 初始宽度 */
  defaultWidth?: number;

  /** 初始 X 位置 */
  defaultX?: number;

  /** 初始 Y 位置 */
  defaultY?: number;

  /** 是否可拖拽 */
  draggable?: boolean;

  /** 拖拽手柄选择器 */
  dragHandle?: string;

  /** 最大宽度 */
  maxWidth?: number | string;

  /** 最大宽度百分比（相对于视窗） */
  maxWidthPercent?: number;

  /** 最小高度 */
  minHeight?: number;

  /** 最小宽度 */
  minWidth?: number;

  /** 是否可调整大小 */
  resizable?: boolean;

  /** 传送目标 */
  teleportTo?: string;

  /** 是否显示 */
  visible?: boolean;
}

/**
 * 位置和大小
 */
export interface PositionAndSize {
  height: number;
  width: number;
  x: number;
  y: number;
}

/**
 * useDraggable 配置选项
 */
export interface UseDraggableOptions {
  /** 压缩状态下的高度 */
  compressedHeight?: number;

  /** 压缩状态下的边距 */
  compressedPadding?: number;

  /** 默认高度 */
  defaultHeight?: number;

  /** 默认左侧位置 */
  defaultLeft?: number;

  /** 默认顶部位置 */
  defaultTop?: number;

  /** 初始宽度 */
  initWidth?: number;

  /** 最大宽度百分比 */
  maxWidthPercent?: number;

  /** 最小高度 */
  minHeight?: number;

  /** 最小宽度 */
  minWidth?: number;
}

/**
 * useDraggable 返回值
 */
export interface UseDraggableReturn {
  height: Ref<number>;
  isCompressed: Ref<boolean>;
  isSidePanelExpanded: Ref<boolean>;
  left: Ref<number>;
  maxWidth: Ref<number>;
  minHeight: number;
  // 基本属性
  minWidth: number;
  top: Ref<number>;
  width: Ref<number>;

  collapseSidePanel: () => void;
  expandForSidePanel: (extraWidth: number) => void;
  // 事件处理方法
  handleDragging: (x: number, y: number) => void;
  handleDragStop: (x: number, y: number) => void;
  handleResizeStop: (x: number, y: number, width: number, height: number) => void;

  handleResizing: (x: number, y: number, width: number, height: number) => void;
  toggleCompression: () => void;
  // 编程式控制方法
  updatePosition: (x: number, y: number) => void;
  updatePositionAndSize: (x: number, y: number, width: number, height: number) => void;
  updateSize: (width: number, height: number) => void;
}
