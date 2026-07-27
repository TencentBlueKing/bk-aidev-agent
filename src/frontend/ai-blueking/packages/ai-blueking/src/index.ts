/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

// ==================== 主组件 ====================
// AIBlueking 完整组件（包含 Nimbus、浮窗、拖拽）
export { default as AIBlueking } from './ai-blueking.vue';

// ChatBot 核心组件（可嵌入使用）
export { ChatBot, type ChatBotEmits, type ChatBotExpose, type ChatBotProps, type IRequestOptions } from './components';

// ==================== Composables ====================
export { BootstrapPhase, type ChatBootstrapOptions, type ChatBootstrapReturn, useChatBootstrap } from './composables';

// ==================== 配置和工具 ====================
export { BluekingProtocol, createBluekingProtocol, type ProtocolOptions } from './config';

export { defaultProps } from './config';

// ==================== 容器组件 ====================
export {
  DraggableContainer,
  type DraggableContainerEmits,
  type DraggableContainerExpose,
  type DraggableContainerProps,
  type PositionAndSize,
  useDraggable,
  type UseDraggableOptions,
  type UseDraggableReturn,
} from './containers';

// ==================== 管理器层 ====================
// ComponentManager - UI 组件协调
export {
  type ComponentEvent,
  type ComponentEventCallback,
  type ComponentEventData,
  ComponentManager,
  type ComponentManagerConfig,
  type ComponentManagerState,
  type ContainerController,
  createComponentManager,
  type NimbusController,
  type PanelController,
} from './manager';

// 业务管理器（高级用法）
export {
  type ChatBusinessConfig,
  ChatBusinessManager,
  type CreateSessionOptions,
  type SendMessageOptions,
  type SessionBusinessConfig,
  SessionBusinessManager,
  type ShortcutFilterFn,
  ShortcutManager,
  UIStateManager,
} from './manager';

// ==================== 类型导出 ====================
export type {
  AIBluekingEmits,
  AIBluekingExpose,
  AIBluekingProps,
  DropdownMenuConfig,
  GetSideRenderComponent,
  GetSideTabRenderComponent,
  IShortcut,
  OnCustomTabChange,
} from './types';

// 重导出 AG-UI SDK 类型（方便使用）
export type { IAgentInfo, ILlmItem, IMessage, ISession, MessageRole, MessageStatus } from '@blueking/chat-helper';

// 重导出 AG-UI SDK（高级用法）
export { AGUIProtocol, useChatHelper } from '@blueking/chat-helper';

// MessageContentType 从 chat-x 导出
export { MessageContentType, RenderMode } from '@blueking/chat-x';

// ==================== 工具函数 ====================
export { parseCustomBlocks, type ContentBlock, type CustomBlock, type TextBlock } from './utils';
