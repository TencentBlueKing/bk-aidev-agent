/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { onUnmounted } from 'vue';

import {
  type InternalEvent,
  type InternalEventData,
  EVENT_BRIDGE_MAP,
  transformEventDataToEmitArgs,
} from '../manager/event-types';

import type { ComponentManager } from '../manager/component-manager';

/**
 * useEventBridge 配置选项
 */
export interface UseEventBridgeOptions {
  /**
   * ComponentManager 实例
   */
  componentManager: ComponentManager;

  /**
   * 是否启用调试模式
   */
  debug?: boolean;

  /**
   * Vue emit 函数
   * 通常是 defineEmits 返回的函数
   */
  emit: (event: string, ...args: unknown[]) => void;
}

/**
 * useEventBridge 返回值
 */
export interface UseEventBridgeReturn {
  /**
   * 清理所有事件监听
   */
  cleanup: () => void;

  /**
   * 手动触发 Vue emit
   * 用于需要直接发射 Vue emit 而不经过 Manager 的场景
   *
   * @param event Vue emit 事件名
   * @param args 事件参数
   */
  emitDirect: (event: string, ...args: unknown[]) => void;

  /**
   * 转发事件到 ComponentManager
   * 用于将子组件的 Vue emit 事件转发到统一事件系统
   *
   * @param event 内部事件名
   * @param data 事件数据
   */
  forwardToManager: <T extends InternalEvent>(event: T, data: InternalEventData[T]) => void;
}

/**
 * 创建事件转发器
 *
 * 用于简化子组件事件到 Manager 的转发
 * 返回一个预配置的转发函数集合
 *
 * @param forwardToManager useEventBridge 返回的 forwardToManager 函数
 */
export function createEventForwarders(forwardToManager: UseEventBridgeReturn['forwardToManager']) {
  return {
    // 消息事件
    sendMessage: (content: string) => forwardToManager('send-message', { content }),
    receiveStart: () => forwardToManager('receive-start', {}),
    receiveText: () => forwardToManager('receive-text', {}),
    receiveEnd: () => forwardToManager('receive-end', {}),
    stop: () => forwardToManager('stop', {}),

    // Header 事件
    newChat: () => forwardToManager('new-chat', {}),
    newChatCreated: (session: { sessionCode: string; sessionName?: string; createdAt?: string }) =>
      forwardToManager('new-chat-created', { session }),
    historyClick: (event: Event) => forwardToManager('history-click', { event }),
    autoGenerateName: () => forwardToManager('auto-generate-name', {}),
    helpClick: () => forwardToManager('help-click', {}),
    rename: (newName: string, sessionCode: string) => forwardToManager('rename', { newName, sessionCode }),
    share: () => forwardToManager('share', {}),

    // 消息选择事件
    transferMessages: (messageIds: string[]) => forwardToManager('transfer-messages', { messageIds }),
    shareMessages: (messageIds: string[]) => forwardToManager('share-messages', { messageIds }),
  };
}

/**
 * 事件桥接 Composable
 *
 * 自动将 ComponentManager 的内部事件桥接到 Vue emit，实现：
 * 1. 统一的事件管理 - 所有事件通过 ComponentManager 统一管理
 * 2. 自动桥接 - 内部事件自动转换为 Vue emit
 * 3. 事件转换 - 支持事件名和数据的转换
 * 4. 子组件事件转发 - 提供 forwardToManager 方法
 *
 * 使用示例：
 * ```typescript
 * const emit = defineEmits<AIBluekingEmits>();
 * const { forwardToManager } = useEventBridge({
 *   componentManager,
 *   emit,
 * });
 *
 * // 子组件事件转发
 * const handleSendMessage = (message: string) => {
 *   forwardToManager('send-message', { content: message });
 * };
 * ```
 */
export function useEventBridge(options: UseEventBridgeOptions): UseEventBridgeReturn {
  const { componentManager, emit, debug = false } = options;

  // 存储取消订阅函数
  const unsubscribers: Array<() => void> = [];

  // 设置事件桥接
  const setupBridge = () => {
    // 遍历事件映射表，设置桥接
    for (const [internalEvent, externalEvent] of Object.entries(EVENT_BRIDGE_MAP)) {
      // 跳过不对外暴露的事件
      if (externalEvent === null) {
        continue;
      }

      // 创建桥接回调函数
      const bridgeCallback = (data: unknown): void => {
        // 转换事件数据为 emit 参数
        const args = transformEventDataToEmitArgs(
          internalEvent as InternalEvent,
          data as InternalEventData[InternalEvent],
        );

        if (debug) {
          console.debug(`[useEventBridge] ${internalEvent} -> ${externalEvent}`, args);
        }

        // 发射 Vue emit
        emit(externalEvent, ...args);
      };

      // 直接订阅 ComponentManager 的事件
      const unsubscribe = componentManager.on(internalEvent as InternalEvent, bridgeCallback as any);

      unsubscribers.push(unsubscribe);
    }
  };

  // 转发事件到 Manager
  const forwardToManager = <T extends InternalEvent>(event: T, data: InternalEventData[T]): void => {
    if (debug) {
      console.debug(`[useEventBridge] Forwarding to manager: ${event}`, data);
    }
    componentManager.emit(event, data);
  };

  // 直接发射 Vue emit
  const emitDirect = (event: string, ...args: unknown[]): void => {
    if (debug) {
      console.debug(`[useEventBridge] Direct emit: ${event}`, args);
    }
    emit(event, ...args);
  };

  // 清理函数
  const cleanup = (): void => {
    unsubscribers.forEach(unsubscribe => unsubscribe());
    unsubscribers.length = 0;
  };

  // 初始化桥接
  setupBridge();

  // 组件卸载时自动清理
  onUnmounted(() => {
    cleanup();
  });

  return {
    forwardToManager,
    emitDirect,
    cleanup,
  };
}
