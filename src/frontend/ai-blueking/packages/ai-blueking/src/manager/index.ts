/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

// ==================== Business Managers ====================
// 业务管理器
export * from './business';

// ==================== ComponentManager ====================
// 统一管理器（含事件系统）
export { ComponentManager, createComponentManager } from './component-manager';

// ==================== Event Types ====================
// 统一事件类型系统
export { EVENT_BRIDGE_MAP, getExternalEventName, getExternalEvents, transformEventDataToEmitArgs } from './event-types';

export type {
  BusinessEvent,
  BusinessEventData,
  ChatBotInternalEvent,
  ChatBotInternalEventData,
  ComponentEvent,
  ComponentEventCallback,
  ComponentEventData,
  EventCallback,
  HeaderEvent,
  HeaderEventData,
  InternalEvent,
  InternalEventData,
  MessageSelectionEvent,
  MessageSelectionEventData,
  UIEvent,
  UIEventData,
} from './event-types';

// ==================== Types ====================
// Manager 配置/状态类型
export type {
  ComponentManagerConfig,
  ComponentManagerState,
  ContainerController,
  IShortcut,
  NimbusController,
  PanelController,
  PositionAndSize,
} from './types';

// ==================== UI State Manager ====================
// UI 状态管理（消息选择、编辑模式等）
export { UIStateManager } from './ui';
