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
import { defineComponent, h, ref } from 'vue';

import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMockChatHelper } from '../../__tests__/helpers';
import ChatBot from '../chat-bot.vue';

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
        asideCollapsed: { type: Boolean, default: undefined },
        placement: { type: String, default: undefined },
        timezone: { type: String, default: undefined },
        getSideRenderComponent: { type: Function, default: undefined },
        getSideTabRenderComponent: { type: Function, default: undefined },
        onCustomTabChange: { type: Function, default: undefined },
      },
      setup(props) {
        chatContainerPropsRef.current = props;
        return () => h('div', { class: 'chat-container-stub' });
      },
    }),
    MessageRender: defineComponent({ name: 'MessageRender', template: '<div />' }),
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
    effectiveMessageTools: ref(undefined),
    effectiveUpdateTools: ref(undefined),
    effectiveUserMessageTools: ref(undefined),
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

describe('ChatBot asideCollapsed', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatHelperRef.value = createMockChatHelper();
    chatContainerPropsRef.current = {};
  });

  it('should not pass placement to ChatContainer', () => {
    mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
      },
    });

    expect(chatContainerPropsRef.current.placement).toBeUndefined();
  });

  it('unbound asideCollapsed should default ChatContainer to collapsed', () => {
    mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
      },
    });

    expect(chatContainerPropsRef.current.asideCollapsed).toBe(true);
  });

  it('should forward bound asideCollapsed to ChatContainer', async () => {
    const wrapper = mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
        asideCollapsed: true,
      },
    });

    expect(chatContainerPropsRef.current.asideCollapsed).toBe(true);

    await wrapper.setProps({ asideCollapsed: false });
    expect(chatContainerPropsRef.current.asideCollapsed).toBe(false);
  });
});

describe('ChatBot timezone', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatHelperRef.value = createMockChatHelper();
    chatContainerPropsRef.current = {};
  });

  it('未传 timezone 时应保持 undefined（与 ChatContainer 一致，按浏览器时区展示）', () => {
    mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
      },
    });

    expect(chatContainerPropsRef.current.timezone).toBeUndefined();
  });

  it('应将 timezone 透传给 ChatContainer', async () => {
    const wrapper = mount(ChatBot, {
      props: {
        url: 'https://api.example.com/',
        timezone: 'Asia/Shanghai',
      },
    });

    expect(chatContainerPropsRef.current.timezone).toBe('Asia/Shanghai');

    await wrapper.setProps({ timezone: 'UTC' });
    expect(chatContainerPropsRef.current.timezone).toBe('UTC');
  });
});
