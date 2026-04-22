/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { createComponentManager } from '../manager';
import { SessionBusinessManager } from '../manager/business/session-business-manager';
import { ShareBusinessManager } from '../manager/business/share-business-manager';
import { ShortcutManager } from '../manager/business/shortcut-manager';
import { isTogglePanelShortcut, normalizeUrl } from '../utils';
import { useChatBootstrap } from './use-chat-bootstrap';
import { createEventForwarders, useEventBridge } from './use-event-bridge';

import type ChatBot from '../components/chat-bot.vue';
import type { DraggableContainerExpose } from '../containers';
import type { AIBluekingProps, IShortcut } from '../types';
import type { UseEventBridgeReturn } from './use-event-bridge';
import type { IAiSlashMenuItem } from '@blueking/chat-x';

export type EventForwarders = ReturnType<typeof createEventForwarders>;
export type ForwardToManagerFn = UseEventBridgeReturn['forwardToManager'];

export interface UseAiBluekingInitParams {
  props: AIBluekingProps;
  emit: (event: string, ...args: unknown[]) => void;
}

export function useAiBluekingInit(params: UseAiBluekingInitParams) {
  const { props, emit } = params;

  // ==================== Template Refs ====================
  const draggableContainerRef = ref<DraggableContainerExpose>();
  const chatBotRef = ref<InstanceType<typeof ChatBot>>();

  // ==================== URL 处理 ====================
  const normalizedUrl = computed(() => normalizeUrl(props.url ?? ''));

  // ==================== ComponentManager ====================
  const componentManager = createComponentManager({
    initialPanelVisible: false,
    initialNimbusMinimized: props.defaultMinimize,
    enablePopup: props.enablePopup,
    enableNimbus: !props.hideNimbus,
    enableDraggable: props.draggable,
  });

  const panelVisible = componentManager.panelVisible;
  const nimbusMinimized = componentManager.nimbusMinimized;

  // ==================== 事件桥接 ====================
  const { forwardToManager } = useEventBridge({
    componentManager,
    emit,
  });

  const forwarders = createEventForwarders(forwardToManager);

  // ==================== 错误处理 ====================
  /**
   * 统一的 SDK 错误发射器
   * 所有错误通过此函数统一格式化后触发 sdk-error，避免散落的重复逻辑
   */
  const emitSdkError = (apiName: string, error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[AIBlueking] ${apiName} error:`, error);
    componentManager.emitInternal('sdk-error', {
      apiName,
      code: -1,
      message,
      data: error,
    });
  };

  /** ChatBot 子组件 @error 回调 */
  const handleError = (error: Error) => {
    emitSdkError('chat', error);
  };

  // ==================== Bootstrap ====================
  const {
    chatHelper: bootstrapChatHelper,
    isReady: isBootstrapReady,
    error: bootstrapError,
    agentInfo,
    agentName: bootstrapAgentName,
    currentSession,
  } = useChatBootstrap({
    url: normalizedUrl,
    requestOptions: props.requestOptions,
    autoInit: true,
    protocolCallbacks: {
      onStart: () => {
        forwarders.receiveStart();
      },
      onMessage: () => {
        forwarders.receiveText();
      },
      onDone: () => {
        forwarders.receiveEnd();
      },
      onError: (error: unknown) => {
        emitSdkError('chat', error);
      },
    },
  });

  const chatHelper = bootstrapChatHelper;

  // ==================== Business Managers ====================
  const sessionBusinessManager = new SessionBusinessManager(chatHelper.session, chatHelper.agent, null, {
    enableChatSession: props.enableChatSession,
    initialSessionCode: props.initialSessionCode,
    alwaysCreateNewSession: props.alwaysCreateNewSession,
  });

  const shareBusinessManager = new ShareBusinessManager(chatHelper.message, chatHelper.session);
  const shortcutManager = new ShortcutManager(null, props.shortcuts || []);

  // ==================== Tippy 配置 ====================
  const messageToolsTippyOptions = {
    appendTo: (ref: Element) => {
      const container = ref.closest('.draggable-container-content');
      console.log('[ai-blueking] appendTo called, ref:', ref);
      console.log('[ai-blueking] appendTo closest result:', container);
      return container ?? document.body;
    },
  };

  // ==================== 派生状态 ====================
  const isCompressed = computed(() => componentManager.isCompressed.value);
  const agentName = computed(() => bootstrapAgentName.value);
  const isWelcomeState = computed(() => chatHelper.message.list.value.length === 0);

  const agentResources = computed(() => {
    if (props.resources?.length) return props.resources;
    return (agentInfo.value?.resources ?? []) as IAiSlashMenuItem[];
  });

  const agentPrompts = computed(() => {
    if (props.prompts?.length) return props.prompts;
    return agentInfo.value?.conversationSettings?.predefinedQuestions ?? [];
  });

  // 监听 Bootstrap 初始化失败（如 Agent 信息获取失败），统一触发 sdk-error
  watch(
    () => bootstrapError.value,
    err => {
      if (err) {
        emitSdkError('init', err);
      }
    },
  );

  // ==================== Agent 初始化 Watcher ====================
  watch(
    () => isBootstrapReady.value,
    async ready => {
      if (ready && agentInfo.value) {
        const info = agentInfo.value;

        if (info.saasUrl) {
          fetch(info.saasUrl, {
            method: 'GET',
            credentials: 'include',
          }).catch(() => {
            // ping 请求，忽略错误
          });
        }

        if (info.conversationSettings) {
          forwardToManager('session-initialized', {
            openingRemark: info.conversationSettings.openingRemark || '',
            predefinedQuestions: info.conversationSettings.predefinedQuestions || [],
          });

          if (info.conversationSettings.commands) {
            shortcutManager.setAgentShortcuts(info.conversationSettings.commands as IShortcut[]);
          }
        }

        if (props.loadRecentSessionOnMount) {
          try {
            await sessionBusinessManager.loadRecentSession({ skipLoadSessions: true });
          } catch (err) {
            console.error('[AIBlueking] Failed to load recent session:', err);
          }
        }
      }
    },
    { immediate: true },
  );

  watch(
    () => props.shortcuts,
    newShortcuts => {
      shortcutManager.setShortcuts(newShortcuts || []);
    },
    { immediate: true },
  );

  // ==================== 键盘快捷键 ====================
  const handleKeydown = (event: KeyboardEvent) => {
    if (isTogglePanelShortcut(event)) {
      event.preventDefault();
      if (panelVisible.value) {
        componentManager.hidePanel();
      } else {
        componentManager.showPanel();
      }
    }
  };

  // ==================== 生命周期 ====================
  onMounted(async () => {
    if (draggableContainerRef.value) {
      componentManager.setContainerRef(draggableContainerRef.value);
    }
    window.addEventListener('keydown', handleKeydown);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleKeydown);
    componentManager.destroy();
  });

  return {
    chatHelper,
    componentManager,
    sessionBusinessManager,
    shareBusinessManager,
    shortcutManager,
    forwarders,
    forwardToManager,
    chatBotRef,
    draggableContainerRef,
    panelVisible,
    nimbusMinimized,
    normalizedUrl,
    agentInfo,
    agentName,
    currentSession,
    isCompressed,
    isWelcomeState,
    messageToolsTippyOptions,
    agentResources,
    agentPrompts,
    handleError,
  };
}
