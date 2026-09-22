/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref } from 'vue';
import { ref } from 'vue';

import type ChatBot from '../components/chat-bot.vue';
import type { ComponentManager } from '../manager/component-manager';
import type { PositionAndSize } from '../manager/types';
import type { IShortcut } from '../types';
import type { EventForwarders, ForwardToManagerFn } from './use-ai-blueking-init';

const SIDE_PANEL_EXTRA_WIDTH = 560;

export interface UsePanelContainerParams {
  chatBotRef: Ref<InstanceType<typeof ChatBot> | undefined>;
  componentManager: ComponentManager;
  forwarders: EventForwarders;
  forwardToManager: ForwardToManagerFn;
  beforeNimbusClick?: () => boolean | Promise<boolean | void> | void;
  /** 等待 sessionList 与最近会话初始化完成（供 show() Promise 语义使用） */
  ensureSessionReady?: () => Promise<void>;
}

export function usePanelContainer(params: UsePanelContainerParams) {
  const { componentManager, chatBotRef, forwarders, forwardToManager, beforeNimbusClick, ensureSessionReady } = params;

  const asideCollapsed = ref(true);
  let extraWidth = SIDE_PANEL_EXTRA_WIDTH;

  // ==================== 面板控制 ====================
  const show = async (sessionCode?: string) => {
    componentManager.showPanel(sessionCode);

    if (ensureSessionReady) {
      await ensureSessionReady();
    }

    if (sessionCode && chatBotRef.value) {
      await chatBotRef.value.switchSession(sessionCode);
    }
  };

  const handleShow = async (sessionCode?: string) => {
    await show(sessionCode);
  };

  const hide = () => {
    asideCollapsed.value = true;
    componentManager.abortSidePanelSequence();
    componentManager.hidePanel();
  };

  const handleClose = () => {
    hide();
  };

  // ==================== Nimbus ====================
  const handleNimbusClick = async () => {
    if (beforeNimbusClick) {
      const result = await beforeNimbusClick();
      if (result === false) {
        // 用户拦截，不执行默认 showPanel
        componentManager.emit('nimbus-click', {});
        return;
      }
    }
    componentManager.handleNimbusClick();
  };

  // ==================== 拖拽处理 ====================
  const handleDragging = (position: PositionAndSize) => {
    componentManager.handleDragging(position);
  };

  const handleResizing = (position: PositionAndSize) => {
    componentManager.handleResizing(position);
  };

  const handleDragStop = (position: PositionAndSize) => {
    componentManager.handleDragStop(position);
  };

  const handleResizeStop = (position: PositionAndSize) => {
    componentManager.handleResizeStop(position);
  };

  // ==================== 压缩处理 ====================
  const handleToggleCompression = () => {
    componentManager.container.toggleCompression();
  };

  const handleCompressionChange = (compressed: boolean) => {
    componentManager.setCompressed(compressed);
  };

  // ==================== 执行面板联动 ====================
  const handleExecutionPanelChange = (_isCollapse: boolean, resizeAsideWidth?: number) => {
    extraWidth = Math.max(SIDE_PANEL_EXTRA_WIDTH, resizeAsideWidth ?? extraWidth);
  };

  const expandAside = async () => {
    if (!asideCollapsed.value) return;
    await componentManager.expandForSidePanel(extraWidth, {
      onBeforeSizeChange: () => {
        asideCollapsed.value = false;
      },
    });
    asideCollapsed.value = false;
  };

  const collapseAside = async () => {
    if (asideCollapsed.value) return;
    await componentManager.collapseSidePanel({
      onBeforeSizeChange: () => {
        asideCollapsed.value = true;
      },
    });
    asideCollapsed.value = true;
  };

  const handleToggleAside = async () => {
    if (asideCollapsed.value) {
      await expandAside();
    } else {
      await collapseAside();
    }
  };

  const handleAsideCollapsedUpdate = async (collapsed: boolean) => {
    if (collapsed === asideCollapsed.value) return;
    if (collapsed) {
      await collapseAside();
    } else {
      await expandAside();
    }
  };

  // ==================== 消息事件转发 ====================
  const sendMessage = async (message: string) => {
    if (chatBotRef.value) {
      await chatBotRef.value.sendMessage(message);
    }
  };

  const handleReceiveStart = () => {
    forwarders.receiveStart();
  };

  const handleReceiveText = () => {
    forwarders.receiveText();
  };

  const handleReceiveEnd = () => {
    forwarders.receiveEnd();
  };

  const handleStop = () => {
    forwarders.stop();
  };

  const stopGeneration = () => {
    if (chatBotRef.value) {
      chatBotRef.value.stopGeneration();
    }
  };

  // ==================== 容器控制 ====================
  const updatePosition = (x: number, y: number) => {
    componentManager.container.updatePosition(x, y);
  };

  const updateSize = (w: number, h: number) => {
    componentManager.container.updateSize(w, h);
  };

  const updatePositionAndSize = (x: number, y: number, w: number, h: number) => {
    componentManager.container.updatePositionAndSize(x, y, w, h);
  };

  // ==================== 其他 ====================
  const setCiteText = (text: string) => {
    if (chatBotRef.value) {
      chatBotRef.value.setCiteText(text);
    }
  };

  const focusInput = () => {
    if (chatBotRef.value) {
      chatBotRef.value.focusInput();
    }
  };

  /**
   * 编程式选择快捷指令并显示表单
   * 委托给 ChatBot 的 selectShortcut 方法
   */
  const selectShortcut = (shortcut: IShortcut, selectedText?: string) => {
    if (chatBotRef.value) {
      chatBotRef.value.selectShortcut(shortcut, selectedText);
    }
  };

  /**
   * 直接发送快捷指令（跳过表单）
   * 委托给 ChatBot 的 sendShortcut 方法
   */
  const sendShortcut = (shortcut: IShortcut, selectedText?: string): Promise<void> => {
    if (chatBotRef.value) {
      return chatBotRef.value.sendShortcut(shortcut, selectedText);
    }
    return Promise.resolve();
  };

  /**
   * 获取 chatHelper 实例
   * 委托给 ChatBot 的 getChatHelper 方法
   */
  const getChatHelper = () => {
    if (chatBotRef.value) {
      return chatBotRef.value.getChatHelper();
    }
    return null;
  };

  const handleShortcutClick = (data: { shortcut: IShortcut; source: 'main' | 'popup' }) => {
    forwardToManager('shortcut-click', data);
  };

  return {
    show,
    handleShow,
    hide,
    handleClose,
    handleNimbusClick,
    handleDragging,
    handleResizing,
    handleDragStop,
    handleResizeStop,
    handleToggleCompression,
    handleCompressionChange,
    handleExecutionPanelChange,
    handleToggleAside,
    handleAsideCollapsedUpdate,
    asideCollapsed,
    sendMessage,
    handleReceiveStart,
    handleReceiveText,
    handleReceiveEnd,
    handleStop,
    stopGeneration,
    updatePosition,
    updateSize,
    updatePositionAndSize,
    setCiteText,
    focusInput,
    selectShortcut,
    sendShortcut,
    getChatHelper,
    handleShortcutClick,
  };
}
