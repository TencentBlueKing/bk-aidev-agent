import { computed, nextTick, reactive, ref, toValue } from 'vue';

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAiBluekingInit } from '../use-ai-blueking-init';

import type { AIBluekingProps } from '../../types';
import type { ChatBootstrapOptions } from '../use-chat-bootstrap';

let capturedBootstrapOptions: ChatBootstrapOptions | undefined;
let capturedOnErrorHandler: ((error: Error) => void) | undefined;
let capturedOnErrorOptions: undefined | { ignoreErrors?: Array<RegExp | string> };
let latestBootstrapReturn: null | {
  agentInfo: ReturnType<typeof ref<unknown>>;
  error: ReturnType<typeof ref<Error | null>>;
  isReady: ReturnType<typeof ref<boolean>>;
} = null;
const mockEmitInternal = vi.fn();
const mockShowToast = vi.fn();
const mockLoadRecentSession = vi.fn().mockResolvedValue(undefined);

vi.mock('@blueking/chat-x', async importOriginal => {
  const actual = await importOriginal<typeof import('@blueking/chat-x')>();
  return {
    ...actual,
    showToast: (...args: unknown[]) => mockShowToast(...args),
  };
});

vi.mock('../../manager', () => ({
  createComponentManager: vi.fn(() => ({
    panelVisible: ref(false),
    nimbusMinimized: ref(false),
    isCompressed: ref(false),
    destroy: vi.fn(),
    emitInternal: mockEmitInternal,
    hidePanel: vi.fn(),
    setContainerRef: vi.fn(),
    showPanel: vi.fn(),
  })),
}));

vi.mock('../../manager/business/model-selection-manager', () => ({
  ModelSelectionManager: vi.fn().mockImplementation(function MockModelSelectionManager() {
    return {
      selectedLlmCode: ref(undefined),
      models: ref([]),
      isLoading: ref(false),
      ensureLoaded: vi.fn().mockResolvedValue(undefined),
      setModels: vi.fn(),
      resolveModelForSession: vi.fn(),
      persistSessionModel: vi.fn().mockResolvedValue(undefined),
    };
  }),
  ModelUnavailableError: class ModelUnavailableError extends Error {
    constructor(message = '当前没有可用模型，无法创建会话') {
      super(message);
      this.name = 'ModelUnavailableError';
    }
  },
}));

vi.mock('../../manager/business/session-business-manager', () => ({
  SessionBusinessManager: vi.fn().mockImplementation(function MockSessionBusinessManager() {
    return {
      loadRecentSession: mockLoadRecentSession,
    };
  }),
}));

vi.mock('../../manager/business/share-business-manager', () => ({
  ShareBusinessManager: vi.fn().mockImplementation(function MockShareBusinessManager() {
    return {};
  }),
}));

vi.mock('../../manager/business/shortcut-manager', () => ({
  ShortcutManager: vi.fn().mockImplementation(function MockShortcutManager() {
    return {
      setAgentShortcuts: vi.fn(),
      setShortcuts: vi.fn(),
    };
  }),
}));

vi.mock('../use-event-bridge', () => ({
  createEventForwarders: vi.fn(() => ({
    receiveDone: vi.fn(),
    receiveEnd: vi.fn(),
    receiveStart: vi.fn(),
    receiveText: vi.fn(),
  })),
  useEventBridge: vi.fn(() => ({
    forwardToManager: vi.fn(),
  })),
}));

vi.mock('../use-chat-bootstrap', () => ({
  useChatBootstrap: vi.fn((options: ChatBootstrapOptions) => {
    capturedBootstrapOptions = options;
    const localError = ref<Error | null>(null);
    const localIsReady = ref(false);
    const localAgentInfo = ref(null);
    latestBootstrapReturn = { agentInfo: localAgentInfo, error: localError, isReady: localIsReady };
    return {
      agentInfo: localAgentInfo,
      agentName: ref(''),
      chatHelper: {
        agent: {},
        message: { list: ref([]) },
        session: {},
        onError: (handler: (error: Error) => void, options?: { ignoreErrors?: Array<RegExp | string> }) => {
          capturedOnErrorHandler = handler;
          capturedOnErrorOptions = options;
        },
      },
      currentSession: ref(null),
      error: localError,
      initialize: vi.fn().mockResolvedValue(undefined),
      isReady: localIsReady,
    };
  }),
}));

function createDefaultProps(overrides: Partial<AIBluekingProps> = {}): AIBluekingProps {
  return reactive({
    defaultMinimize: false,
    draggable: true,
    enablePopup: true,
    hideNimbus: false,
    url: '/api/chat/',
    ...overrides,
  }) as AIBluekingProps;
}

async function flushMicrotasks() {
  await Promise.resolve();
  await nextTick();
  vi.runOnlyPendingTimers();
}

function getSdkErrorCalls() {
  return mockEmitInternal.mock.calls.filter(call => call[0] === 'sdk-error');
}

describe('useAiBluekingInit requestOptions', () => {
  it('passes requestOptions as a getter so bootstrap reads latest prop value', () => {
    const props = createDefaultProps({
      requestOptions: computed(() => ({
        data: { app_id: 'app-1' },
        headers: { Authorization: 'Bearer token-1' },
      })),
    });

    useAiBluekingInit({
      props,
      emit: vi.fn(),
    });

    expect(typeof capturedBootstrapOptions?.requestOptions).toBe('function');
    expect(toValue(capturedBootstrapOptions?.requestOptions)).toEqual({
      data: { app_id: 'app-1' },
      headers: { Authorization: 'Bearer token-1' },
    });

    props.requestOptions = computed(() => ({
      data: { app_id: 'app-2' },
      headers: { Authorization: 'Bearer token-2' },
    }));

    expect(toValue(capturedBootstrapOptions?.requestOptions)).toEqual({
      data: { app_id: 'app-2' },
      headers: { Authorization: 'Bearer token-2' },
    });
  });
});

describe('useAiBluekingInit error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    capturedOnErrorHandler = undefined;
    capturedOnErrorOptions = undefined;
    latestBootstrapReturn = null;
    mockLoadRecentSession.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('reports bootstrap init failure once with apiName init', async () => {
    useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn() });

    const initError = new Error('init failed');
    latestBootstrapReturn!.error.value = initError;
    await nextTick();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'init',
      source: 'http',
      message: 'init failed',
    });
    expect(mockShowToast).toHaveBeenCalledTimes(1);
  });

  it('uses injected toast instead of default showToast', async () => {
    const toast = vi.fn();
    useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn(), toast });

    latestBootstrapReturn!.error.value = new Error('init failed');
    await nextTick();

    expect(toast).toHaveBeenCalledWith({ message: 'init failed', theme: 'error' });
    expect(mockShowToast).not.toHaveBeenCalled();
  });

  it('reports deferred bare HTTP error as init before bootstrap ready', async () => {
    useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn() });

    const httpError = new Error('network error');
    capturedOnErrorHandler?.(httpError);
    await flushMicrotasks();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'init',
      source: 'http',
    });
    expect(mockShowToast).toHaveBeenCalledTimes(1);
  });

  it('reports deferred bare HTTP error as chat after bootstrap ready', async () => {
    useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn() });
    latestBootstrapReturn!.isReady.value = true;

    const httpError = new Error('network error');
    capturedOnErrorHandler?.(httpError);
    await flushMicrotasks();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'chat',
      source: 'http',
    });
  });

  it('reports ensureSessionReady recent session HTTP failure as init even after bootstrap ready', async () => {
    const { ensureSessionReady } = useAiBluekingInit({
      props: createDefaultProps({ loadRecentSessionOnMount: true }),
      emit: vi.fn(),
    });
    latestBootstrapReturn!.isReady.value = true;

    const error = new Error('load recent failed');
    mockLoadRecentSession.mockImplementationOnce(() => {
      capturedOnErrorHandler?.(error);
      return Promise.reject(error);
    });

    await expect(ensureSessionReady()).rejects.toThrow('load recent failed');
    await flushMicrotasks();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'init',
      source: 'http',
    });
  });

  it('protocol stream error reports chat once without duplicate http sdk-error', async () => {
    useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn() });

    const streamError = new Error('stream failed');
    capturedBootstrapOptions?.protocolCallbacks?.onError?.(streamError);
    capturedOnErrorHandler?.(streamError);
    await flushMicrotasks();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'chat',
      source: 'protocol',
    });
    expect(mockShowToast).toHaveBeenCalledTimes(1);
  });

  it('business reportSdkError cancels deferred HTTP report and uses semantic apiName', async () => {
    const { reportSdkError } = useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn() });

    const httpError = new Error('rename failed');
    capturedOnErrorHandler?.(httpError);
    reportSdkError({ apiName: 'session', action: 'rename', error: httpError, source: 'business' });
    await flushMicrotasks();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'session',
      action: 'rename',
      source: 'business',
    });
    expect(mockShowToast).toHaveBeenCalledTimes(1);
  });

  it('handleError reports chat with business source', () => {
    const { handleError } = useAiBluekingInit({ props: createDefaultProps(), emit: vi.fn() });

    const error = new Error('send failed');
    handleError(error);

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(getSdkErrorCalls()[0][1]).toMatchObject({
      apiName: 'chat',
      source: 'business',
    });
  });

  it('respects errorToast false', async () => {
    useAiBluekingInit({
      props: createDefaultProps({ errorToast: false }),
      emit: vi.fn(),
    });

    const error = new Error('silent error');
    latestBootstrapReturn!.error.value = error;
    await nextTick();

    expect(getSdkErrorCalls()).toHaveLength(1);
    expect(mockShowToast).not.toHaveBeenCalled();
  });

  it('registers ignoreErrors on chatHelper.onError', () => {
    const ignoreErrors = [/health-check/];
    useAiBluekingInit({
      props: createDefaultProps({ ignoreErrors }),
      emit: vi.fn(),
    });

    expect(capturedOnErrorOptions).toEqual({ ignoreErrors });
  });

  it('does not map agent.info into resources/prompts/skills; host props stay passthrough', () => {
    const result = useAiBluekingInit({
      props: createDefaultProps({
        prompts: ['host prompt'],
        resources: [{ type: 'tool', name: '搜索', code: 'search', id: 1, icon: '' }],
      }),
      emit: vi.fn(),
    });

    expect(result).not.toHaveProperty('agentResources');
    expect(result).not.toHaveProperty('agentPrompts');
    expect(result).not.toHaveProperty('agentSkills');
  });
});

describe('useAiBluekingInit conversation flags', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    latestBootstrapReturn = null;
  });

  it('disables chat session when agent enableChatSession is false', () => {
    const { effectiveEnableChatSession } = useAiBluekingInit({
      props: createDefaultProps({ enableChatSession: true }),
      emit: vi.fn(),
    });

    latestBootstrapReturn!.agentInfo.value = {
      conversationSettings: { enableChatSession: false },
    };

    expect(effectiveEnableChatSession.value).toBe(false);
  });

  it('disables popup when agent enableWordSelectionPopup is false', () => {
    const { effectiveEnablePopup } = useAiBluekingInit({
      props: createDefaultProps({ enablePopup: true }),
      emit: vi.fn(),
    });

    latestBootstrapReturn!.agentInfo.value = {
      conversationSettings: { enableWordSelectionPopup: false },
    };

    expect(effectiveEnablePopup.value).toBe(false);
  });

  it('keeps flags enabled when agent fields are absent', () => {
    const { effectiveEnableChatSession, effectiveEnablePopup } = useAiBluekingInit({
      props: createDefaultProps(),
      emit: vi.fn(),
    });

    expect(effectiveEnableChatSession.value).toBe(true);
    expect(effectiveEnablePopup.value).toBe(true);
  });

  it('forces flags off when host props are false even if agent enables them', () => {
    const { effectiveEnableChatSession, effectiveEnablePopup } = useAiBluekingInit({
      props: createDefaultProps({ enableChatSession: false, enablePopup: false }),
      emit: vi.fn(),
    });

    latestBootstrapReturn!.agentInfo.value = {
      conversationSettings: { enableChatSession: true, enableWordSelectionPopup: true },
    };

    expect(effectiveEnableChatSession.value).toBe(false);
    expect(effectiveEnablePopup.value).toBe(false);
  });
});
