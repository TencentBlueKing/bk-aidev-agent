/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import {
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
  computed,
  ref,
  toValue,
  watch,
} from 'vue';

import { AGUIProtocol, useChatHelper } from '@blueking/chat-helper';

import type { IChatHelper, IRequestOptions } from '../types';
import type { IAgentInfo, ISession } from '@blueking/chat-helper';

/**
 * Bootstrap 阶段枚举
 */
export enum BootstrapPhase {
  /** 初始化失败 */
  ERROR = 'error',
  /** 未开始 */
  IDLE = 'idle',
  /** 正在获取 Agent 信息 */
  LOADING_AGENT = 'loading_agent',
  /** 初始化完成（Agent 信息已获取，会话初始化由 SessionBusinessManager 负责） */
  READY = 'ready',
}

/**
 * useChatBootstrap 配置选项
 */
export interface ChatBootstrapOptions {
  /** 是否自动初始化（默认 true） */
  autoInit?: boolean;
  /** 请求配置 */
  requestOptions?: IRequestOptions;
  /** API 服务地址（支持响应式） */
  url: MaybeRefOrGetter<string>;
  /** Protocol 事件回调 */
  protocolCallbacks?: {
    onDone?: () => void;
    onError?: (error: unknown) => void;
    onMessage?: (event: unknown) => void;
    onStart?: () => void;
  };
}

/**
 * useChatBootstrap 返回值
 */
export interface ChatBootstrapReturn {
  // ==================== 数据 ====================
  /** Agent 信息 */
  agentInfo: ComputedRef<IAgentInfo | null>;
  /** Agent 名称 */
  agentName: ComputedRef<string>;

  // ==================== 核心实例 ====================
  /** ChatHelper 实例（生命周期内不变） */
  chatHelper: IChatHelper;
  /** 当前会话 */
  currentSession: ComputedRef<ISession | null>;
  /** 初始化错误 */
  error: Ref<Error | null>;
  /** 是否正在初始化 */
  isInitializing: ComputedRef<boolean>;

  /** 是否已初始化完成 */
  isReady: ComputedRef<boolean>;
  // ==================== 状态 ====================
  /** 当前初始化阶段 */
  phase: Ref<BootstrapPhase>;
  /** Protocol 实例 */
  protocol: AGUIProtocol;
  /** 会话列表 */
  sessionList: ComputedRef<ISession[]>;

  /** 获取扩展方法 */
  getExtension: <T extends (...args: any[]) => any>(key: string) => T | undefined;
  // ==================== 方法 ====================
  /** 初始化（获取 Agent 信息 + 加载最近会话） */
  initialize: () => Promise<void>;
  // ==================== 扩展预留 ====================
  /**
   * 扩展方法注册器
   * 用于未来添加更多组合式业务逻辑
   * @example
   * const { registerExtension } = useChatBootstrap({ url: '...' });
   * registerExtension('createNewSession', async () => { ... });
   */
  registerExtension: <T extends (...args: any[]) => any>(key: string, fn: T) => void;

  /** 重试初始化 */
  retry: () => Promise<void>;
  /**
   * 更新配置并重新初始化
   * @param newUrl 新的 URL
   */
  updateConfig: (newUrl: string) => Promise<void>;
}

/**
 * 聊天初始化 Composable
 *
 * 职责单一：只负责创建 ChatHelper 和获取 Agent 信息
 * 会话管理由 SessionBusinessManager 统一负责
 *
 * 初始化流程：
 * 1. 创建 ChatHelper 实例（同步，生命周期内不变）
 * 2. 获取 Agent 信息 (getAgentInfo)
 *
 * 注意：会话初始化应在 isReady 后通过 SessionBusinessManager.loadRecentSession() 执行
 *
 * @example
 * ```ts
 * // 基础用法
 * const { chatHelper, isReady, agentInfo } = useChatBootstrap({
 *   url: '/api/chat',
 *   autoInit: true,
 * });
 *
 * // 会话初始化由 SessionBusinessManager 负责
 * watch(isReady, (ready) => {
 *   if (ready) {
 *     sessionBusinessManager.loadRecentSession();
 *   }
 * });
 * ```
 */
export function useChatBootstrap(options: ChatBootstrapOptions): ChatBootstrapReturn {
  // ==================== 配置处理 ====================
  const {
    url: urlOption,
    requestOptions,
    autoInit = true,
    protocolCallbacks,
  } = options;

  // 获取初始 URL 值
  const initialUrl = toValue(urlOption);
  if (!initialUrl) {
    throw new Error('[useChatBootstrap] url is required');
  }

  // ==================== 状态 ====================
  const phase = ref<BootstrapPhase>(BootstrapPhase.IDLE);
  const error = ref<Error | null>(null);
  /** 标记是否已完成过初始化（用于防止重复初始化） */
  const hasInitializedOnce = ref(false);

  // 扩展方法存储
  const extensions = new Map<string, (...args: any[]) => any>();

  // ==================== Protocol 创建 ====================
  const protocol = new AGUIProtocol({
    onStart: () => {
      protocolCallbacks?.onStart?.();
    },
    onMessage: (event: unknown) => {
      protocolCallbacks?.onMessage?.(event);
    },
    onDone: () => {
      protocolCallbacks?.onDone?.();
    },
    onError: (err: unknown) => {
      protocolCallbacks?.onError?.(err);
    },
  });

  // ==================== ChatHelper 创建（同步，生命周期内不变） ====================
  const chatHelper = useChatHelper({
    requestData: {
      urlPrefix: initialUrl,
      headers: requestOptions?.headers,
      data: requestOptions?.data,
    },
    protocol,
  }) as unknown as IChatHelper;

  // 注入消息模块到 protocol
  protocol.injectMessageModule(chatHelper.message);

  // ==================== 计算属性 ====================
  const isInitializing = computed(() => phase.value === BootstrapPhase.LOADING_AGENT);

  const isReady = computed(() => phase.value === BootstrapPhase.READY);

  // chatHelper 不是 ref，所以访问内部的 ref 属性需要 .value
  const agentInfo = computed(() => chatHelper.agent.info.value ?? null);

  const agentName = computed(() => agentInfo.value?.agentName ?? '');

  const currentSession = computed(() => chatHelper.session.current.value ?? null);

  const sessionList = computed(() => chatHelper.session.list.value ?? []);

  // ==================== 初始化流程 ====================
  /**
   * 执行初始化流程（并行获取 Agent 信息和会话列表）
   *
   * 优化：getAgentInfo 和 getSessions 并行执行，减少初始化时间
   *
   * 注意：
   * - 初始化只会执行一次，后续调用会被忽略（除非通过 retry 或 updateConfig 重置）
   * - 会话列表已在初始化时预加载，SessionBusinessManager.loadRecentSession() 会跳过重复加载
   */
  const initialize = async (): Promise<void> => {
    // 防止重复初始化：如果已经初始化过，直接返回
    if (hasInitializedOnce.value) {
      return;
    }

    // 防止并发初始化
    if (isInitializing.value) {
      return;
    }

    // 重置错误状态
    error.value = null;

    try {
      phase.value = BootstrapPhase.LOADING_AGENT;

      // 并行获取 Agent 信息和会话列表，优化初始化性能
      await Promise.all([
        chatHelper.agent.getAgentInfo(),
        chatHelper.session.getSessions(),
      ]);

      // 初始化完成
      phase.value = BootstrapPhase.READY;
      hasInitializedOnce.value = true;
    } catch (err) {
      console.error('[useChatBootstrap] Initialization failed:', err);
      error.value = err as Error;
      phase.value = BootstrapPhase.ERROR;
      throw err;
    }
  };

  /**
   * 重试初始化
   */
  const retry = async (): Promise<void> => {
    // 重置状态，允许重新初始化
    phase.value = BootstrapPhase.IDLE;
    error.value = null;
    hasInitializedOnce.value = false;

    // 重新初始化
    await initialize();
  };

  /**
   * 更新配置并重新初始化
   * TODO: 待 chatHelper 实现 updateConfig 方法后完善
   * @param newUrl 新的 URL
   */
  const updateConfig = async (newUrl: string): Promise<void> => {
    // 重置状态，允许重新初始化
    phase.value = BootstrapPhase.IDLE;
    error.value = null;
    hasInitializedOnce.value = false;

    // TODO: 调用 chatHelper.updateConfig({ urlPrefix: newUrl }) 更新配置
    // 目前 chatHelper 尚未实现此方法，暂时通过 http 模块直接更新
    const httpModule = chatHelper.http as {
      updateConfig?: (config: { urlPrefix: string }) => void;
    };
    if (httpModule?.updateConfig) {
      httpModule.updateConfig({ urlPrefix: newUrl });
    } else {
      console.warn(
        '[useChatBootstrap] chatHelper.http.updateConfig is not implemented yet, URL change may not take effect'
      );
    }

    // 重新初始化
    await initialize();
  };

  // ==================== 扩展方法 ====================
  const registerExtension = <T extends (...args: any[]) => any>(key: string, fn: T): void => {
    extensions.set(key, fn);
  };

  const getExtension = <T extends (...args: any[]) => any>(key: string): T | undefined => {
    return extensions.get(key) as T | undefined;
  };

  // ==================== URL 变化监听 ====================
  // 如果 url 是响应式的，监听其变化并重新初始化
  watch(
    () => toValue(urlOption),
    (newUrl, oldUrl) => {
      if (newUrl && newUrl !== oldUrl && oldUrl) {
        // URL 变化时更新配置并重新初始化
        updateConfig(newUrl).catch(() => {
          // 错误已在 initialize 内部处理（设置 error.value + phase = ERROR）
          // 此处仅防止 unhandled promise rejection
        });
      }
    }
  );

  // ==================== 自动初始化 ====================
  if (autoInit) {
    // 延迟到下一个微任务，确保调用者可以先获取返回值
    // 注意：不在此处 catch，错误由调用方通过 watch phase/error 或 onInitError 回调处理
    Promise.resolve().then(() => {
      initialize().catch(() => {
        // 错误已在 initialize 内部处理（设置 error.value + phase = ERROR）
        // 此处仅防止 unhandled promise rejection，不再 re-throw
      });
    });
  }

  // ==================== 返回值 ====================
  return {
    // 核心实例
    chatHelper,
    protocol,

    // 状态
    phase,
    isInitializing,
    isReady,
    error,

    // 数据
    agentInfo,
    agentName,
    currentSession,
    sessionList,

    // 方法
    initialize,
    retry,
    updateConfig,

    // 扩展
    registerExtension,
    getExtension,
  };
}
