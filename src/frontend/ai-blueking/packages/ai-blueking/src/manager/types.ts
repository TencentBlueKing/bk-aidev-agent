/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { ComputedRef, Ref } from 'vue';

// 从主 types.ts 导入 IShortcut
import type { IShortcut } from '../types';

// 重导出以供其他 manager 模块使用
export type { IShortcut };

/**
 * ComponentManager 配置选项
 */
export interface ComponentManagerConfig {
  /** 是否启用调试模式（输出事件日志） */
  debug?: boolean;

  /** 是否启用拖拽 */
  enableDraggable?: boolean;

  /** 是否启用 Nimbus */
  enableNimbus?: boolean;

  /** 是否启用 Popup */
  enablePopup?: boolean;

  /** 初始 Nimbus 最小化状态 */
  initialNimbusMinimized?: boolean;

  /** 初始面板可见性 */
  initialPanelVisible?: boolean;
}

/**
 * ComponentManager 状态
 */
export interface ComponentManagerState {
  /** 是否正在拖拽或调整大小 */
  isDraggingOrResizing: Ref<boolean>;

  /** Nimbus 是否最小化 */
  nimbusMinimized: Ref<boolean>;

  /** 面板是否可见 */
  panelVisible: Ref<boolean>;

  /** 当前位置和大小 */
  positionAndSize: Ref<PositionAndSize>;
}

/**
 * 容器控制接口
 */
export interface ContainerController {
  /** 是否压缩状态 */
  isCompressed: ComputedRef<boolean>;

  /** 侧面板是否已展开 */
  isSidePanelExpanded: ComputedRef<boolean>;

  /** 当前位置和大小 */
  positionAndSize: ComputedRef<PositionAndSize>;

  /** 中止进行中的侧面板展开/收起并恢复收起布局 */
  abortSidePanelSequence: () => void;

  /** 折叠侧面板：左边缘不动，从右侧收窄到原始宽度 */
  collapseSidePanel: (hooks?: { onBeforeSizeChange?: () => void }) => Promise<void>;

  /** 为侧面板展开扩展容器宽度 */
  expandForSidePanel: (extraWidth: number, hooks?: { onBeforeSizeChange?: () => void }) => Promise<void>;

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
 * Nimbus 控制接口
 */
export interface NimbusController {
  /** 是否最小化 */
  isMinimized: ComputedRef<boolean>;

  /** 最小化 Nimbus */
  minimize: () => void;

  /** 恢复 Nimbus */
  restore: () => void;

  /** 切换最小化状态 */
  toggle: () => void;
}

/**
 * 面板控制接口
 */
export interface PanelController {
  /** 面板是否可见 */
  isVisible: ComputedRef<boolean>;

  /** 隐藏面板 */
  hide: () => void;

  /** 显示面板 */
  show: (sessionCode?: string) => void;

  /** 切换面板显示状态 */
  toggle: () => void;
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
