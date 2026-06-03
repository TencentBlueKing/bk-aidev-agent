import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { computed, nextTick, reactive, ref, toValue } from 'vue';

import { useAiBluekingInit } from '../use-ai-blueking-init';

import type { ChatBootstrapOptions } from '../use-chat-bootstrap';
import type { AIBluekingProps } from '../../types';

let capturedBootstrapOptions: ChatBootstrapOptions | undefined;
let capturedOnErrorHandler: ((error: Error) => void) | undefined;
let capturedOnErrorOptions: { ignoreErrors?: Array<RegExp | string> } | undefined;
let latestBootstrapReturn: {
  error: ReturnType<typeof ref<Error | null>>;
  isReady: ReturnType<typeof ref<boolean>>;
} | null = null;
const mockEmitInternal = vi.fn();
const mockMessage = vi.fn();
const mockLoadRecentSession = vi.fn().mockResolvedValue(undefined);

vi.mock('bkui-vue', () => ({
  Message: (...args: unknown[]) => mockMessage(...args),
}));

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
    latestBootstrapReturn = { error: localError, isReady: localIsReady };
    return {
      agentInfo: ref(null),
      agentName: ref(''),
      chatHelper: {
        agent: {},
        message: { list: ref([]) },
        session: {},
        onError: (
          handler: (error: Error) => void,
          options?: { ignoreErrors?: Array<RegExp | string> },
        ) => {
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

function getSdkErrorCalls() {
  return mockEmitInternal.mock.calls.filter(call => call[0] === 'sdk-error');
}

async function flushMicrotasks() {
  await Promise.resolve();
  await nextTick();
  vi.runOnlyPendingTimers();
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
    expect(mockMessage).toHaveBeenCalledTimes(1);
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
    expect(mockMessage).toHaveBeenCalledTimes(1);
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
    expect(mockMessage).toHaveBeenCalledTimes(1);
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
    expect(mockMessage).toHaveBeenCalledTimes(1);
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
    expect(mockMessage).not.toHaveBeenCalled();
  });

  it('registers ignoreErrors on chatHelper.onError', () => {
    const ignoreErrors = [/health-check/];
    useAiBluekingInit({
      props: createDefaultProps({ ignoreErrors }),
      emit: vi.fn(),
    });

    expect(capturedOnErrorOptions).toEqual({ ignoreErrors });
  });
});
