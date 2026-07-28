import { defineComponent, h, ref } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { createMockChatHelper } from '../../__tests__/helpers';
import ChatBot from '../chat-bot.vue';

const chatContainerPropsRef = { current: {} as Record<string, unknown> };
const messageRenderPropsRef = { current: {} as Record<string, unknown> };
const chatHelperRef = ref(createMockChatHelper());
const handleInterruptResumeRef = vi.fn();

vi.mock('@blueking/chat-x', async importOriginal => {
  const actual = await importOriginal<typeof import('@blueking/chat-x')>();
  return {
    ...actual,
    RenderMode: { Chat: 'chat', Share: 'share', Test: 'test' },
    ChatContainer: defineComponent({
      name: 'ChatContainer',
      props: {
        onInterruptResume: { type: Function, default: undefined },
      },
      setup(props) {
        chatContainerPropsRef.current = props;
        return () => h('div', { class: 'chat-container-stub' });
      },
    }),
    MessageRender: defineComponent({
      name: 'MessageRender',
      props: {
        onInterruptResume: { type: Function, default: undefined },
      },
      setup(props) {
        messageRenderPropsRef.current = props;
        return () => h('div', { class: 'message-render-stub' });
      },
    }),
    ChatInput: defineComponent({ name: 'ChatInput', template: '<div />' }),
  };
});

vi.mock('../composables/use-chatbot-init', () => ({
  useChatbotInit: () => ({
    chatHelper: chatHelperRef,
    isStandaloneMode: ref(true),
    isInitialized: ref(true),
    isReady: ref(true),
    initError: ref(null),
    whenReady: vi.fn().mockResolvedValue(undefined),
    chatBusinessManager: ref(null),
    sessionBusinessManager: ref(null),
    shortcutManager: ref(null),
  }),
}));

vi.mock('../composables/use-interrupt-resume', () => ({
  useInterruptResume: () => ({
    handleInterruptResume: handleInterruptResumeRef,
    resumeUserQuestionWithInput: vi.fn(),
  }),
}));

vi.mock('../composables/use-message-sender', () => ({
  useMessageSender: () => ({
    userInput: ref(''),
    cite: ref(''),
    handleUpdateModelValue: vi.fn(),
    doSendMessage: vi.fn(),
    handleSendMessage: vi.fn(),
    handleUpload: vi.fn(),
    handleArtifactClick: vi.fn(),
    handleStopSending: vi.fn(),
    stopGeneration: vi.fn(),
  }),
}));

vi.mock('../composables/use-shortcuts', () => ({
  useShortcuts: () => ({
    handleSelectShortcut: vi.fn(),
    handleCloseShortcut: vi.fn(),
    handleShortcutSubmit: vi.fn(),
    selectShortcutWithText: vi.fn(),
    getShortcutFromMessage: vi.fn(),
    buildShortcutProperty: vi.fn(),
    sendShortcutDirectly: vi.fn(),
  }),
}));

vi.mock('../composables/use-chatbot-state', () => ({
  useChatbotState: () => ({
    messageStatus: ref({}),
    messageToolsStatus: ref({}),
    messages: ref([{ id: 'msg-1', role: 'assistant', content: 'hello' }]),
    isMessagesLoading: ref(false),
    isGenerating: ref(false),
    currentSession: ref(null),
    isWelcomeState: ref(false),
    openingRemark: ref(''),
    effectiveResources: ref([]),
    effectivePrompts: ref([]),
    effectiveSkills: ref([]),
    effectiveSupportUpload: ref(false),
    chatbotStyle: ref({}),
    filteredShortcuts: ref([]),
  }),
}));

vi.mock('../composables/use-tool-actions', () => ({
  useToolActions: () => ({
    handleAgentAction: vi.fn(),
    handleAgentFeedback: vi.fn(),
    handleUserAction: vi.fn(),
    handleUserInputConfirm: vi.fn(),
    handleUserShortcutConfirm: vi.fn(),
    handleStopStreaming: vi.fn(),
  }),
}));

vi.mock('../composables/use-share-selection', () => ({
  useShareSelection: () => ({
    handleConfirmShare: vi.fn(),
  }),
}));

describe('ChatBot interrupt resume wiring', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatContainerPropsRef.current = {};
    messageRenderPropsRef.current = {};
  });

  it('应将 onInterruptResume 传给 ChatContainer', () => {
    mount(ChatBot, {
      props: { url: 'https://example.com/api/' },
    });

    expect(chatContainerPropsRef.current.onInterruptResume).toBe(handleInterruptResumeRef);
  });
});
