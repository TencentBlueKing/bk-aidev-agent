import { defineComponent, h, ref, shallowRef } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { createMockChatHelper } from '../../__tests__/helpers';
import ChatBot from '../chat-bot.vue';
import type { CustomBkFlowTab } from '@blueking/chat-x';

const chatContainerPropsRef = { current: {} as Record<string, unknown> };
const chatHelperRef = ref(createMockChatHelper());

vi.mock('@blueking/chat-x', async importOriginal => {
  const actual = await importOriginal<typeof import('@blueking/chat-x')>();
  return {
    ...actual,
    RenderMode: { Chat: 'chat', Share: 'share', Test: 'test' },
    ChatContainer: defineComponent({
      name: 'ChatContainer',
      props: {
        getSideRenderComponent: { type: Function, default: undefined },
        getSideTabRenderComponent: { type: Function, default: undefined },
        onCustomTabChange: { type: Function, default: undefined },
      },
      setup(props) {
        chatContainerPropsRef.current = props;
        return () => h('div', { class: 'chat-container-stub' });
      },
    }),
    MessageRender: defineComponent({ name: 'MessageRender', template: '<motion />' }),
    ChatInput: defineComponent({ name: 'ChatInput', template: '<motion />' }),
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

vi.mock('../composables/use-message-sender', () => ({
  useMessageSender: () => ({
    userInput: ref(''),
    cite: ref(''),
    handleUpdateModelValue: vi.fn(),
    doSendMessage: vi.fn(),
    handleSendMessage: vi.fn(),
    handleUpload: vi.fn(),
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
    messages: ref([]),
    isMessagesLoading: ref(false),
    isGenerating: ref(false),
    currentSession: ref(null),
    isWelcomeState: ref(true),
    openingRemark: ref(''),
    effectiveResources: ref([]),
    effectivePrompts: ref([]),
    effectiveSupportUpload: ref(true),
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

describe('ChatBot 侧栏渲染 props 透传', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatHelperRef.value = createMockChatHelper();
    chatHelperRef.value.message.getFlowAgentTaskNodeInfo = vi.fn().mockResolvedValue({ node: 'default' });
  });

  it('应将 getSideRenderComponent 与 getSideTabRenderComponent 传给 ChatContainer', () => {
    const getSideRenderComponent = vi.fn();
    const getSideTabRenderComponent = vi.fn();

    mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
        getSideRenderComponent,
        getSideTabRenderComponent,
      },
    });

    expect(chatContainerPropsRef.current.getSideRenderComponent).toBe(getSideRenderComponent);
    expect(chatContainerPropsRef.current.getSideTabRenderComponent).toBe(getSideTabRenderComponent);
  });

  it('onCustomTabChange 应优先于默认节点详情拉取', async () => {
    const onCustomTabChange = vi.fn().mockResolvedValue({ node: 'custom' });

    mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
        onCustomTabChange,
      },
    });

    const tab = {
      label: 'node',
      name: '1|n1|Node',
      data: {
        props: { task_id: 1, node_id: 'n1' },
      },
    } as CustomBkFlowTab;

    const onChange = chatContainerPropsRef.current.onCustomTabChange as (t: CustomBkFlowTab) => Promise<unknown>;
    await onChange(tab);

    expect(onCustomTabChange).toHaveBeenCalledWith(tab);
    expect(chatHelperRef.value.message.getFlowAgentTaskNodeInfo).not.toHaveBeenCalled();
  });

  it('未传 onCustomTabChange 时应使用默认 getFlowAgentTaskNodeInfo', async () => {
    mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
      },
    });

    const tab = {
      label: 'node',
      name: '1|n1|Node',
      data: {
        props: { task_id: 1, node_id: 'n1' },
      },
    } as CustomBkFlowTab;

    const onChange = chatContainerPropsRef.current.onCustomTabChange as (t: CustomBkFlowTab) => Promise<unknown>;
    await onChange(tab);

    expect(chatHelperRef.value.message.getFlowAgentTaskNodeInfo).toHaveBeenCalledWith(1, 'n1');
  });
});
