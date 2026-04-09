/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref, ComputedRef } from 'vue';

// 从主 types.ts 导入 IShortcut
import type { IShortcut } from '../types';

// 重导出以供其他 manager 模块使用
export type { IShortcut };

/**
 * 位置和大小
 */
export interface PositionAndSize {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * ComponentManager 配置选项
 */
export interface ComponentManagerConfig {
  /** 初始面板可见性 */
  initialPanelVisible?: boolean;

  /** 初始 Nimbus 最小化状态 */
  initialNimbusMinimized?: boolean;

  /** 是否启用 Popup */
  enablePopup?: boolean;

  /** 是否启用 Nimbus */
  enableNimbus?: boolean;

  /** 是否启用拖拽 */
  enableDraggable?: boolean;

  /** 是否启用调试模式（输出事件日志） */
  debug?: boolean;
}

/**
 * ComponentManager 状态
 */
export interface ComponentManagerState {
  /** 面板是否可见 */
  panelVisible: Ref<boolean>;

  /** Nimbus 是否最小化 */
  nimbusMinimized: Ref<boolean>;

  /** 是否正在拖拽或调整大小 */
  isDraggingOrResizing: Ref<boolean>;

  /** 当前位置和大小 */
  positionAndSize: Ref<PositionAndSize>;
}

/**
 * 面板控制接口
 */
export interface PanelController {
  /** 显示面板 */
  show: (sessionCode?: string) => void;

  /** 隐藏面板 */
  hide: () => void;

  /** 切换面板显示状态 */
  toggle: () => void;

  /** 面板是否可见 */
  isVisible: ComputedRef<boolean>;
}

/**
 * Nimbus 控制接口
 */
export interface NimbusController {
  /** 最小化 Nimbus */
  minimize: () => void;

  /** 恢复 Nimbus */
  restore: () => void;

  /** 切换最小化状态 */
  toggle: () => void;

  /** 是否最小化 */
  isMinimized: ComputedRef<boolean>;
}

/**
 * 容器控制接口
 */
export interface ContainerController {
  /** 更新位置 */
  updatePosition: (x: number, y: number) => void;

  /** 更新大小 */
  updateSize: (width: number, height: number) => void;

  /** 同时更新位置和大小 */
  updatePositionAndSize: (x: number, y: number, width: number, height: number) => void;

  /** 切换压缩状态 */
  toggleCompression: () => void;

  /** 为侧面板展开扩展容器宽度 */
  expandForSidePanel: (extraWidth: number) => void;

  /** 折叠侧面板并恢复容器原始宽度 */
  collapseSidePanel: () => void;

  /** 当前位置和大小 */
  positionAndSize: ComputedRef<PositionAndSize>;

  /** 是否压缩状态 */
  isCompressed: ComputedRef<boolean>;

  /** 侧面板是否已展开 */
  isSidePanelExpanded: ComputedRef<boolean>;
}
