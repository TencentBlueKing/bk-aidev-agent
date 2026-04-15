import { describe, it, expect, vi } from 'vitest';
import { ref, shallowRef, computed } from 'vue';

import {
  createMockChatHelper,
  createMockChatBusinessManager,
  createMockSessionBusinessManager,
} from '../../../__tests__/helpers';

vi.mock('@blueking/chat-x', () => ({
  MessageStatus: { Streaming: 'streaming', Complete: 'complete' },
  MessageToolsStatus: { Disabled: 'disabled' },
}));

import { useChatbotState } from '../use-chatbot-state';
import type { UseChatbotStateParams } from '../use-chatbot-state';
import type { ChatBotProps } from '../../types';

function createParams(overrides: Partial<UseChatbotStateParams> = {}): UseChatbotStateParams {
  return {
    props: {} as ChatBotProps,
    chatHelper: shallowRef(createMockChatHelper()),
    chatBusinessManager: shallowRef(createMockChatBusinessManager()),
    sessionBusinessManager: shallowRef(createMockSessionBusinessManager()),
    shortcutManager: shallowRef({
      effectiveShortcuts: computed(() => []),
      shortcuts: computed(() => []),
      setShortcuts: vi.fn(),
      setAgentShortcuts: vi.fn(),
    } as any),
    isStandaloneMode: ref(true),
    isInitialized: ref(false),
    selectedShortcut: ref(null),
    ...overrides,
  };
}

describe('useChatbotState', () => {
  describe('messageStatus', () => {
    it('should return Streaming when agent.isChatting is true', () => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.isChatting as any).value = true;
      const params = createParams({ chatHelper });
      const { messageStatus } = useChatbotState(params);
      expect(messageStatus.value).toBe('streaming');
    });

    it('should return Complete when agent.isChatting is false', () => {
      const params = createParams();
      const { messageStatus } = useChatbotState(params);
      expect(messageStatus.value).toBe('complete');
    });

    it('should use props.chatHelper over internal chatHelper', () => {
      const propsChatHelper = createMockChatHelper();
      (propsChatHelper.agent.isChatting as any).value = true;
      const params = createParams({
        props: { chatHelper: propsChatHelper } as ChatBotProps,
        chatHelper: shallowRef(createMockChatHelper()),
      });
      const { messageStatus } = useChatbotState(params);
      expect(messageStatus.value).toBe('streaming');
    });
  });

  describe('messageToolsStatus', () => {
    it('should return Disabled when streaming', () => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.isChatting as any).value = true;
      const params = createParams({ chatHelper });
      const { messageToolsStatus } = useChatbotState(params);
      expect(messageToolsStatus.value).toBe('disabled');
    });

    it('should return undefined when complete', () => {
      const params = createParams();
      const { messageToolsStatus } = useChatbotState(params);
      expect(messageToolsStatus.value).toBeUndefined();
    });
  });

  describe('isWelcomeState', () => {
    it('should return false when standalone and not initialized', () => {
      const params = createParams({ isStandaloneMode: ref(true), isInitialized: ref(false) });
      const { isWelcomeState } = useChatbotState(params);
      expect(isWelcomeState.value).toBe(false);
    });

    it('should return true when initialized and no messages', () => {
      const params = createParams({ isStandaloneMode: ref(true), isInitialized: ref(true) });
      const { isWelcomeState } = useChatbotState(params);
      expect(isWelcomeState.value).toBe(true);
    });

    it('should return false when there are messages', () => {
      const cbm = shallowRef(createMockChatBusinessManager());
      (cbm.value.messages as any).value = [{ id: 1, role: 'user', content: 'hi' }];
      const params = createParams({
        isInitialized: ref(true),
        chatBusinessManager: cbm,
      });
      const { isWelcomeState } = useChatbotState(params);
      expect(isWelcomeState.value).toBe(false);
    });

    it('should return true in integration mode even when not initialized', () => {
      const params = createParams({ isStandaloneMode: ref(false), isInitialized: ref(false) });
      const { isWelcomeState } = useChatbotState(params);
      expect(isWelcomeState.value).toBe(true);
    });
  });

  describe('effectiveResources', () => {
    it('should use props resources when provided', () => {
      const resources = [{ id: 'r1', label: 'Res1' }] as any;
      const params = createParams({ props: { resources } as ChatBotProps });
      const { effectiveResources } = useChatbotState(params);
      expect(effectiveResources.value).toEqual(resources);
    });

    it('should fall back to agent info resources', () => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.info as any).value = { resources: [{ id: 'r2', label: 'Res2' }] };
      const params = createParams({ chatHelper, props: {} as ChatBotProps });
      const { effectiveResources } = useChatbotState(params);
      expect(effectiveResources.value).toEqual([{ id: 'r2', label: 'Res2' }]);
    });

    it('should return empty array when no resources available', () => {
      const params = createParams({ props: {} as ChatBotProps });
      const { effectiveResources } = useChatbotState(params);
      expect(effectiveResources.value).toEqual([]);
    });
  });

  describe('effectivePrompts', () => {
    it('should use props prompts when provided', () => {
      const prompts = ['prompt1', 'prompt2'];
      const params = createParams({ props: { prompts } as ChatBotProps });
      const { effectivePrompts } = useChatbotState(params);
      expect(effectivePrompts.value).toEqual(prompts);
    });

    it('should fall back to agent info predefined questions', () => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.info as any).value = {
        conversationSettings: { predefinedQuestions: ['q1'] },
      };
      const params = createParams({ chatHelper, props: {} as ChatBotProps });
      const { effectivePrompts } = useChatbotState(params);
      expect(effectivePrompts.value).toEqual(['q1']);
    });
  });

  describe('effectiveSupportUpload', () => {
    it('should use selectedShortcut supportUpload when available', () => {
      const selectedShortcut = ref({ id: 's1', name: 'test', supportUpload: { vision: true } }) as any;
      const params = createParams({ selectedShortcut });
      const { effectiveSupportUpload } = useChatbotState(params);
      expect(effectiveSupportUpload.value).toBe(true);
    });

    it('should fall back to agent info supportUpload', () => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.info as any).value = {
        promptSetting: { supportUpload: { vision: true } },
      };
      const params = createParams({ chatHelper, selectedShortcut: ref(null) });
      const { effectiveSupportUpload } = useChatbotState(params);
      expect(effectiveSupportUpload.value).toBe(true);
    });

    it('should return false when no upload support', () => {
      const params = createParams({ selectedShortcut: ref(null) });
      const { effectiveSupportUpload } = useChatbotState(params);
      expect(effectiveSupportUpload.value).toBe(false);
    });
  });

  describe('chatbotStyle', () => {
    it('should convert number height to px', () => {
      const params = createParams({ props: { height: 500 } as ChatBotProps });
      const { chatbotStyle } = useChatbotState(params);
      expect(chatbotStyle.value.height).toBe('500px');
    });

    it('should pass through string height', () => {
      const params = createParams({ props: { height: '100vh' } as ChatBotProps });
      const { chatbotStyle } = useChatbotState(params);
      expect(chatbotStyle.value.height).toBe('100vh');
    });

    it('should convert number maxWidth to px', () => {
      const params = createParams({ props: { maxWidth: 800 } as ChatBotProps });
      const { chatbotStyle } = useChatbotState(params);
      expect(chatbotStyle.value.maxWidth).toBe('800px');
    });
  });
});
