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

  describe('effectiveMenuSources', () => {
    it('should prefer props over agent.info and merge three channels', () => {
      const params = createParams({
        props: {
          skills: [{ skill_code: 's1', skill_name: 'Skill 1', description: '', icon: '' }],
          resources: [{ type: 'tool', name: '搜索工具', code: 'search_tool', id: 1, icon: '' }],
          prompts: ['完整提示词'],
        } as ChatBotProps,
      });
      const { effectiveMenuSources } = useChatbotState(params);
      expect(effectiveMenuSources.value).toEqual([
        { type: 'skill', id: 's1', name: 'Skill 1', description: '', icon: '' },
        { type: 'tool', id: 'search_tool', name: '搜索工具', icon: '' },
        { type: 'prompt', id: 'prompt-0', name: '完整提示词', content: '完整提示词' },
      ]);
    });

    it('should fall back to agent.info with real API shape', () => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.info as any).value = {
        relatedSkills: [{ skill_code: 'code_review', skill_name: '代码审查', description: 'desc', icon: 'i' }],
        resources: [
          { type: 'mcp', name: '监控', code: 'monitor_mcp', id: 2, icon: '' },
          { type: 'knowledgebase', name: '运维知识库', code: 'ops_kb', id: 58, icon: '' },
        ],
        conversationSettings: { predefinedQuestions: ['q1'] },
      };
      const params = createParams({ chatHelper, props: {} as ChatBotProps });
      const { effectiveMenuSources } = useChatbotState(params);
      expect(effectiveMenuSources.value.map(item => `${item.type}:${item.id}`)).toEqual([
        'skill:code_review',
        'mcp:monitor_mcp',
        'knowledgebase:58',
        'prompt:prompt-0',
      ]);
    });

    it('should return empty array when no menu sources available', () => {
      const params = createParams({ props: {} as ChatBotProps });
      const { effectiveMenuSources } = useChatbotState(params);
      expect(effectiveMenuSources.value).toEqual([]);
    });
  });

  describe('effectiveSupportUpload', () => {
    it('should use selectedShortcut supportUpload when available', () => {
      const selectedShortcut = ref({ id: 's1', name: 'test', supportUpload: { vision: true } }) as any;
      const params = createParams({ selectedShortcut });
      const { effectiveSupportUpload } = useChatbotState(params);
      expect(effectiveSupportUpload.value).toBe(true);
    });

    it('should use selected model property.support_vision', () => {
      const chatBusinessManager = shallowRef(createMockChatBusinessManager());
      (chatBusinessManager.value.selectedModelSupportsVision as any).value = true;
      const params = createParams({ chatBusinessManager, selectedShortcut: ref(null) });
      const { effectiveSupportUpload } = useChatbotState(params);
      expect(effectiveSupportUpload.value).toBe(true);
    });

    it('should return false when selected model does not support vision', () => {
      const chatBusinessManager = shallowRef(createMockChatBusinessManager());
      (chatBusinessManager.value.selectedModelSupportsVision as any).value = false;
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.info as any).value = {
        promptSetting: { supportUpload: { vision: true } },
      };
      const params = createParams({ chatBusinessManager, chatHelper, selectedShortcut: ref(null) });
      const { effectiveSupportUpload } = useChatbotState(params);
      expect(effectiveSupportUpload.value).toBe(false);
    });

    it('should treat truthy support_vision as enabled via manager computed', () => {
      const chatBusinessManager = shallowRef(createMockChatBusinessManager());
      (chatBusinessManager.value.selectedModelSupportsVision as any).value = true;
      const params = createParams({ chatBusinessManager, selectedShortcut: ref(null) });
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

  describe('claw agent toolbar hiding', () => {
    const setAgentType = (agentType?: string) => {
      const chatHelper = shallowRef(createMockChatHelper());
      (chatHelper.value.agent.info as any).value = agentType === undefined ? {} : { agentType };
      return chatHelper;
    };

    it('should hide rebuild/edit/delete when agentType is claw', () => {
      const params = createParams({ chatHelper: setAgentType('claw'), props: {} as ChatBotProps });
      const { effectiveMessageTools, effectiveUpdateTools, effectiveUserMessageTools } = useChatbotState(params);
      expect(effectiveMessageTools.value).toEqual([{ id: 'rebuild', hidden: true }]);
      expect(effectiveUpdateTools.value).toEqual([{ id: 'delete', hidden: true }]);
      expect(effectiveUserMessageTools.value).toEqual([
        { id: 'edit', hidden: true },
        { id: 'delete', hidden: true },
      ]);
    });

    it('should prepend claw hidden flags so they take precedence over consumer tools', () => {
      const params = createParams({
        chatHelper: setAgentType('claw'),
        props: {
          messageTools: [{ id: 'rebuild', name: '重新生成' }],
          updateTools: [{ id: 'delete', name: '删除' }],
        } as ChatBotProps,
      });
      const { effectiveMessageTools, effectiveUpdateTools } = useChatbotState(params);
      expect(effectiveMessageTools.value?.[0]).toEqual({ id: 'rebuild', hidden: true });
      expect(effectiveUpdateTools.value?.[0]).toEqual({ id: 'delete', hidden: true });
    });

    it('should pass through consumer tools when agentType is single', () => {
      const messageTools = [{ id: 'save', name: '保存' }];
      const params = createParams({
        chatHelper: setAgentType('single'),
        props: { messageTools } as ChatBotProps,
      });
      const { effectiveMessageTools, effectiveUpdateTools, effectiveUserMessageTools } = useChatbotState(params);
      expect(effectiveMessageTools.value).toEqual(messageTools);
      expect(effectiveUpdateTools.value).toBeUndefined();
      expect(effectiveUserMessageTools.value).toBeUndefined();
    });

    it('should not hide tools when agentType is absent', () => {
      const params = createParams({ chatHelper: setAgentType(), props: {} as ChatBotProps });
      const { effectiveMessageTools, effectiveUpdateTools, effectiveUserMessageTools } = useChatbotState(params);
      expect(effectiveMessageTools.value).toBeUndefined();
      expect(effectiveUpdateTools.value).toBeUndefined();
      expect(effectiveUserMessageTools.value).toBeUndefined();
    });
  });
});
