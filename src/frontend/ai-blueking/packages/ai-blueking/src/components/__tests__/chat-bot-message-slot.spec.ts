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
import { defineComponent, h, nextTick, ref } from 'vue';

import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChatMessageSlotProps } from '../types';
import { createMockChatHelper } from '../../__tests__/helpers';
import ChatBot from '../chat-bot.vue';

type SlotMessage = { content?: unknown; id?: string; role?: string };

type RenderedMessage = {
  message?: SlotMessage;
  messageTools?: Array<{ id?: string; name?: string }>;
  onAction?: (tool: { id: string }) => unknown;
  onInputConfirm?: (content: string, docSchema: unknown) => unknown;
  onInterruptResume?: () => unknown;
  onShortcutConfirm?: (formModel: Record<string, unknown>) => unknown;
  tippyOptions?: { appendTo?: unknown; placement?: string };
};

const chatHelperRef = ref(createMockChatHelper());
const handleUserAction = vi.fn();
const handleUserInputConfirm = vi.fn();
const handleUserShortcutConfirm = vi.fn();
const effectiveUserMessageTools = ref<Array<{ id: string; name: string }>>([{ id: 'chatbot-edit', name: '编辑' }]);
const renderedMessage: { current?: RenderedMessage; setupCount: number } = { setupCount: 0 };
const containerRenderTick = ref(0);
const forwardedOnAction = vi.fn();
const forwardedOnInputConfirm = vi.fn();
const forwardedOnShortcutConfirm = vi.fn();
const forwardedOnInterruptResume = vi.fn();
const forwardedScope = {
  message: { id: 'user-1', role: 'user', content: 'hello user' },
  messageTools: [{ id: 'from-container', name: '复制' }],
  messageToolsStatus: 'disabled',
  onAction: forwardedOnAction,
  onInputConfirm: forwardedOnInputConfirm,
  onInterruptResume: forwardedOnInterruptResume,
  onShortcutConfirm: forwardedOnShortcutConfirm,
  tippyOptions: { placement: 'bottom' as const },
};

vi.mock('@blueking/chat-x', async importOriginal => {
  const actual = await importOriginal<typeof import('@blueking/chat-x')>();
  return {
    ...actual,
    ChatContainer: defineComponent({
      name: 'ChatContainer',
      setup(_props, { slots }) {
        return () =>
          h('div', { class: 'chat-container-stub', 'data-tick': containerRenderTick.value }, [
            slots.message?.(forwardedScope),
            slots.codeHeader?.({}),
          ]);
      },
    }),
    MessageRender: defineComponent({
      name: 'MessageRender',
      props: {
        message: { type: Object, default: undefined },
        messageTools: { type: Array, default: undefined },
        messageToolsStatus: { type: String, default: undefined },
        onAction: { type: Function, default: undefined },
        onInputConfirm: { type: Function, default: undefined },
        onInterruptResume: { type: Function, default: undefined },
        onShortcutConfirm: { type: Function, default: undefined },
        tippyOptions: { type: Object, default: undefined },
      },
      setup(props, { slots }) {
        renderedMessage.setupCount += 1;
        renderedMessage.current = {
          message: props.message as SlotMessage | undefined,
          messageTools: props.messageTools as RenderedMessage['messageTools'],
          onAction: props.onAction as RenderedMessage['onAction'],
          onInputConfirm: props.onInputConfirm as RenderedMessage['onInputConfirm'],
          onInterruptResume: props.onInterruptResume as RenderedMessage['onInterruptResume'],
          onShortcutConfirm: props.onShortcutConfirm as RenderedMessage['onShortcutConfirm'],
          tippyOptions: props.tippyOptions as RenderedMessage['tippyOptions'],
        };
        const message = props.message as SlotMessage | undefined;
        const content = typeof message?.content === 'string' ? message.content : '';
        return () =>
          h(
            'div',
            { class: 'message-render-stub', 'data-role': message?.role },
            [content, ...(slots.codeHeader?.({ language: 'ts', token: [] }) ?? [])],
          );
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
    handleInterruptResume: vi.fn(),
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
    handleDeleteFile: vi.fn(),
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
    effectiveUserMessageTools,
    messages: ref([{ id: 'msg-1', role: 'assistant', content: 'hello' }]),
    isMessagesLoading: ref(false),
    isGenerating: ref(false),
    currentSession: ref(null),
    isWelcomeState: ref(false),
    openingRemark: ref(''),
    effectiveMenuSources: ref([]),
    effectiveSupportUpload: ref(false),
    chatbotStyle: ref({}),
    filteredShortcuts: ref([]),
  }),
}));

vi.mock('../composables/use-tool-actions', () => ({
  useToolActions: () => ({
    handleAgentAction: vi.fn(),
    handleAgentFeedback: vi.fn(),
    handleUserAction,
    handleUserInputConfirm,
    handleUserShortcutConfirm,
    handleStopStreaming: vi.fn(),
  }),
}));

vi.mock('../composables/use-share-selection', () => ({
  useShareSelection: () => ({
    handleConfirmShare: vi.fn(),
  }),
}));

const mountProps = {
  url: 'https://example.com/api/',
  messageToolsTippyOptions: { placement: 'top' as const },
};

describe('ChatBot message slot', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    renderedMessage.current = undefined;
    renderedMessage.setupCount = 0;
  });

  it('父组件重渲染时默认消息不会被重新挂载', async () => {
    mount(ChatBot, { props: mountProps });
    expect(renderedMessage.setupCount).toBe(1);

    containerRenderTick.value += 1;
    await nextTick();

    expect(renderedMessage.setupCount).toBe(1);
  });

  it('未传 #message 时仍渲染默认用户消息，并绑定 ChatBot 自己的工具回调', async () => {
    const wrapper = mount(ChatBot, {
      props: mountProps,
    });

    expect(wrapper.find('.message-render-stub').exists()).toBe(true);
    expect(wrapper.find('.message-render-stub').text()).toContain('hello user');
    expect(renderedMessage.current?.messageTools).toEqual(effectiveUserMessageTools.value);
    expect(renderedMessage.current?.tippyOptions).toMatchObject({ placement: 'top' });
    expect(renderedMessage.current?.onInterruptResume).toBe(forwardedOnInterruptResume);

    const tool = { id: 'edit' };
    await renderedMessage.current?.onAction?.(tool);
    expect(handleUserAction).toHaveBeenCalledWith(tool, forwardedScope.message);

    await renderedMessage.current?.onInputConfirm?.('edited', { type: 'doc' });
    expect(handleUserInputConfirm).toHaveBeenCalledWith(forwardedScope.message, 'edited', { type: 'doc' });

    await renderedMessage.current?.onShortcutConfirm?.({ field: 'value' });
    expect(handleUserShortcutConfirm).toHaveBeenCalledWith(forwardedScope.message, { field: 'value' });
  });

  it('#message 作用域包含工具字段与 renderDefault，且 renderDefault 可渲染默认用户消息', async () => {
    let captured: ChatMessageSlotProps | undefined;
    const wrapper = mount(ChatBot, {
      props: mountProps,
      slots: {
        codeHeader: () => h('em', { class: 'host-code-header' }, 'lang'),
        message: (slotProps: ChatMessageSlotProps) => {
          captured = slotProps;
          return h('div', { class: 'host-message' }, [slotProps.renderDefault()]);
        },
      },
    });

    if (!captured) {
      throw new Error('message slot props missing');
    }

    expect(captured.message).toMatchObject({ id: 'user-1', role: 'user', content: 'hello user' });
    expect(captured.messageTools).toEqual(forwardedScope.messageTools);
    expect(captured.messageToolsStatus).toBe('disabled');
    expect(captured.tippyOptions).toEqual({ placement: 'bottom' });
    expect(captured.onInterruptResume).toBe(forwardedOnInterruptResume);
    expect(captured.onAction).toBe(forwardedOnAction);
    expect(captured.onInputConfirm).toBe(forwardedOnInputConfirm);
    expect(captured.onShortcutConfirm).toBe(forwardedOnShortcutConfirm);
    expect(captured.renderDefault).toEqual(expect.any(Function));

    const tool = { id: 'cite' };
    await captured.onAction?.(tool);
    expect(forwardedOnAction).toHaveBeenCalledWith(tool);
    expect(handleUserAction).not.toHaveBeenCalled();

    expect(wrapper.find('.host-message').exists()).toBe(true);
    expect(wrapper.find('.message-render-stub').text()).toContain('hello user');
    expect(wrapper.find('.host-code-header').exists()).toBe(true);
    expect(renderedMessage.current?.messageTools).toEqual(effectiveUserMessageTools.value);
    expect(renderedMessage.current?.tippyOptions).toMatchObject({ placement: 'top' });

    await renderedMessage.current?.onAction?.(tool);
    expect(handleUserAction).toHaveBeenCalledWith(tool, forwardedScope.message);
  });
});
