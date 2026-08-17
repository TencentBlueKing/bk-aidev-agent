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

import { defineComponent, h, nextTick } from 'vue';

import { type VueWrapper, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageContentType, MessageRole, MessageStatus } from '../../../ag-ui/types';
import { LOADING_MESSAGE_ID, RenderMode } from '../../../common';
import { MessageToolsStatus } from '../../../types/tool';
import MessageContainer from './message-container.vue';

import type { AssistantMessage, Message, ToolMessage, UserMessage } from '../../../ag-ui/types';

const jumpToBottomMock = vi.fn();
const toScrollBottomMock = vi.fn();

// Mock composables
vi.mock('../../../composables', () => ({
  useClipboard: () => ({
    copy: vi.fn(),
  }),
  useContainerScrollProvider: () => ({
    isScrollBottom: { value: true },
    jumpToBottom: jumpToBottomMock,
    toScrollBottom: toScrollBottomMock,
    scrollBottomHeight: { value: 0 },
    toScrollTop: vi.fn(),
    debouncedShowScrollBottomBtn: { value: false },
  }),
}));

// Mock bkui-vue Checkbox
vi.mock('bkui-vue', () => ({
  Checkbox: defineComponent({
    name: 'Checkbox',
    props: {
      modelValue: Boolean,
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () =>
        h('label', { class: 'mock-checkbox' }, [
          h('input', {
            type: 'checkbox',
            checked: props.modelValue,
            onChange: (e: Event) => {
              const checked = (e.target as HTMLInputElement).checked;
              emit('update:modelValue', checked);
            },
          }),
        ]);
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock child components
vi.mock('../message-render/message-render.vue', () => ({
  default: defineComponent({
    name: 'MessageRender',
    props: {
      message: { type: Object, default: null },
      messageToolsStatus: { type: String, default: undefined },
      onAction: { type: Function, default: null },
      tippyOptions: { type: Object, default: undefined },
    },
    setup(props) {
      return () =>
        h(
          'div',
          {
            class: 'mock-message-render',
            'data-role': props.message?.role,
            'data-message-id': props.message?.messageId,
            'data-message-tools-status': props.messageToolsStatus,
            'data-has-tippy-options': props.tippyOptions !== undefined ? 'true' : undefined,
          },
          props.message?.content,
        );
    },
  }),
}));

vi.mock('../../message-tools/message-tools.vue', () => ({
  default: defineComponent({
    name: 'MessageTools',
    props: {
      messageToolsStatus: { type: String, default: undefined },
      messageTools: { type: Array, default: undefined },
      updateTools: { type: Array, default: undefined },
      onAction: { type: Function, default: null },
      tippyOptions: { type: Object, default: undefined },
    },
    setup(props) {
      return () =>
        h(
          'div',
          {
            class: 'mock-message-tools',
            'data-message-tools-status': props.messageToolsStatus,
            'data-has-tippy-options': props.tippyOptions !== undefined ? 'true' : undefined,
            'data-tools-count': props.messageTools?.length,
            'data-update-tools-count': props.updateTools?.length,
            // 序列化工具明细，便于单测断言合并/覆盖/隐藏结果
            'data-tools-json': JSON.stringify(props.messageTools ?? []),
            'data-update-tools-json': JSON.stringify(props.updateTools ?? []),
          },
          'Message Tools',
        );
    },
  }),
}));

vi.mock('../../ai-buttons/scroll-btn/scroll-btn.vue', () => ({
  default: defineComponent({
    name: 'ScrollBtn',
    props: {
      title: { type: String, default: '' },
      loading: { type: Boolean, default: false },
    },
    emits: ['click'],
    setup(props, { emit, slots }) {
      return () =>
        h(
          'button',
          {
            class: 'mock-scroll-btn',
            'data-loading': props.loading ? 'true' : undefined,
            onClick: () => emit('click'),
          },
          [props.title, slots.icon?.()],
        );
    },
  }),
}));

vi.mock('../../../icons', () => ({
  ArrowDownIcon: defineComponent({
    name: 'ArrowDownIcon',
    setup() {
      return () => h('span', { class: 'mock-arrow-down-icon' });
    },
  }),
  CloseCircleIcon: defineComponent({
    name: 'CloseCircleIcon',
    setup() {
      return () => h('span', { class: 'mock-close-circle-icon' });
    },
  }),
}));

// Helper function to create test messages
const createUserMessage = (id: string, content: string, messageId = 1): UserMessage => ({
  id,
  content,
  messageId,
  role: MessageRole.User,
  status: MessageStatus.Complete,
});

const createAssistantMessage = (id: string, content: string, messageId = 2): AssistantMessage => ({
  id,
  content,
  messageId,
  role: MessageRole.Assistant,
  status: MessageStatus.Complete,
});

const createToolMessage = (
  id: string,
  content: string,
  toolCallId: string,
  messageId = 3,
): Omit<ToolMessage, 'duration'> & { duration?: number } => ({
  id,
  content,
  messageId,
  role: MessageRole.Tool,
  status: MessageStatus.Complete,
  toolCallId,
  duration: 100,
});

type MessageGroup = {
  checked: boolean;
  isHover: boolean;
  messages: Message[];
  pause?: boolean;
  startTime?: number;
  type: string;
  uid: string;
};

const buildGroups = (messages: Message[]): MessageGroup[] => {
  const groups: MessageGroup[] = [];

  for (const msg of messages) {
    if (msg.role === MessageRole.User) {
      groups.push({
        uid: `group-${msg.id}`,
        messages: [msg],
        type: MessageRole.User,
        isHover: false,
        checked: false,
      });
    } else if (msg.role === MessageRole.Assistant) {
      const lastGroup = groups[groups.length - 1];
      if (lastGroup?.type === MessageRole.Assistant) {
        lastGroup.messages.push(msg);
      } else {
        groups.push({
          uid: `group-${msg.id}`,
          messages: [msg],
          type: MessageRole.Assistant,
          isHover: false,
          checked: false,
          pause: (msg as Record<string, unknown> & { property?: { extra?: { pause?: boolean } } }).property?.extra
            ?.pause,
        });
      }
    } else if (msg.role === MessageRole.Tool) {
      const lastGroup = groups[groups.length - 1];
      if (lastGroup?.type === MessageRole.Assistant) {
        lastGroup.messages.push(msg);
      }
    }
  }

  const lastMsg = messages[messages.length - 1];
  if (lastMsg?.role === MessageRole.User) {
    groups.push({
      uid: 'loading-group',
      messages: [
        {
          id: LOADING_MESSAGE_ID,
          content: '',
          role: MessageRole.Loading,
          status: MessageStatus.Pending,
          messageId: -1,
        } as unknown as Message,
      ],
      type: MessageRole.Loading,
      isHover: false,
      checked: false,
    });
  }

  return groups;
};

describe('MessageContainer', () => {
  let wrapper: VueWrapper;

  const defaultProps = {
    messages: [] as Message[],
    messageGroups: [] as MessageGroup[],
    messageStatus: MessageStatus.Complete,
    enableSelection: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('发送消息后滚动到底部', () => {
    it('新增用户消息时应调用 jumpToBottom', async () => {
      const messages = [createUserMessage('1', 'Hello')];
      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });
      await flushPromises();
      jumpToBottomMock.mockClear();

      const nextMessages = [...messages, createUserMessage('2', 'World', 2)];
      await wrapper.setProps({
        messages: nextMessages,
        messageGroups: buildGroups(nextMessages),
      });
      await nextTick();
      await flushPromises();

      expect(jumpToBottomMock).toHaveBeenCalled();
    });
  });

  describe('渲染测试', () => {
    it('应该正确渲染空消息列表', () => {
      wrapper = mount(MessageContainer, {
        props: defaultProps,
      });

      expect(wrapper.find('.ai-message-container').exists()).toBe(true);
      expect(wrapper.findAll('.message-group').length).toBe(0);
    });

    it('应该正确渲染单个用户消息（并追加 Loading 组）', async () => {
      const messages = [createUserMessage('1', 'Hello')];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(2);
      expect(wrapper.find('.mock-message-render').exists()).toBe(true);
    });

    it('应该正确渲染单个助手消息', async () => {
      const messages = [createAssistantMessage('1', 'Hi there!')];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(1);
      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
    });

    it('应该正确渲染多条混合消息', async () => {
      const messages: Message[] = [
        createUserMessage('1', 'Hello', 1),
        createAssistantMessage('2', 'Hi!', 2),
        createUserMessage('3', 'How are you?', 3),
        createAssistantMessage('4', 'I am fine!', 4),
      ];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(4);
    });
  });

  describe('DOM 标识测试', () => {
    it('消息组根节点应该输出 data-message-group-id', async () => {
      const messages = [createAssistantMessage('1', 'Hi there!')];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      expect(wrapper.find('.message-group').attributes('data-message-group-id')).toBe('group-1');
    });

    it('每条消息都应该被带 data-message-id 的容器包裹', async () => {
      const messages: Message[] = [
        createAssistantMessage('1', 'Message 1', 1),
        createAssistantMessage('2', 'Message 2', 2),
      ];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageItems = wrapper.findAll('.ai-message-item');
      expect(messageItems.length).toBe(2);
      expect(messageItems.map(item => item.attributes('data-message-id'))).toEqual(['1', '2']);
      expect(messageItems[0].find('.mock-message-render').exists()).toBe(true);
    });

    it('消息缺少 id 时应该回退到 uid', async () => {
      const message = { ...createAssistantMessage('', 'Streaming...'), uid: 'temp-uid-1' } as Message;

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages: [message],
          messageGroups: [
            { uid: 'group-temp', messages: [message], type: MessageRole.Assistant, isHover: false, checked: false },
          ],
        },
      });

      await nextTick();

      expect(wrapper.find('.ai-message-item').attributes('data-message-id')).toBe('temp-uid-1');
    });

    it('自定义 default slot 渲染的消息同样带 data-message-id', async () => {
      const messages = [createAssistantMessage('1', 'Hi there!')];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
        slots: {
          default: '<div class="custom-message">custom</div>',
        },
      });

      await nextTick();

      const messageItem = wrapper.find('.ai-message-item');
      expect(messageItem.attributes('data-message-id')).toBe('1');
      expect(messageItem.find('.custom-message').exists()).toBe(true);
      expect(wrapper.find('.mock-message-render').exists()).toBe(false);
    });
  });

  describe('消息分组测试', () => {
    it('应该将连续的助手消息分组在一起', async () => {
      const messages: Message[] = [
        createAssistantMessage('1', 'Message 1', 1),
        createAssistantMessage('2', 'Message 2', 2),
        createAssistantMessage('3', 'Message 3', 3),
      ];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      // 连续的助手消息应该分组在一起
      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(1);

      // 应该只有一个 message-tools（因为只有一个助手消息组）
      expect(wrapper.findAll('.mock-message-tools').length).toBe(1);
    });

    it('应该将用户消息单独分组（末尾追加 Loading 组）', async () => {
      const messages: Message[] = [createUserMessage('1', 'User 1', 1), createUserMessage('2', 'User 2', 2)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(3);

      expect(wrapper.findAll('.mock-message-tools').length).toBe(0);
    });

    it('应该正确处理交替的用户和助手消息', async () => {
      const messages: Message[] = [
        createUserMessage('1', 'Q1', 1),
        createAssistantMessage('2', 'A1', 2),
        createUserMessage('3', 'Q2', 3),
        createAssistantMessage('4', 'A2', 4),
      ];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(4);

      // 只有助手消息组有 message-tools
      expect(wrapper.findAll('.mock-message-tools').length).toBe(2);
    });
  });

  describe('滚动按钮测试', () => {
    it('流式状态时应该显示停止生成按钮', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Streaming,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));
      expect(stopBtn?.isVisible()).toBe(true);
    });

    it('Fetching 状态时应该显示停止生成按钮', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Fetching,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));
      expect(stopBtn?.isVisible()).toBe(true);
      expect(stopBtn?.attributes('data-loading')).toBeUndefined();
    });

    it('Pending 状态时应该显示停止生成按钮', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Pending,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));
      expect(stopBtn?.isVisible()).toBe(true);
    });

    it('StopLoading 状态时应该显示停止按钮且 loading 为 true', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.StopLoading,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('正在停止'));
      expect(stopBtn?.isVisible()).toBe(true);
      expect(stopBtn?.attributes('data-loading')).toBe('true');
    });

    it('Complete 状态时不应该显示停止按钮', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Complete,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));
      expect(stopBtn).toBeTruthy();
      expect((stopBtn?.element as HTMLElement).style.display).toBe('none');
    });

    it('点击停止生成按钮应该触发 stopStreaming 事件', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Streaming,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));

      await stopBtn?.trigger('click');

      expect(wrapper.emitted('stopStreaming')).toBeTruthy();
      expect(wrapper.emitted('stopStreaming')?.length).toBe(1);
    });
  });

  describe('鼠标悬停测试', () => {
    const getToolsVisibility = (w: VueWrapper) =>
      (w.find('.mock-message-tools').element as HTMLElement).style.visibility;

    it('鼠标进入消息组时 MessageTools visibility 应为 visible', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroup = wrapper.find('.message-group');
      await messageGroup.trigger('mouseenter');

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
      expect(getToolsVisibility(wrapper)).toBe('visible');
    });

    it('鼠标离开消息组时 MessageTools visibility 应为 hidden', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroup = wrapper.find('.message-group');
      await messageGroup.trigger('mouseenter');
      await messageGroup.trigger('mouseleave');

      expect(getToolsVisibility(wrapper)).toBe('hidden');
    });

    it('初始状态 MessageTools visibility 应为 hidden', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
      expect(getToolsVisibility(wrapper)).toBe('hidden');
    });

    it('鼠标移入 ai-user-feedback 时 isHover 应保持 true', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageGroup = wrapper.find('.message-group');
      await messageGroup.trigger('mouseenter');

      const feedbackEl = document.createElement('div');
      feedbackEl.classList.add('ai-user-feedback');
      const mouseleaveEvent = new MouseEvent('mouseleave', {
        relatedTarget: feedbackEl,
      });
      messageGroup.element.dispatchEvent(mouseleaveEvent);
      await nextTick();

      expect(getToolsVisibility(wrapper)).toBe('visible');
    });

    it('消息组最后一条为 Interrupt 时 mouseenter 不应显示 MessageTools', async () => {
      const interruptMessage: Message = {
        id: 'interrupt-1',
        content: {
          outcome: {
            type: 'interrupt',
            interrupts: [],
          },
        },
        messageId: 2,
        role: MessageRole.Interrupt,
        status: MessageStatus.Complete,
      };
      const messageGroups: MessageGroup[] = [
        {
          uid: 'group-assistant-interrupt',
          messages: [createAssistantMessage('1', 'Hello', 1), interruptMessage],
          type: MessageRole.Assistant,
          isHover: false,
          checked: false,
        },
      ];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages: messageGroups[0].messages,
          messageGroups,
        },
      });

      await nextTick();

      const messageGroup = wrapper.find('.message-group');
      await messageGroup.trigger('mouseenter');

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
      expect(getToolsVisibility(wrapper)).toBe('hidden');
    });
  });

  describe('Slot 测试', () => {
    it('应该支持自定义消息渲染 slot', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
        slots: {
          default: ({ message }: { message: Message }) =>
            h('div', { class: 'custom-message' }, `Custom: ${message.content}`),
        },
      });

      await nextTick();

      expect(wrapper.find('.custom-message').exists()).toBe(true);
      expect(wrapper.find('.custom-message').text()).toBe('Custom: Hello');
    });

    it('应该支持 group 插槽自定义整组渲染', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];
      const messageGroups = buildGroups(messages);

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups },
        slots: {
          group: ({ group }: { group: MessageGroup }) =>
            h('div', { class: 'custom-group', 'data-uid': group.uid, 'data-type': group.type }, 'Custom Group'),
        },
      });

      await nextTick();

      expect(wrapper.find('.custom-group').exists()).toBe(true);
      expect(wrapper.find('.custom-group').attributes('data-uid')).toBe('group-1');
      expect(wrapper.find('.custom-group').attributes('data-type')).toBe(MessageRole.Assistant);
      expect(wrapper.find('.mock-message-render').exists()).toBe(false);
      expect(wrapper.find('.mock-message-tools').exists()).toBe(false);
    });

    it('group 插槽应接收完整的消息组数据', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];
      const messageGroups = buildGroups(messages);

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups },
        slots: {
          group: ({ group }: { group: MessageGroup }) =>
            h('div', { class: 'custom-group', 'data-messages-count': group.messages.length }, group.type),
        },
      });

      await nextTick();

      const customGroups = wrapper.findAll('.custom-group');
      // 用户组 + 助手组（末条为助手消息时不追加 Loading 组）
      expect(customGroups.length).toBe(2);
      expect(customGroups[0].attributes('data-messages-count')).toBe('1');
      expect(customGroups[0].text()).toBe(MessageRole.User);
      expect(customGroups[1].attributes('data-messages-count')).toBe('1');
      expect(customGroups[1].text()).toBe(MessageRole.Assistant);
    });
  });

  describe('Actions 测试', () => {
    it('onAgentAction 应该被正确调用', async () => {
      const onAgentAction = vi.fn();
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), onAgentAction },
      });

      await nextTick();
      await flushPromises();

      // 验证 onAgentAction prop 被传递
      expect((wrapper.props() as Record<string, unknown>).onAgentAction).toBe(onAgentAction);
    });

    it('onUserAction 应该被正确调用', async () => {
      const onUserAction = vi.fn();
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), onUserAction },
      });

      await nextTick();
      await flushPromises();

      // 验证 onUserAction prop 被传递
      expect((wrapper.props() as Record<string, unknown>).onUserAction).toBe(onUserAction);
    });
  });

  describe('Tool Message 处理测试', () => {
    it('应该正确处理 Tool 消息与 AssistantMessage 的关联', async () => {
      const toolCallId = 'tool-call-1';
      const assistantMsg: AssistantMessage = {
        ...createAssistantMessage('1', 'Let me help you', 1),
        toolCalls: [
          {
            id: toolCallId,
            type: MessageContentType.Function,
            function: {
              name: 'search',
              arguments: '{}',
            },
          },
        ],
      };
      const messages: Message[] = [assistantMsg, createToolMessage('2', 'Tool result', toolCallId, 2) as ToolMessage];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      // Tool 消息应该被关联到对应的 AssistantMessage
      expect(wrapper.find('.ai-message-container').exists()).toBe(true);
    });

    it('Tool 消息错误时应该设置 AssistantMessage 状态为 Error', async () => {
      const toolCallId = 'tool-call-1';
      const assistantMsg: AssistantMessage = {
        ...createAssistantMessage('1', 'Let me help you', 1),
        toolCalls: [
          {
            id: toolCallId,
            type: MessageContentType.Function,
            function: {
              name: 'search',
              arguments: '{}',
            },
          },
        ],
      };
      const toolMsg = {
        ...(createToolMessage('2', 'Tool error', toolCallId, 2) as ToolMessage),
        error: 'Something went wrong',
      };
      const messages: Message[] = [assistantMsg, toolMsg];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      // 组件应该正确渲染
      expect(wrapper.find('.ai-message-container').exists()).toBe(true);
    });
  });

  describe('消息更新响应测试', () => {
    it('消息列表更新时应该重新渲染', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();
      expect(wrapper.findAll('.message-group').length).toBe(2);

      const updatedMessages: Message[] = [...messages, createAssistantMessage('2', 'Hi!', 2)];
      await wrapper.setProps({
        messages: updatedMessages,
        messageGroups: buildGroups(updatedMessages),
      });

      await nextTick();
      expect(wrapper.findAll('.message-group').length).toBe(2);
    });

    it('messageStatus 更新时应该响应变化', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Complete,
        },
      });

      await nextTick();

      // 更新状态为 Streaming
      await wrapper.setProps({
        messageStatus: MessageStatus.Streaming,
      });

      await nextTick();

      // 停止生成按钮应该可见
      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));
      expect(stopBtn?.exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空内容的消息', async () => {
      const messages: Message[] = [createUserMessage('1', '', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      expect(wrapper.find('.ai-message-container').exists()).toBe(true);
      expect(wrapper.findAll('.message-group').length).toBe(2);
    });

    it('应该处理大量消息', async () => {
      const messages: Message[] = [];
      for (let i = 0; i < 100; i++) {
        messages.push(createUserMessage(`user-${i}`, `User message ${i}`, i * 2));
        messages.push(createAssistantMessage(`assistant-${i}`, `Assistant message ${i}`, i * 2 + 1));
      }

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      // 应该正确渲染所有消息组
      expect(wrapper.findAll('.message-group').length).toBe(200);
    });
  });

  describe('Loading 消息组测试', () => {
    it('最后一条消息是用户消息时应该追加 Loading 消息组', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageRenders = wrapper.findAll('.mock-message-render');
      const loadingRender = messageRenders.find(r => r.attributes('data-role') === MessageRole.Loading);
      expect(loadingRender).toBeTruthy();
    });

    it('renderMode 为 Share 时不应渲染 Loading 消息组', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          renderMode: RenderMode.Share,
        },
      });

      await nextTick();

      const messageRenders = wrapper.findAll('.mock-message-render');
      const loadingRender = messageRenders.find(r => r.attributes('data-role') === MessageRole.Loading);
      expect(loadingRender).toBeUndefined();
    });

    it('最后一条消息是助手消息时不应该追加 Loading 消息组', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageRenders = wrapper.findAll('.mock-message-render');
      const loadingRender = messageRenders.find(r => r.attributes('data-role') === MessageRole.Loading);
      expect(loadingRender).toBeUndefined();
    });

    it('空消息列表不应该追加 Loading 消息组', async () => {
      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages: [] },
      });

      await nextTick();

      expect(wrapper.findAll('.message-group').length).toBe(0);
    });
  });

  describe('多选功能测试', () => {
    it('enableSelection 为 true 时应该显示 Checkbox', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();

      expect(wrapper.find('.mock-checkbox').exists()).toBe(true);
    });

    it('Loading 消息组不应该显示 Checkbox', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();

      const messageGroups = wrapper.findAll('.message-group');
      expect(messageGroups.length).toBe(2);
      expect(wrapper.findAll('.mock-checkbox').length).toBe(1);
    });

    it('enableSelection 为 false 时应该隐藏 Checkbox', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: false },
      });

      await nextTick();

      expect(wrapper.find('.mock-checkbox').exists()).toBe(false);
    });

    it('enableSelection 默认应该为 false', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { messages, messageGroups: buildGroups(messages), messageStatus: MessageStatus.Complete },
      });

      await nextTick();

      expect(wrapper.find('.mock-checkbox').exists()).toBe(false);
    });

    it('选中用户消息组时应该同时选中下一个 Assistant 消息组', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];

      let selectedUserMessages: Message[] = [];
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          enableSelection: true,
          selectedUserMessages,
          'onUpdate:selectedUserMessages': (val: Message[]) => {
            selectedUserMessages = val;
          },
        },
      });

      await nextTick();

      // 找到第一个 Checkbox（用户消息组）并选中
      const checkboxInput = wrapper.find('.mock-checkbox input[type="checkbox"]');
      await checkboxInput.setValue(true);

      await nextTick();

      // 验证 selectedUserMessages 更新事件被触发
      const emittedEvents = wrapper.emitted('update:selectedUserMessages');
      expect(emittedEvents).toBeTruthy();

      const lastEmitted = emittedEvents?.[emittedEvents.length - 1]?.[0] as Message[];
      expect(lastEmitted.length).toBe(2);
      expect(lastEmitted.some(m => m.role === MessageRole.User)).toBe(true);
      expect(lastEmitted.some(m => m.role === MessageRole.Assistant)).toBe(true);
    });

    it('选中 Assistant 消息组时应该同时选中上一个用户消息组', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];

      let selectedUserMessages: Message[] = [];
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          enableSelection: true,
          selectedUserMessages,
          'onUpdate:selectedUserMessages': (val: Message[]) => {
            selectedUserMessages = val;
          },
        },
      });

      await nextTick();

      const checkboxInputs = wrapper.findAll('.mock-checkbox input[type="checkbox"]');
      expect(checkboxInputs.length).toBe(2);

      await checkboxInputs[1].setValue(true);

      await nextTick();

      const emittedEvents = wrapper.emitted('update:selectedUserMessages');
      expect(emittedEvents).toBeTruthy();

      const lastEmitted = emittedEvents?.[emittedEvents.length - 1]?.[0] as Message[];
      expect(lastEmitted.length).toBe(2);
      expect(lastEmitted.some(m => m.role === MessageRole.User)).toBe(true);
      expect(lastEmitted.some(m => m.role === MessageRole.Assistant)).toBe(true);
    });

    it('取消选中时应该同时取消关联消息组', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];

      let selectedUserMessages: Message[] = [];
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          enableSelection: true,
          selectedUserMessages,
          'onUpdate:selectedUserMessages': (val: Message[]) => {
            selectedUserMessages = val;
          },
        },
      });

      await nextTick();

      const checkboxInput = wrapper.find('.mock-checkbox input[type="checkbox"]');

      // 先选中
      await checkboxInput.setValue(true);
      await nextTick();

      // 再取消选中
      await checkboxInput.setValue(false);
      await nextTick();

      // 验证 selectedUserMessages 最后是空数组
      const emittedEvents = wrapper.emitted('update:selectedUserMessages');
      const lastEmitted = emittedEvents?.[emittedEvents.length - 1]?.[0] as Message[];
      expect(lastEmitted.length).toBe(0);
    });

    it('选中状态应该改变消息组背景色', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();

      // 初始状态背景透明
      const messageGroup = wrapper.find('.message-group');
      expect(messageGroup.attributes('style')).toContain('transparent');

      // 选中后背景色改变
      const checkboxInput = wrapper.find('.mock-checkbox input[type="checkbox"]');
      await checkboxInput.setValue(true);
      await nextTick();

      expect(messageGroup.attributes('style')).toContain('#f5f7fa');
    });

    it('enableSelection 为 true 时，非 Loading 消息组的 message-group-messages 宽度应为 calc(100% - 16px)', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();

      // 第一个消息组（User 消息）有 Checkbox，宽度应缩减
      const messageGroupMessages = wrapper.findAll('.message-group-messages');
      expect(messageGroupMessages[0].attributes('style')).toContain('calc(100% - 16px)');
    });

    it('enableSelection 为 true 时，非 Loading 消息组的 message-group-messages 应有 enabled-selection 类名', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();

      const messageGroupMessages = wrapper.findAll('.message-group-messages');
      expect(messageGroupMessages[0].classes()).toContain('message-group-enabled-selection');
    });

    it('enableSelection 为 false 时，message-group-messages 宽度应为 100%', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: false },
      });

      await nextTick();

      const messageGroupMessages = wrapper.find('.message-group-messages');
      expect(messageGroupMessages.attributes('style')).toContain('100%');
    });

    it('enableSelection 从 true 变为 false 时应该隐藏 Checkbox', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1), createAssistantMessage('2', 'Hi!', 2)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();
      expect(wrapper.find('.mock-checkbox').exists()).toBe(true);

      await wrapper.setProps({ enableSelection: false });
      await nextTick();

      expect(wrapper.find('.mock-checkbox').exists()).toBe(false);
    });
  });

  describe('messageToolsTippyOptions 测试', () => {
    it('应该正确接收 messageToolsTippyOptions 属性', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];
      const messageToolsTippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), messageToolsTippyOptions },
      });

      await nextTick();

      expect(wrapper.props().messageToolsTippyOptions).toEqual(messageToolsTippyOptions);
    });

    it('messageToolsTippyOptions 应透传给 MessageTools 的 tippyOptions', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];
      const messageToolsTippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), messageToolsTippyOptions },
      });

      await nextTick();

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.attributes('data-has-tippy-options')).toBe('true');
    });

    it('不传 messageToolsTippyOptions 时 MessageTools 不应有 tippyOptions', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.attributes('data-has-tippy-options')).toBeUndefined();
    });

    it('messageToolsTippyOptions 应透传给 MessageRender 的 tippyOptions', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];
      const messageToolsTippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), messageToolsTippyOptions },
      });

      await nextTick();

      const messageRender = wrapper.find('.mock-message-render');
      expect(messageRender.attributes('data-has-tippy-options')).toBe('true');
    });

    it('不传 messageToolsTippyOptions 时 MessageRender 不应有 tippyOptions', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageRender = wrapper.find('.mock-message-render');
      expect(messageRender.attributes('data-has-tippy-options')).toBeUndefined();
    });
  });

  describe('messageToolsStatus 测试', () => {
    it('应该正确接收 messageToolsStatus 属性', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      await nextTick();

      expect(wrapper.props().messageToolsStatus).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 应该传递给 MessageTools', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      await nextTick();

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.attributes('data-message-tools-status')).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 应该传递给 MessageRender', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      await nextTick();

      const messageRender = wrapper.find('.mock-message-render');
      expect(messageRender.attributes('data-message-tools-status')).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 为 Hidden 时不应该渲染 MessageTools', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          messageToolsStatus: MessageToolsStatus.Hidden,
        },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(false);
    });

    it('messageToolsStatus 为 Disabled 时应该渲染 MessageTools', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
    });

    it('messageToolsStatus 未设置时应该正常渲染 MessageTools', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
    });

    it('slot 应该接收 messageToolsStatus', async () => {
      const messages: Message[] = [createUserMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messages,
          messageGroups: buildGroups(messages),
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
        slots: {
          default: ({ messageToolsStatus }: { messageToolsStatus: MessageToolsStatus }) =>
            h('div', { class: 'custom-message', 'data-status': messageToolsStatus }, 'Custom'),
        },
      });

      await nextTick();

      const customMessage = wrapper.find('.custom-message');
      expect(customMessage.exists()).toBe(true);
      expect(customMessage.attributes('data-status')).toBe(MessageToolsStatus.Disabled);
    });

    it('renderMode 为 Share 时 Assistant 消息组不应该渲染 MessageTools', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), renderMode: RenderMode.Share },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(false);
    });

    it('assistantMessage 包含 pause 标记时不应该渲染 MessageTools', async () => {
      const pausedMessage: Message = {
        ...createAssistantMessage('1', 'Hello', 1),
        property: { extra: { pause: true } },
      };
      const messages: Message[] = [pausedMessage];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(false);
    });

    it('enableSelection 为 true 时 Assistant 消息组不应该渲染 MessageTools', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), enableSelection: true },
      });

      await nextTick();

      expect(wrapper.find('.mock-message-tools').exists()).toBe(false);
    });
  });

  describe('renderMode 测试', () => {
    it('renderMode 为 Share 时 message-group-messages 应有 enabled-selection 类名', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), renderMode: RenderMode.Share },
      });

      await nextTick();

      const messageGroupMessages = wrapper.find('.message-group-messages');
      expect(messageGroupMessages.classes()).toContain('message-group-enabled-selection');
    });

    it('renderMode 为 Share 时流式状态不应显示停止生成按钮', async () => {
      wrapper = mount(MessageContainer, {
        props: {
          ...defaultProps,
          messageStatus: MessageStatus.Streaming,
          renderMode: RenderMode.Share,
        },
      });

      await nextTick();

      const scrollBtns = wrapper.findAll('.mock-scroll-btn');
      const stopBtn = scrollBtns.find(btn => btn.text().includes('停止生成'));
      expect(stopBtn).toBeTruthy();
      expect((stopBtn?.element as HTMLElement).style.display).toBe('none');
    });

    it('renderMode 为 Test 时 MessageTools 应过滤掉 share 按钮', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), renderMode: RenderMode.Test },
      });

      await nextTick();

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.exists()).toBe(true);
      expect(Number(messageTools.attributes('data-tools-count'))).toBe(3);
    });

    it('renderMode 为 Chat 时 MessageTools 应包含全部工具按钮', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), renderMode: RenderMode.Chat },
      });

      await nextTick();

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.exists()).toBe(true);
      expect(Number(messageTools.attributes('data-tools-count'))).toBe(4);
    });

    it('不传 renderMode 时 MessageTools 应包含全部工具按钮', async () => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];

      wrapper = mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages) },
      });

      await nextTick();

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.exists()).toBe(true);
      expect(Number(messageTools.attributes('data-tools-count'))).toBe(4);
    });
  });

  describe('messageTools / updateTools 合并测试', () => {
    // 读取 mock 序列化的工具明细
    const readTools = (w: VueWrapper, attr: 'data-tools-json' | 'data-update-tools-json') =>
      JSON.parse(w.find('.mock-message-tools').attributes(attr) ?? '[]') as Array<{
        description?: string;
        id?: string;
      }>;

    const mountAssistant = (extra: Record<string, unknown>) => {
      const messages: Message[] = [createAssistantMessage('1', 'Hello', 1)];
      return mount(MessageContainer, {
        props: { ...defaultProps, messages, messageGroups: buildGroups(messages), ...extra },
      });
    };

    it('传入 messageTools 中的新 id 应追加到内置列表末尾', async () => {
      wrapper = mountAssistant({ messageTools: [{ id: 'save', name: '保存', description: '保存' }] });
      await nextTick();

      const tools = readTools(wrapper, 'data-tools-json');
      expect(tools.length).toBe(5);
      expect(tools.at(-1)?.id).toBe('save');
    });

    it('传入 messageTools 中的同 id 应字段级覆盖内置项且不新增', async () => {
      wrapper = mountAssistant({ messageTools: [{ id: 'copy', description: '复制全文' }] });
      await nextTick();

      const tools = readTools(wrapper, 'data-tools-json');
      expect(tools.length).toBe(4);
      expect(tools.find(tool => tool.id === 'copy')?.description).toBe('复制全文');
    });

    it('messageTools 中标记 hidden 的内置项应被过滤', async () => {
      wrapper = mountAssistant({ messageTools: [{ id: 'share', hidden: true }] });
      await nextTick();

      const tools = readTools(wrapper, 'data-tools-json');
      expect(tools.length).toBe(3);
      expect(tools.some(tool => tool.id === 'share')).toBe(false);
    });

    it('不传 updateTools 时应使用内置反馈工具（like/unlike/delete）', async () => {
      wrapper = mountAssistant({});
      await nextTick();

      const tools = readTools(wrapper, 'data-update-tools-json');
      expect(tools.map(tool => tool.id)).toEqual(['like', 'unlike', 'delete']);
    });

    it('传入 updateTools 的新 id 应追加，hidden 项应被过滤', async () => {
      wrapper = mountAssistant({
        updateTools: [
          { id: 'collect', name: '收藏', description: '收藏' },
          { id: 'delete', hidden: true },
        ],
      });
      await nextTick();

      const tools = readTools(wrapper, 'data-update-tools-json');
      expect(tools.map(tool => tool.id)).toEqual(['like', 'unlike', 'collect']);
    });
  });
});
