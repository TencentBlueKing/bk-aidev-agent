/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, onBeforeUnmount, ref, shallowRef, toValue, watch } from 'vue';
import type { ComputedRef, Ref } from 'vue';

import { AGUIProtocol, useChatHelper } from '@blueking/chat-helper';

import { runAgentBootstrap } from '../../bootstrap/agent-bootstrap';
import { ChatBusinessManager, SessionBusinessManager, ShortcutManager } from '../../manager';
import { buildRequestDataFromOptions, normalizeUrl, toError } from '../../utils';

import type { IEventEmitter } from '../../manager/business/types';
import type { IChatHelper } from '../../types';
import type { ChatBotProps } from '../types';
import type { ReportChatBotError } from './use-error-reporter';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ChatBotEmitFn = (...args: any[]) => void;

export interface UseChatbotInitParams {
  emit: ChatBotEmitFn;
  /** 注入业务管理器的错误事件桥接器 */
  managerErrorBridge: IEventEmitter;
  props: ChatBotProps;
  reportError: ReportChatBotError;
}

export interface UseChatbotInitReturn {
  chatBusinessManager: Ref<ChatBusinessManager | null>;
  chatHelper: Ref<IChatHelper | null>;
  initError: Ref<Error | null>;
  isInitialized: Ref<boolean>;
  isReady: ComputedRef<boolean>;
  isStandaloneMode: Ref<boolean>;
  sessionBusinessManager: Ref<null | SessionBusinessManager>;
  shortcutManager: Ref<null | ShortcutManager>;
  whenReady: () => Promise<void>;
}

/** URL / chatHelper 变更导致上一轮初始化被取代 */
export class ChatBotInitStaleError extends Error {
  constructor() {
    super('[ChatBot] Initialization was superseded by a newer init');
    this.name = 'ChatBotInitStaleError';
  }
}

export function useChatbotInit(params: UseChatbotInitParams): UseChatbotInitReturn {
  const { props, emit, reportError, managerErrorBridge } = params;

  const chatHelper = shallowRef<IChatHelper | null>(null);
  const sessionBusinessManager = shallowRef<null | SessionBusinessManager>(null);
  const chatBusinessManager = shallowRef<ChatBusinessManager | null>(null);
  const shortcutManager = shallowRef<null | ShortcutManager>(null);
  const isInitialized = ref(false);
  const isStandaloneMode = ref(!props.chatHelper);
  const initError = ref<Error | null>(null);
  const isReady = computed(() => isInitialized.value);

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
      },
      onError: (error: unknown) => {
        reportError(error, 'Stream error');
      },
    });

    const helper = useChatHelper({
      requestData: buildRequestDataFromOptions(normalizeUrl(props.url!), () => toValue(props.requestOptions)),
      protocol,
    }) as unknown as IChatHelper;

    protocol.injectMessageModule(helper.message);

    return helper;
  };

  /**
   * 清理 ChatHelper 资源（仅断开前端 SSE，不调用后端 stop）
   * stopChat 仅应由用户主动点击停止触发，避免 URL 变化/卸载时把后台 agent 杀掉
   */
  const destroyChatHelper = (helper: IChatHelper | null) => {
    if (!helper) return;
    try {
      helper.agent.abortChat();
      helper.agent.clearLongPollTimer?.();
    } catch {
      // destroy 不应抛出异常阻塞重新初始化
    }
  };

  /**
   * 统一初始化入口（destroy → recreate → reinit）
   * 使用 generation counter 防止快速连续 URL 变化导致的竞态
   */
  let initGeneration = 0;
  let initializeInFlight: null | Promise<void> = null;
  let readyResolved: null | Promise<void> = null;
  let settleInFlight: null | {
    reject: (error: Error) => void;
    resolve: () => void;
  } = null;

  const abortInFlightInit = (error?: Error) => {
    if (settleInFlight) {
      if (error) {
        settleInFlight.reject(error);
      } else {
        settleInFlight.resolve();
      }
      settleInFlight = null;
    }
    initializeInFlight = null;
  };

  const assertGeneration = (currentGen: number) => {
    if (currentGen !== initGeneration) {
      throw new ChatBotInitStaleError();
    }
  };

  const runInitialize = async (currentGen: number): Promise<void> => {
    const oldHelper = chatHelper.value;

    isInitialized.value = false;
    initError.value = null;
    isStandaloneMode.value = !props.chatHelper;

    destroyChatHelper(oldHelper);
    assertGeneration(currentGen);

    chatHelper.value = null;
    sessionBusinessManager.value = null;
    chatBusinessManager.value = null;
    shortcutManager.value = null;

    const newHelper = createChatHelper();
    if (!newHelper) {
      const err = initError.value ?? new Error('[ChatBot] Failed to create chatHelper');
      throw err;
    }

    const sessionMgr = new SessionBusinessManager(
      newHelper.session,
      newHelper.agent,
      managerErrorBridge,
      {
        enableChatSession: true,
        autoSwitchToInitialSession: !!props.sessionCode,
        loadRecentSessionOnMount: props.autoLoad,
        initialSessionCode: props.sessionCode,
        alwaysCreateNewSession: props.alwaysCreateNewSession,
      },
      newHelper.message,
    );

    const chatMgr = new ChatBusinessManager(newHelper.agent, newHelper.message, newHelper.session, managerErrorBridge, {
      openingRemark: props.helloText,
      predefinedQuestions: props.prompts,
      placeholder: props.placeholder,
      // 首条消息自动重命名成功 → ChatBot rename → AIBlueking forwarders.rename
      onSessionRenamed: (newName: string, sessionCode: string) => emit('rename', newName, sessionCode),
    });

    const shortcutMgr = new ShortcutManager(null, props.shortcuts || []);

    chatHelper.value = newHelper;
    sessionBusinessManager.value = sessionMgr;
    chatBusinessManager.value = chatMgr;
    shortcutManager.value = shortcutMgr;

    try {
      if (isStandaloneMode.value) {
        await runAgentBootstrap(newHelper, {
          enableModelSelect: props.enableModelSelect !== false && !props.models?.length,
        });
        assertGeneration(currentGen);

        await sessionMgr.loadRecentSession({ skipLoadSessions: true });
        assertGeneration(currentGen);
      }

      // 模型选择：外部 models 优先；否则从接口 / agent 缓存同步到 ChatBusinessManager
      if (props.enableModelSelect !== false) {
        if (props.models?.length) {
          chatMgr.setModels(props.models);
        } else {
          await chatMgr.loadModels();
        }
        assertGeneration(currentGen);
      }

      assertGeneration(currentGen);
      isInitialized.value = true;
      emit('agent-info-loaded', newHelper);
    } catch (error) {
      assertGeneration(currentGen);
      initError.value = reportError(error, 'Failed to initialize ChatBot');
      throw error;
    }
  };

  const initialize = () => {
    abortInFlightInit(new ChatBotInitStaleError());
    readyResolved = null;

    const currentGen = ++initGeneration;

    initializeInFlight = new Promise<void>((resolve, reject) => {
      settleInFlight = { resolve, reject };
      runInitialize(currentGen)
        .then(() => {
          if (settleInFlight) {
            readyResolved = Promise.resolve();
            settleInFlight.resolve();
            settleInFlight = null;
          }
        })
        .catch((error: unknown) => {
          if (settleInFlight) {
            settleInFlight.reject(toError(error));
            settleInFlight = null;
          }
        })
        .finally(() => {
          if (currentGen === initGeneration) {
            initializeInFlight = null;
          }
        });
    });

    // 避免未调用 whenReady 时产生 unhandled rejection；whenReady 调用方仍会收到 reject
    void initializeInFlight.catch(() => {});
  };

  const whenReady = (): Promise<void> => {
    if (isInitialized.value) {
      if (!readyResolved) {
        readyResolved = Promise.resolve();
      }
      return readyResolved;
    }
    if (initError.value) {
      return Promise.reject(initError.value);
    }
    if (initializeInFlight) {
      return initializeInFlight;
    }
    return Promise.resolve();
  };

  watch([() => props.url, () => props.chatHelper], () => initialize(), { immediate: true });

  onBeforeUnmount(() => {
    abortInFlightInit();
    destroyChatHelper(chatHelper.value);
  });

  return {
    chatHelper,
    isStandaloneMode,
    isInitialized,
    isReady,
    initError,
    whenReady,
    chatBusinessManager,
    sessionBusinessManager,
    shortcutManager,
  };
}
