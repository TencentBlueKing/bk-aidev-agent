/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, onBeforeUnmount, onMounted, ref, toValue, watch } from 'vue';

import { Message } from 'bkui-vue';

import { t } from '../lang';
import { createComponentManager } from '../manager';
import { ModelSelectionManager } from '../manager/business/model-selection-manager';
import { SessionBusinessManager } from '../manager/business/session-business-manager';
import { ShareBusinessManager } from '../manager/business/share-business-manager';
import { ShortcutManager } from '../manager/business/shortcut-manager';
import { isTogglePanelShortcut, normalizeUrl } from '../utils';
import { useChatBootstrap } from './use-chat-bootstrap';
import { createEventForwarders, useEventBridge } from './use-event-bridge';

import type ChatBot from '../components/chat-bot.vue';
import type { DraggableContainerExpose } from '../containers';
import type { AIBluekingProps, IShortcut, ReportSdkErrorOptions, SdkErrorApiName } from '../types';
import type { UseEventBridgeReturn } from './use-event-bridge';
import type { ILlmItem } from '@blueking/chat-helper';
import type { IAiSlashMenuItem, ISkillListItem } from '@blueking/chat-x';

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
  /** 已上报错误去重（同一 Error 实例只对外上报一次） */
  const reportedErrors = new WeakSet<Error>();

  /** 延迟上报裸 HTTP 错误，给业务 catch 优先上报语义化 apiName 的机会 */
  let pendingHttpErrorReport: {
    error: Error;
    timer: ReturnType<typeof setTimeout>;
  } | null = null;

  let httpErrorApiNameContext: SdkErrorApiName | null = null;

  const cancelPendingHttpErrorReport = () => {
    if (pendingHttpErrorReport) {
      clearTimeout(pendingHttpErrorReport.timer);
      pendingHttpErrorReport = null;
    }
  };

  /**
   * 统一 SDK 错误出口：toast + sdk-error 仅在此处发生
   * apiName 表达业务语义；source 标识底层来源（http/protocol/business）
   */
  const reportSdkError = (options: ReportSdkErrorOptions) => {
    const { apiName, error, action, source, shouldToast = true } = options;
    const message = error instanceof Error ? error.message : String(error);
    const errorObj = error instanceof Error ? error : null;

    if (errorObj && reportedErrors.has(errorObj)) {
      return;
    }
    if (errorObj) {
      reportedErrors.add(errorObj);
    }

    if (source !== 'http' && errorObj && pendingHttpErrorReport?.error === errorObj) {
      cancelPendingHttpErrorReport();
    }

    console.error(`[AIBlueking] ${apiName} error:`, error);

    if (shouldToast && props.errorToast !== false) {
      Message({
        message: message || t('请求失败'),
        theme: 'error',
      });
    }

    componentManager.emitInternal('sdk-error', {
      apiName,
      action,
      source,
      code: -1,
      message,
      data: error,
    });
  };

  const scheduleHttpErrorReport = (error: Error) => {
    cancelPendingHttpErrorReport();
    const apiName = httpErrorApiNameContext ?? (isBootstrapReady.value ? 'chat' : 'init');
    const timer = setTimeout(() => {
      pendingHttpErrorReport = null;
      reportSdkError({ apiName, error, source: 'http' });
    }, 0);
    pendingHttpErrorReport = { error, timer };
  };

  const runWithHttpErrorApiName = async <T>(apiName: SdkErrorApiName, task: () => Promise<T>): Promise<T> => {
    const previousApiName = httpErrorApiNameContext;
    httpErrorApiNameContext = apiName;
    try {
      return await task();
    } finally {
      httpErrorApiNameContext = previousApiName;
    }
  };

  /** ChatBot 子组件 @error 回调 */
  const handleError = (error: Error) => {
    reportSdkError({ apiName: 'chat', error, source: 'business' });
  };

  // ==================== Bootstrap ====================
  const {
    chatHelper: bootstrapChatHelper,
    isReady: isBootstrapReady,
    error: bootstrapError,
    agentInfo,
    agentName: bootstrapAgentName,
    currentSession,
    initialize: bootstrapInitialize,
  } = useChatBootstrap({
    url: normalizedUrl,
    requestOptions: () => toValue(props.requestOptions),
    autoInit: true,
    enableModelSelect: props.enableModelSelect !== false,
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
        reportSdkError({ apiName: 'chat', error, source: 'protocol' });
      },
    },
  });

  const chatHelper = bootstrapChatHelper;

  // ==================== 统一错误处理 ====================
  // 注册全局 HTTP 错误处理器：延迟上报，让业务 catch 优先使用 session/share/chat 等语义
  chatHelper.onError?.(
    (error: Error) => {
      scheduleHttpErrorReport(error);
    },
    {
      ignoreErrors: props.ignoreErrors,
    },
  );

  // ==================== 模型选择（与内嵌 ChatBot 共享同一实例） ====================
  // 建会话与模型切换读同一份选中状态，避免外壳层反向读取子组件
  const modelSelection = new ModelSelectionManager(chatHelper.agent, chatHelper.session, {
    enabled: props.enableModelSelect !== false,
  });

  /** 建会话前确保模型列表就绪：外部 models 优先，否则复用 bootstrap 已拉取的结果 */
  const ensureModelsReady = async (): Promise<void> => {
    if (props.enableModelSelect === false) {
      return;
    }
    if (props.models?.length) {
      modelSelection.setModels(props.models as ILlmItem[]);
      return;
    }
    await modelSelection.ensureLoaded();
  };

  // ==================== Business Managers ====================
  const sessionBusinessManager = new SessionBusinessManager(
    chatHelper.session,
    chatHelper.agent,
    null,
    {
      enableChatSession: props.enableChatSession,
      initialSessionCode: props.initialSessionCode,
      alwaysCreateNewSession: props.alwaysCreateNewSession,
    },
    chatHelper.message,
    modelSelection,
  );

  const shareBusinessManager = new ShareBusinessManager(chatHelper.message, chatHelper.session);
  const shortcutManager = new ShortcutManager(null, props.shortcuts || []);

  // ==================== 会话就绪（供 show() 等待） ====================
  let recentSessionPromise: null | Promise<void> = null;

  const ensureRecentSessionLoaded = (): Promise<void> => {
    if (!props.loadRecentSessionOnMount) {
      return Promise.resolve();
    }

    if (!recentSessionPromise) {
      // 先确保模型列表就绪，创建首个会话时才能落到「前端可选中」的 model
      recentSessionPromise = ensureModelsReady()
        .then(() => sessionBusinessManager.loadRecentSession({ skipLoadSessions: true }))
        .finally(() => {
          recentSessionPromise = null;
        });
    }

    return recentSessionPromise;
  };

  const ensureSessionReady = async (): Promise<void> => {
    await runWithHttpErrorApiName('init', async () => {
      await bootstrapInitialize();
      await ensureRecentSessionLoaded();
    });
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

  const agentSkills = computed<ISkillListItem[]>(() => {
    return (agentInfo.value?.relatedSkills ?? []).map(skill => ({
      skill_name: skill.skill_name,
      skill_code: skill.skill_code,
      description: skill.description,
      icon: skill.icon,
    }));
  });

  // 监听 Bootstrap 初始化失败（如 Agent 信息获取失败）
  watch(
    () => bootstrapError.value,
    err => {
      if (err) {
        cancelPendingHttpErrorReport();
        reportSdkError({ apiName: 'init', error: err, source: 'http' });
      }
    },
  );

  // ==================== Agent Info 处理 ====================
  /**
   * 处理 agentInfo 数据：更新 shortcutManager
   * 供初始化 watcher 和 updateAgentInfo 复用
   * 注意：ping saasUrl 已移至 runAgentBootstrap 统一处理
   */
  const processAgentInfo = (info: NonNullable<typeof agentInfo.value>) => {
    if (info.conversationSettings?.commands) {
      shortcutManager.setAgentShortcuts(info.conversationSettings.commands as IShortcut[]);
    }
  };

  /**
   * 主动刷新 agentInfo 并更新内部状态
   * 业务方可调用此方法获取最新的 agent 信息，同时会自动更新 shortcuts 等状态
   *
   * @returns 最新的 agentInfo 数据，获取失败返回 null
   */
  const updateAgentInfo = async (): Promise<typeof agentInfo.value> => {
    try {
      await chatHelper.agent.getAgentInfo();
      const info = agentInfo.value;
      if (info) {
        processAgentInfo(info);
      }
      return info;
    } catch (err) {
      reportSdkError({ apiName: 'getAgentInfo', error: err, source: 'http' });
      return null;
    }
  };

  // ==================== Agent 初始化 Watcher ====================
  watch(
    () => isBootstrapReady.value,
    async ready => {
      if (ready && agentInfo.value) {
        processAgentInfo(agentInfo.value);

        if (agentInfo.value.conversationSettings) {
          forwardToManager('session-initialized', {
            openingRemark: agentInfo.value.conversationSettings.openingRemark || '',
            predefinedQuestions: agentInfo.value.conversationSettings.predefinedQuestions || [],
          });
        }

        if (props.loadRecentSessionOnMount) {
          try {
            await ensureRecentSessionLoaded();
          } catch (err) {
            // 含「无可用模型」阻断：需上报，避免静默停在无会话状态
            reportSdkError({ apiName: 'session', action: 'loadRecentSession', error: err, source: 'business' });
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
    cancelPendingHttpErrorReport();
    window.removeEventListener('keydown', handleKeydown);
    componentManager.destroy();
  });

  return {
    chatHelper,
    componentManager,
    modelSelection,
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
    agentResources,
    agentPrompts,
    agentSkills,
    handleError,
    reportSdkError,
    ensureSessionReady,
    updateAgentInfo,
  };
}
