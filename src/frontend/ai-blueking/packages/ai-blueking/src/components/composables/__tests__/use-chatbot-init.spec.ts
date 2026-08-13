import { describe, it, expect, vi, beforeEach } from 'vitest';
import { defineComponent, nextTick, reactive } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';

import { createErrorReporterParams, createMockChatHelper, createMockEmit } from '../../../__tests__/helpers';
import type { ChatBotProps } from '../../types';

// Inline mocks using vi.fn() directly in the factory - no hoisting issues
// since vi.fn() is always available in vi.mock factories
vi.mock('@blueking/chat-helper', async () => {
  const { ref, shallowRef } = await import('vue');
  return {
    AGUIProtocol: vi.fn().mockImplementation(function (this: any) {
      this.injectMessageModule = vi.fn();
    }),
    useChatHelper: vi.fn().mockReturnValue({
      agent: {
        getAgentInfo: vi.fn().mockResolvedValue({}),
        getLlms: vi.fn().mockResolvedValue([]),
        stopChat: vi.fn().mockResolvedValue(undefined),
        abortChat: vi.fn(),
        clearLongPollTimer: vi.fn(),
        info: ref(null),
        isChatting: ref(false),
        isModelsLoading: ref(false),
        models: ref([]),
        chat: vi.fn().mockResolvedValue(undefined),
        resendMessage: vi.fn().mockResolvedValue(undefined),
        handleRole: vi.fn(),
      },
      session: {
        getSessions: vi.fn().mockResolvedValue(undefined),
        loadMoreSessions: vi.fn().mockResolvedValue(undefined),
        hasMore: ref(false),
        isLoadingMore: ref(false),
        page: ref(0),
        numPages: ref(0),
        count: ref(0),
        chooseSession: vi.fn().mockResolvedValue(undefined),
        current: ref(null),
        list: ref([]),
        createSession: vi.fn(),
        deleteSession: vi.fn(),
        getSession: vi.fn(),
        getSessionFeedbackReasons: vi.fn().mockResolvedValue([]),
        isCreateLoading: ref(false),
        isCurrentLoading: ref(false),
        isDeleteLoading: ref(false),
        isListLoading: ref(false),
        isUpdateLoading: ref(false),
        postSessionFeedback: vi.fn(),
        renameSession: vi.fn(),
        updateSession: vi.fn(),
        uploadFile: vi.fn(),
      },
      message: {
        list: shallowRef([]),
        isListLoading: ref(false),
        deleteMessages: vi.fn(),
        shareMessages: vi.fn(),
      },
      http: {},
    }),
  };
});

vi.mock('../../../manager', async () => {
  const { ref, shallowRef } = await import('vue');
  return {
    ChatBusinessManager: vi.fn().mockImplementation(function (this: any) {
      this.messages = shallowRef([]);
      this.isMessagesLoading = ref(false);
      this.isGenerating = ref(false);
      this.isStopLoading = ref(false);
      this.models = ref([]);
      this.selectedLlmCode = ref(undefined);
      this.selectedModelName = ref('');
      this.selectedModelSupportsVision = ref(false);
      this.sendMessage = vi.fn();
      this.stopGeneration = vi.fn();
      this.regenerateFromAIMessages = vi.fn();
      this.resendMessageWithProperty = vi.fn();
      this.loadModels = vi.fn().mockResolvedValue(undefined);
      this.ensureModelsLoaded = vi.fn().mockResolvedValue(undefined);
      this.setModels = vi.fn();
      this.setSelectedModel = vi.fn();
      this.setSelectedModelByName = vi.fn();
    }),
    SessionBusinessManager: vi.fn().mockImplementation(function (this: any) {
      this.currentSession = ref(null);
      this.sessionList = ref([]);
      this.loadRecentSession = vi.fn().mockResolvedValue(undefined);
      this.switchSession = vi.fn();
      this.createNewSession = vi.fn();
    }),
    ShortcutManager: vi.fn().mockImplementation(function (this: any) {
      this.effectiveShortcuts = ref([]);
      this.shortcuts = ref([]);
      this.setShortcuts = vi.fn();
      this.setAgentShortcuts = vi.fn();
    }),
    ModelSelectionManager: vi.fn().mockImplementation(function (this: any) {
      this.selectedLlmCode = ref(undefined);
      this.models = ref([]);
      this.isLoading = ref(false);
      this.selectedModelName = ref('');
      this.selectedModelSupportsVision = ref(false);
      this.ensureLoaded = vi.fn().mockResolvedValue(undefined);
      this.loadModels = vi.fn().mockResolvedValue(undefined);
      this.setModels = vi.fn();
      this.setSelectedModel = vi.fn();
      this.setSelectedModelByName = vi.fn();
      this.resolveModelForSession = vi.fn();
      this.persistSessionModel = vi.fn().mockResolvedValue(undefined);
      this.applySessionModel = vi.fn();
    }),
    ModelUnavailableError: class ModelUnavailableError extends Error {
      constructor(message = '当前没有可用模型，无法创建会话') {
        super(message);
        this.name = 'ModelUnavailableError';
      }
    },
  };
});

vi.mock('../../../utils', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../utils')>();
  return {
    ...actual,
    normalizeUrl: vi.fn((url: string) => url),
  };
});

import { ChatBotInitStaleError, useChatbotInit } from '../use-chatbot-init';
import { AGUIProtocol, useChatHelper } from '@blueking/chat-helper';
import { ChatBusinessManager, SessionBusinessManager, ShortcutManager } from '../../../manager';

function withSetup(composableFn: () => any) {
  let result: any;
  const Comp = defineComponent({
    setup() {
      result = composableFn();
      return () => null;
    },
  });
  const wrapper = mount(Comp);
  return { result, wrapper };
}

function withSetupReactive(propsInit: Partial<ChatBotProps>) {
  const reactiveProps = reactive({ ...propsInit }) as ChatBotProps;
  const emit = createMockEmit();
  let result: any;

  const Comp = defineComponent({
    setup() {
      result = useChatbotInit({
        props: reactiveProps,
        emit,
        ...createErrorReporterParams(emit),
      });
      return () => null;
    },
  });

  const wrapper = mount(Comp);
  return { result, wrapper, reactiveProps, emit };
}

function getMockHelper() {
  return (useChatHelper as any)() as any;
}

describe('useChatbotInit', () => {
  let mockHelper: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockHelper = getMockHelper();
    mockHelper.agent.getAgentInfo.mockResolvedValue({});
    mockHelper.session.getSessions.mockResolvedValue(undefined);
    mockHelper.session.list.value = [];
    mockHelper.session.current.value = null;
  });

  describe('props validation', () => {
    it('should set initError when no url and no chatHelper provided', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: {} as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(result.initError.value).toBeTruthy();
      expect(result.chatHelper.value).toBeNull();
      wrapper.unmount();
    });
  });

  describe('standalone mode', () => {
    it('should create protocol, chatHelper, and managers when url is provided', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(AGUIProtocol).toHaveBeenCalled();
      expect(useChatHelper).toHaveBeenCalled();
      expect(result.isStandaloneMode.value).toBe(true);
      expect(result.chatHelper.value).not.toBeNull();
      expect(result.chatBusinessManager.value).not.toBeNull();
      expect(result.sessionBusinessManager.value).not.toBeNull();
      wrapper.unmount();
    });

    it('should call getAgentInfo and getSessions on mount', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(mockHelper.agent.getAgentInfo).toHaveBeenCalled();
      expect(mockHelper.session.getSessions).toHaveBeenCalled();
      expect(result.isInitialized.value).toBe(true);
      wrapper.unmount();
    });

    it('should choose session by sessionCode when provided', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com', sessionCode: 'my-session' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(result.sessionBusinessManager.value?.loadRecentSession).toHaveBeenCalledWith({ skipLoadSessions: true });
      wrapper.unmount();
    });

    it('should choose first session when sessions exist and no sessionCode', async () => {
      mockHelper.session.list.value = [{ sessionCode: 'latest-session' }];
      const emit = createMockEmit();

      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(result.sessionBusinessManager.value?.loadRecentSession).toHaveBeenCalledWith({ skipLoadSessions: true });
      wrapper.unmount();
    });
  });

  describe('integration mode', () => {
    it('should reuse chatHelper and create managers', async () => {
      const propsChatHelper = createMockChatHelper();
      const emit = createMockEmit();

      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { chatHelper: propsChatHelper } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(result.isStandaloneMode.value).toBe(false);
      expect(result.chatHelper.value).toBe(propsChatHelper);
      expect(ChatBusinessManager).toHaveBeenCalled();
      expect(SessionBusinessManager).toHaveBeenCalled();
      wrapper.unmount();
    });

    it('should skip agent initialization and set initialized immediately on mount', async () => {
      const propsChatHelper = createMockChatHelper();
      const emit = createMockEmit();

      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { chatHelper: propsChatHelper } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(result.isInitialized.value).toBe(true);
      expect(propsChatHelper.agent.getAgentInfo).not.toHaveBeenCalled();
      wrapper.unmount();
    });
  });

  describe('init failure', () => {
    it('should set initError and emit error on initialization failure', async () => {
      const error = new Error('Network error');
      mockHelper.agent.getAgentInfo.mockRejectedValue(error);
      const emit = createMockEmit();

      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(result.initError.value).toEqual(error);
      expect(emit).toHaveBeenCalledWith('error', error);
      wrapper.unmount();
    });
  });

  describe('error bridge wiring', () => {
    it('should pass the manager error bridge to both business managers', async () => {
      const emit = createMockEmit();
      const errorReporterParams = createErrorReporterParams(emit);

      const { wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...errorReporterParams,
        }),
      );

      await flushPromises();

      // 业务管理器的失败事件必须能汇入 error 出口，否则 chat-error / session-error 是死通道
      expect(vi.mocked(ChatBusinessManager).mock.calls[0][3]).toBe(errorReporterParams.managerErrorBridge);
      expect(vi.mocked(SessionBusinessManager).mock.calls[0][2]).toBe(errorReporterParams.managerErrorBridge);

      // 自动重命名成功应经 onSessionRenamed → ChatBot emit('rename')
      const chatConfig = vi.mocked(ChatBusinessManager).mock.calls[0][4] as {
        onSessionRenamed?: (name: string, sessionCode: string) => void;
      };
      expect(typeof chatConfig?.onSessionRenamed).toBe('function');
      chatConfig.onSessionRenamed!('Auto Name', 'session-1');
      expect(emit).toHaveBeenCalledWith('rename', 'Auto Name', 'session-1');
      wrapper.unmount();
    });

    it('should emit error when a business manager reports a failure event', async () => {
      const emit = createMockEmit();
      const errorReporterParams = createErrorReporterParams(emit);

      const { wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...errorReporterParams,
        }),
      );

      await flushPromises();

      const error = new Error('delete failed');
      vi.mocked(ChatBusinessManager).mock.calls[0][3]!.emit('chat-error', { action: 'delete-message', error });

      expect(emit).toHaveBeenCalledWith('error', error);
      wrapper.unmount();
    });
  });

  describe('shortcutManager', () => {
    it('should always create a ShortcutManager', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await flushPromises();

      expect(ShortcutManager).toHaveBeenCalled();
      expect(result.shortcutManager.value).toBeTruthy();
      wrapper.unmount();
    });
  });

  describe('URL change re-initialization', () => {
    it('should re-initialize when url changes', async () => {
      const { result, wrapper, reactiveProps, emit } = withSetupReactive({
        url: 'https://api-v1.example.com',
      });

      await flushPromises();

      expect(result.isInitialized.value).toBe(true);
      const firstCallCount = (ChatBusinessManager as any).mock.calls.length;

      reactiveProps.url = 'https://api-v2.example.com';
      await nextTick();
      await flushPromises();

      expect((ChatBusinessManager as any).mock.calls.length).toBe(firstCallCount + 1);
      expect(result.isInitialized.value).toBe(true);
      expect(result.chatHelper.value).not.toBeNull();
      wrapper.unmount();
    });

    it('should reset isInitialized to false during re-init', async () => {
      let capturedInitializedDuringReinit = true;
      let initResult: ReturnType<typeof useChatbotInit> | null = null;

      const { result, wrapper, reactiveProps } = withSetupReactive({
        url: 'https://api-v1.example.com',
      });
      initResult = result;

      await flushPromises();
      expect(result.isInitialized.value).toBe(true);

      // 仅在第二次 init（url 变化）时捕获 isInitialized，避免首轮 init 的 TDZ/时序干扰
      mockHelper.agent.getAgentInfo.mockImplementation(() => {
        capturedInitializedDuringReinit = initResult!.isInitialized.value;
        return Promise.resolve({});
      });

      reactiveProps.url = 'https://api-v2.example.com';
      await nextTick();

      expect(capturedInitializedDuringReinit).toBe(false);
      await flushPromises();
      expect(result.isInitialized.value).toBe(true);
      wrapper.unmount();
    });

    it('should abortChat on old helper during destroy without stopChat', async () => {
      const { wrapper, reactiveProps } = withSetupReactive({
        url: 'https://api-v1.example.com',
      });

      await flushPromises();
      mockHelper.agent.stopChat.mockClear();
      mockHelper.agent.abortChat.mockClear();

      reactiveProps.url = 'https://api-v2.example.com';
      await nextTick();
      await flushPromises();

      expect(mockHelper.agent.abortChat).toHaveBeenCalled();
      expect(mockHelper.agent.stopChat).not.toHaveBeenCalled();
      wrapper.unmount();
    });

    it('should not re-initialize when url stays the same', async () => {
      const { wrapper, reactiveProps } = withSetupReactive({
        url: 'https://api.example.com',
      });

      await flushPromises();
      const callCount = (ChatBusinessManager as any).mock.calls.length;

      reactiveProps.url = 'https://api.example.com';
      await nextTick();
      await flushPromises();

      expect((ChatBusinessManager as any).mock.calls.length).toBe(callCount);
      wrapper.unmount();
    });
  });

  describe('whenReady / isReady', () => {
    it('should resolve whenReady after standalone init completes', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await expect(result.whenReady()).resolves.toBeUndefined();
      await flushPromises();

      expect(result.isReady.value).toBe(true);
      expect(result.isInitialized.value).toBe(true);
      wrapper.unmount();
    });

    it('should reject whenReady when initialization fails', async () => {
      const error = new Error('Network error');
      mockHelper.agent.getAgentInfo.mockRejectedValue(error);
      const emit = createMockEmit();

      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await expect(result.whenReady()).rejects.toThrow('Network error');
      await flushPromises();

      expect(result.isReady.value).toBe(false);
      wrapper.unmount();
    });

    it('should return the same in-flight promise for concurrent whenReady calls', async () => {
      mockHelper.agent.getAgentInfo.mockImplementation(
        () => new Promise<void>(() => {
          /* hang until unmount */
        }),
      );
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { url: 'https://api.example.com' } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await nextTick();

      const first = result.whenReady();
      const second = result.whenReady();
      expect(first).toBe(second);

      wrapper.unmount();
    });

    it('should resolve whenReady immediately in integration mode', async () => {
      const propsChatHelper = createMockChatHelper();
      const emit = createMockEmit();

      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: { chatHelper: propsChatHelper } as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await expect(result.whenReady()).resolves.toBeUndefined();
      await flushPromises();

      expect(result.isReady.value).toBe(true);
      wrapper.unmount();
    });

    it('should reject whenReady with ChatBotInitStaleError when url changes during init', async () => {
      let resolveSlowInit: (() => void) | null = null;

      mockHelper.agent.getAgentInfo.mockImplementation(() => {
        return new Promise<void>(resolve => {
          resolveSlowInit = resolve;
        });
      });

      const { result, wrapper, reactiveProps } = withSetupReactive({
        url: 'https://api-v1.example.com',
      });

      const readyPromise = result.whenReady();
      await nextTick();

      reactiveProps.url = 'https://api-v2.example.com';
      await nextTick();

      await expect(readyPromise).rejects.toBeInstanceOf(ChatBotInitStaleError);

      if (resolveSlowInit) {
        resolveSlowInit();
      }
      await flushPromises();
      wrapper.unmount();
    });

    it('should reject whenReady when props validation fails', async () => {
      const emit = createMockEmit();
      const { result, wrapper } = withSetup(() =>
        useChatbotInit({
          props: {} as ChatBotProps,
          emit,
          ...createErrorReporterParams(emit),
        }),
      );

      await expect(result.whenReady()).rejects.toThrow();
      await flushPromises();

      expect(result.isReady.value).toBe(false);
      wrapper.unmount();
    });
  });

  describe('generation counter (race condition protection)', () => {
    it('should discard stale initialization when URL changes rapidly', async () => {
      let resolveFirstGetAgentInfo: (() => void) | null = null;
      let getAgentInfoCallCount = 0;

      mockHelper.agent.getAgentInfo.mockImplementation(() => {
        getAgentInfoCallCount++;
        if (getAgentInfoCallCount === 2) {
          return new Promise<void>(resolve => {
            resolveFirstGetAgentInfo = resolve;
          });
        }
        return Promise.resolve({});
      });

      const { result, wrapper, reactiveProps, emit } = withSetupReactive({
        url: 'https://api-v1.example.com',
      });

      await flushPromises();
      expect(result.isInitialized.value).toBe(true);
      emit.mockClear();

      reactiveProps.url = 'https://api-v2.example.com';
      await nextTick();

      reactiveProps.url = 'https://api-v3.example.com';
      await nextTick();
      await flushPromises();

      expect(result.isInitialized.value).toBe(true);

      if (resolveFirstGetAgentInfo) {
        resolveFirstGetAgentInfo();
        await flushPromises();
      }

      const agentInfoLoadedCalls = emit.mock.calls.filter(
        (call: any[]) => call[0] === 'agent-info-loaded',
      );
      expect(agentInfoLoadedCalls.length).toBeGreaterThanOrEqual(1);

      wrapper.unmount();
    });

    it('should not set initError from stale initialization failure', async () => {
      let rejectFirstInit: ((err: Error) => void) | null = null;
      let callCount = 0;

      mockHelper.agent.getAgentInfo.mockImplementation(() => {
        callCount++;
        if (callCount === 2) {
          return new Promise<void>((_resolve, reject) => {
            rejectFirstInit = reject;
          });
        }
        return Promise.resolve({});
      });

      const { result, wrapper, reactiveProps } = withSetupReactive({
        url: 'https://api-v1.example.com',
      });

      await flushPromises();

      reactiveProps.url = 'https://api-v2.example.com';
      await nextTick();

      reactiveProps.url = 'https://api-v3.example.com';
      await nextTick();
      await flushPromises();

      if (rejectFirstInit) {
        rejectFirstInit(new Error('Stale network error'));
        await flushPromises();
      }

      expect(result.initError.value).toBeNull();
      wrapper.unmount();
    });
  });
});
