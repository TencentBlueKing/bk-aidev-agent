/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 统一事件类型系统
 *
 * 本文件定义了 AIBlueking V2 组件的完整事件类型系统，包括：
 * 1. UI 事件 - 面板、Nimbus、拖拽等 UI 交互事件
 * 2. 业务事件 - 消息、会话等业务操作事件
 * 3. 子组件事件 - ChatBot、AIHeader 等子组件发射的事件
 *
 * 事件桥接映射：
 * - 内部事件通过 useEventBridge 自动桥接到 Vue emit
 * - 某些内部事件不对外暴露（映射为 null）
 */

import type { ISession } from '@blueking/chat-helper';
import type { PositionAndSize, IShortcut } from './types';
import type { IChatHelper, SdkErrorPayload } from '../types';

// ============================================================================
// UI 事件类型
// ============================================================================

/**
 * UI 事件名称
 */
export type UIEvent =
  // 面板事件
  | 'panel-show'
  | 'panel-hide'
  | 'panel-toggle'
  // Nimbus 事件
  | 'nimbus-click'
  | 'nimbus-minimize'
  | 'nimbus-restore'
  // Popup 事件
  | 'popup-click'
  | 'popup-shortcut-click'
  // 拖拽事件
  | 'dragging'
  | 'resizing'
  | 'drag-stop'
  | 'resize-stop'
  // 压缩状态事件
  | 'compression-toggle'
  // 侧面板展开/折叠事件
  | 'side-panel-expand'
  | 'side-panel-collapse';

/**
 * UI 事件数据映射
 */
export interface UIEventData {
  'panel-show': { sessionCode?: string };
  'panel-hide': Record<string, never>;
  'panel-toggle': { visible: boolean };
  'nimbus-click': Record<string, never>;
  'nimbus-minimize': Record<string, never>;
  'nimbus-restore': Record<string, never>;
  'popup-click': Record<string, never>;
  'popup-shortcut-click': { shortcut: IShortcut };
  dragging: PositionAndSize;
  resizing: PositionAndSize;
  'drag-stop': PositionAndSize;
  'resize-stop': PositionAndSize;
  'compression-toggle': { compressed: boolean };
  'side-panel-expand': { extraWidth: number };
  'side-panel-collapse': Record<string, never>;
}

// ============================================================================
// 业务事件类型
// ============================================================================

/**
 * 业务事件名称
 */
export type BusinessEvent =
  // 消息事件
  | 'send-message'
  | 'receive-start'
  | 'receive-text'
  | 'receive-end'
  | 'receive-error'
  | 'stop'
  | 'chat-regenerate'
  | 'chat-retry'
  | 'message-deleted'
  | 'messages-batch-deleted'
  // 会话事件
  | 'session-created'
  | 'session-switched'
  | 'session-deleted'
  | 'session-updated'
  | 'sessions-loaded'
  | 'session-initialized'
  | 'session-error'
  // 快捷方式事件
  | 'shortcut-click'
  // 错误事件
  | 'chat-error'
  | 'sdk-error';

/**
 * 业务事件数据映射
 */
export interface BusinessEventData {
  // 消息事件
  'send-message': { content: string };
  'receive-start': Record<string, never>;
  'receive-text': Record<string, never>;
  'receive-end': Record<string, never>;
  'receive-error': { error: Error };
  stop: Record<string, never>;
  'chat-regenerate': { messageId: string };
  'chat-retry': { messageId: string };
  'message-deleted': { messageId: number };
  'messages-batch-deleted': { messageIds: number[] };
  // 会话事件
  'session-created': { session: ISession };
  'session-switched': { session: ISession | null };
  'session-deleted': { sessionCode: string };
  'session-updated': { session: ISession };
  'sessions-loaded': { sessions: ISession[] };
  'session-initialized': { openingRemark: string; predefinedQuestions: string[] };
  'session-error': { action: string; error: unknown };
  // 快捷方式事件
  'shortcut-click': { shortcut: IShortcut; source: 'popup' | 'main' };
  // 错误事件
  'chat-error': { action: string; error: unknown };
  'sdk-error': SdkErrorPayload;
}

// ============================================================================
// Header 事件类型
// ============================================================================

/**
 * Header 事件名称
 */
export type HeaderEvent =
  | 'new-chat'
  | 'new-chat-created'
  | 'history-click'
  | 'auto-generate-name'
  | 'help-click'
  | 'rename'
  | 'share'
  | 'close'
  | 'toggle-compression';

/**
 * Header 事件数据映射
 */
export interface HeaderEventData {
  'new-chat': Record<string, never>;
  'new-chat-created': { session: { sessionCode: string; sessionName?: string; createdAt?: string } };
  'history-click': { event: Event };
  'auto-generate-name': Record<string, never>;
  'help-click': Record<string, never>;
  rename: { newName: string };
  share: Record<string, never>;
  close: Record<string, never>;
  'toggle-compression': Record<string, never>;
}

// ============================================================================
// 消息选择事件类型
// ============================================================================

/**
 * 消息选择事件名称
 */
export type MessageSelectionEvent = 'transfer-messages' | 'share-messages';

/**
 * 消息选择事件数据映射
 */
export interface MessageSelectionEventData {
  'transfer-messages': { messageIds: string[] };
  'share-messages': { messageIds: string[] };
}

// ============================================================================
// ChatBot 内部事件类型
// ============================================================================

/**
 * ChatBot 内部事件名称
 */
export type ChatBotInternalEvent = 'agent-info-loaded' | 'error';

/**
 * ChatBot 内部事件数据映射
 */
export interface ChatBotInternalEventData {
  'agent-info-loaded': { chatHelper: IChatHelper };
  error: { error: Error };
}

// ============================================================================
// 组合事件类型
// ============================================================================

/**
 * ComponentManager 事件（UI + 业务事件的子集）
 * 这些事件由 ComponentManager 内部管理和发射
 */
export type ComponentEvent = UIEvent | Extract<BusinessEvent, 'shortcut-click'>;

/**
 * ComponentManager 事件数据
 */
export type ComponentEventData = UIEventData & Pick<BusinessEventData, 'shortcut-click'>;

/**
 * 所有内部事件类型
 * 用于 ComponentManager 和业务管理器
 */
export type InternalEvent = UIEvent | BusinessEvent | HeaderEvent | MessageSelectionEvent | ChatBotInternalEvent;

/**
 * 所有内部事件数据
 */
export type InternalEventData = UIEventData &
  BusinessEventData &
  HeaderEventData &
  MessageSelectionEventData &
  ChatBotInternalEventData;

// ============================================================================
// 事件桥接映射
// ============================================================================

/**
 * 事件桥接映射配置
 * key: 内部事件名
 * value: Vue emit 事件名（null 表示不对外暴露）
 *
 * 注意：业务管理器（ChatBusinessManager / SessionBusinessManager）的失败事件
 * （`chat-error` / `receive-error` / `session-error`）不走此映射，而是由 ChatBot 的
 * `useErrorReporter` 桥接到 `error` 事件；AIBlueking 再把 `error` 转成 `sdk-error`。
 */
export const EVENT_BRIDGE_MAP: Record<InternalEvent, string | null> = {
  // UI 事件
  'panel-show': 'show',
  'panel-hide': 'close',
  'panel-toggle': null, // 内部事件，不对外暴露
  'nimbus-click': null, // 内部事件，不对外暴露
  'nimbus-minimize': null, // 内部事件，不对外暴露
  'nimbus-restore': null, // 内部事件，不对外暴露
  'popup-click': null, // 内部事件，不对外暴露
  'popup-shortcut-click': null, // 通过 shortcut-click 统一暴露
  dragging: 'dragging',
  resizing: 'resizing',
  'drag-stop': 'drag-stop',
  'resize-stop': 'resize-stop',
  'compression-toggle': null, // 内部事件，不对外暴露
  'side-panel-expand': null, // 内部事件，不对外暴露
  'side-panel-collapse': null, // 内部事件，不对外暴露

  // 业务事件
  'send-message': 'send-message',
  'receive-start': 'receive-start',
  'receive-text': 'receive-text',
  'receive-end': 'receive-end',
  'receive-error': null, // 由 useErrorReporter 转 error，再由 AIBlueking 转 sdk-error
  stop: 'stop',
  'chat-regenerate': null, // 内部事件
  'chat-retry': null, // 内部事件
  'message-deleted': null, // 内部事件
  'messages-batch-deleted': null, // 内部事件
  'session-created': null, // 内部事件
  'session-switched': null, // 内部事件
  'session-deleted': null, // 内部事件
  'session-updated': null, // 内部事件
  'sessions-loaded': null, // 内部事件
  'session-initialized': 'session-initialized',
  'session-error': null, // 由 useErrorReporter 转 error，再由 AIBlueking 转 sdk-error
  'shortcut-click': 'shortcut-click',
  'chat-error': null, // 由 useErrorReporter 转 error，再由 AIBlueking 转 sdk-error
  'sdk-error': 'sdk-error',

  // Header 事件
  'new-chat': 'new-chat',
  'new-chat-created': 'new-chat-created',
  'history-click': 'history-click',
  'auto-generate-name': 'auto-generate-name',
  'help-click': 'help-click',
  rename: 'rename',
  share: 'share',
  close: 'close',
  'toggle-compression': null, // 内部事件

  // 消息选择事件
  'transfer-messages': 'transfer-messages',
  'share-messages': 'share-messages',

  // ChatBot 内部事件
  'agent-info-loaded': null, // 内部事件
  error: null, // 通过 sdk-error 统一暴露
} as const;

/**
 * 获取对外暴露的事件列表
 */
export function getExternalEvents(): string[] {
  return Object.entries(EVENT_BRIDGE_MAP)
    .filter(([, external]) => external !== null)
    .map(([, external]) => external as string);
}

/**
 * 获取内部事件对应的外部事件名
 */
export function getExternalEventName(internalEvent: InternalEvent): string | null {
  return EVENT_BRIDGE_MAP[internalEvent];
}

// ============================================================================
// 事件回调类型
// ============================================================================

/**
 * 事件回调类型（泛型）
 */
export type EventCallback<T extends InternalEvent> = (data: InternalEventData[T]) => void;

/**
 * ComponentManager 事件回调类型
 */
export type ComponentEventCallback<T extends ComponentEvent> = (data: ComponentEventData[T]) => void;

// ============================================================================
// Vue Emit 参数类型转换
// ============================================================================

/**
 * 将内部事件数据转换为 Vue emit 参数
 * 某些事件需要特殊处理（如解构对象为多个参数）
 */
export function transformEventDataToEmitArgs(event: InternalEvent, data: InternalEventData[InternalEvent]): unknown[] {
  switch (event) {
    // 简单值事件：直接返回值
    case 'send-message':
      return [(data as BusinessEventData['send-message']).content];
    case 'rename':
      return [(data as HeaderEventData['rename']).newName];
    case 'history-click':
      return [(data as HeaderEventData['history-click']).event];

    // 对象事件：直接返回整个对象
    case 'dragging':
    case 'resizing':
    case 'drag-stop':
    case 'resize-stop':
    case 'shortcut-click':
    case 'session-initialized':
    case 'sdk-error':
    case 'transfer-messages':
    case 'share-messages':
    case 'new-chat-created':
      return [data];

    // 无参数事件
    case 'panel-show':
    case 'panel-hide':
    case 'receive-start':
    case 'receive-text':
    case 'receive-end':
    case 'stop':
    case 'new-chat':
    case 'auto-generate-name':
    case 'help-click':
    case 'share':
    case 'close':
      return [];

    // 默认：返回整个数据对象
    default:
      return [data];
  }
}
