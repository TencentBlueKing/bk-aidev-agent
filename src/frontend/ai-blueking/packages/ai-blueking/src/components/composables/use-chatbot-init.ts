/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import type { Ref } from 'vue';

import { AGUIProtocol, useChatHelper } from '@blueking/chat-helper';

import { ChatBusinessManager, SessionBusinessManager, ShortcutManager } from '../../manager';
import { normalizeUrl } from '../../utils';

import type { IChatHelper } from '../../types';
import type { ChatBotProps } from '../types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ChatBotEmitFn = (...args: any[]) => void;

export interface UseChatbotInitParams {
  emit: ChatBotEmitFn;
  props: ChatBotProps;
  scrollToBottom: () => Promise<void>;
}

export interface UseChatbotInitReturn {
  chatBusinessManager: Ref<ChatBusinessManager | null>;
  chatHelper: Ref<IChatHelper | null>;
  initError: Ref<Error | null>;
  isInitialized: Ref<boolean>;
  isStandaloneMode: Ref<boolean>;
  sessionBusinessManager: Ref<null | SessionBusinessManager>;
  shortcutManager: Ref<null | ShortcutManager>;
}

export function useChatbotInit(params: UseChatbotInitParams): UseChatbotInitReturn {
  const { props, emit, scrollToBottom } = params;

  const chatHelper = shallowRef<IChatHelper | null>(null);
  const sessionBusinessManager = shallowRef<null | SessionBusinessManager>(null);
  const chatBusinessManager = shallowRef<ChatBusinessManager | null>(null);
  const shortcutManager = shallowRef<null | ShortcutManager>(null);
  const isInitialized = ref(false);
  const isStandaloneMode = ref(!props.chatHelper);
  const initError = ref<Error | null>(null);

  /**
   * 验证 props 配置
   */
  const validateProps = (): { error?: string; valid: boolean } => {
    if (props.chatHelper) {
      if (!props.chatHelper.agent || !props.chatHelper.session || !props.chatHelper.message) {
        return {
          valid: false,
          error: '[ChatBot] Invalid chatHelper: missing required modules (agent, session, message)',
        };
      }
      return { valid: true };
    }

    if (!props.url) {
      return {
        valid: false,
        error: '[ChatBot] Neither chatHelper nor url provided. Component requires at least one.',
      };
    }

    return { valid: true };
  };

  /**
   * 创建 ChatHelper 实例
   */
  const createChatHelper = (): IChatHelper | null => {
    const validation = validateProps();
    if (!validation.valid) {
      console.error(validation.error);
      initError.value = new Error(validation.error);
      return null;
    }

    if (props.chatHelper) {
      return props.chatHelper;
    }

    const protocol = new AGUIProtocol({
      onStart: () => {
        emit('receive-start');
      },
      onMessage: (_event: unknown) => {
        emit('receive-text');
      },
      onDone: () => {
        emit('receive-end');
        scrollToBottom();
      },
      onError: (error: unknown) => {
        emit('error', error as Error);
      },
    });

    const helper = useChatHelper({
      requestData: {
        urlPrefix: normalizeUrl(props.url!),
        headers: props.requestOptions?.headers,
        data: props.requestOptions?.data,
      },
      protocol,
    }) as unknown as IChatHelper;

    protocol.injectMessageModule(helper.message);

    return helper;
  };

  /**
   * 清理 ChatHelper 资源
   */
  const destroyChatHelper = async (helper: IChatHelper | null, wasStandalone: boolean) => {
    if (!helper) return;
    try {
      const sessionCode = helper.session.current?.value?.sessionCode ?? '';
      await helper.agent.stopChat(sessionCode);
      if (wasStandalone) {
        helper.agent.abortChat();
      }
    } catch {
      // destroy 不应抛出异常阻塞重新初始化
    }
  };

  /**
   * 统一初始化入口（destroy → recreate → reinit）
   * 使用 generation counter 防止快速连续 URL 变化导致的竞态
   */
  let initGeneration = 0;

  const initialize = async () => {
    const currentGen = ++initGeneration;

    const oldHelper = chatHelper.value;
    const wasStandalone = isStandaloneMode.value;

    // 1. 立即重置状态，让 UI 马上展示 loading（不等 stop 请求返回）
    isInitialized.value = false;
    initError.value = null;
    isStandaloneMode.value = !props.chatHelper;

    // 2. 清理旧实例（stop 请求可能较慢，但 loading 已在展示）
    await destroyChatHelper(oldHelper, wasStandalone);

    // 3. 清空旧 ref
    chatHelper.value = null;
    sessionBusinessManager.value = null;
    chatBusinessManager.value = null;
    shortcutManager.value = null;

    // 4. 创建新实例
    const newHelper = createChatHelper();
    if (!newHelper) return;

    const sessionMgr = new SessionBusinessManager(newHelper.session, newHelper.agent, null, {
      enableChatSession: true,
      autoSwitchToInitialSession: !!props.sessionCode,
      loadRecentSessionOnMount: props.autoLoad,
      initialSessionCode: props.sessionCode,
      alwaysCreateNewSession: props.alwaysCreateNewSession,
    });

    const chatMgr = new ChatBusinessManager(newHelper.agent, newHelper.message, newHelper.session, null, {
      openingRemark: props.helloText,
      predefinedQuestions: props.prompts,
      placeholder: props.placeholder,
    });

    const shortcutMgr = new ShortcutManager(null, props.shortcuts || []);

    chatHelper.value = newHelper;
    sessionBusinessManager.value = sessionMgr;
    chatBusinessManager.value = chatMgr;
    shortcutManager.value = shortcutMgr;

    // 5. 执行初始化流程
    try {
      if (isStandaloneMode.value) {
        await Promise.all([newHelper.agent.getAgentInfo(), newHelper.session.getSessions()]);
        if (currentGen !== initGeneration) return;

        await sessionMgr.loadRecentSession({ skipLoadSessions: true });
        if (currentGen !== initGeneration) return;
      }
      isInitialized.value = true;
      emit('agent-info-loaded', newHelper);
    } catch (error) {
      if (currentGen !== initGeneration) return;
      console.error('Failed to initialize ChatBot:', error);
      initError.value = error as Error;
      emit('error', error as Error);
    }
  };

  watch([() => props.url, () => props.chatHelper], () => initialize(), { immediate: true });

  onBeforeUnmount(() => {
    destroyChatHelper(chatHelper.value, isStandaloneMode.value);
  });

  return {
    chatHelper,
    isStandaloneMode,
    isInitialized,
    initError,
    chatBusinessManager,
    sessionBusinessManager,
    shortcutManager,
  };
}
