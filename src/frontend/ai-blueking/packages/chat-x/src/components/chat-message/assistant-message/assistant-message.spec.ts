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

import { defineComponent, h } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageContentType, MessageStatus } from '../../../ag-ui/types';
import AssistantMessage from './assistant-message.vue';

// Mock ContentRender
vi.mock('../../chat-content/content-render/content-render.vue', () => ({
  default: defineComponent({
    name: 'ContentRender',
    props: {
      content: { type: [String, Array], default: '' },
      status: { type: String, default: '' },
      type: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-content-render' }, props.content);
    },
  }),
}));

// Mock ToolCallRender
vi.mock('../../tool-call/toolcall-render/toolcall-render.vue', () => ({
  default: defineComponent({
    name: 'ToolCallRender',
    props: {
      toolCall: { type: Object, default: null },
      status: { type: String, default: '' },
    },
    setup(props) {
      return () =>
        h('div', {
          class: 'mock-toolcall-render',
          'data-tool-id': props.toolCall?.id,
          'data-status': props.status,
        });
    },
  }),
}));

describe('AssistantMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '助手消息内容',
        },
      });

      expect(wrapper.find('.ai-assistant-message').exists()).toBe(true);
    });

    it('应该渲染 ContentRender 组件', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '助手消息内容',
        },
      });

      expect(wrapper.find('.mock-content-render').exists()).toBe(true);
    });

    it('应该正确传递 content 到 ContentRender', () => {
      const content = '这是助手的回复内容';

      wrapper = mount(AssistantMessage, {
        props: { content },
      });

      expect(wrapper.find('.mock-content-render').text()).toBe(content);
    });
  });

  describe('ToolCalls 渲染测试', () => {
    it('有 toolCalls 时应该渲染 ToolCallRender', () => {
      const toolCalls = [
        { id: 'tool-1', type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } },
      ];

      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          toolCalls,
        },
      });

      expect(wrapper.find('.mock-toolcall-render').exists()).toBe(true);
    });

    it('没有 toolCalls 时不应该渲染 ToolCallRender', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
        },
      });

      expect(wrapper.find('.mock-toolcall-render').exists()).toBe(false);
    });

    it('应该渲染多个 ToolCallRender', () => {
      const toolCalls = [
        { id: 'tool-1', type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } },
        { id: 'tool-2', type: MessageContentType.Function, function: { name: 'fetch', arguments: '{}' } },
      ];

      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          toolCalls,
        },
      });

      expect(wrapper.findAll('.mock-toolcall-render').length).toBe(2);
    });

    it('无 toolMessage 时应向 ToolCallRender 传递 Pending，即使助手 status 为 Complete', () => {
      const toolCalls = [
        { id: 'tool-1', type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } },
      ];

      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          status: MessageStatus.Complete,
          toolCalls,
        },
      });

      expect(wrapper.find('.mock-toolcall-render').attributes('data-status')).toBe(MessageStatus.Pending);
    });

    it('toolMessage.error 为真时应向 ToolCallRender 传递 Error', () => {
      const toolCalls = [
        {
          id: 'tool-1',
          type: MessageContentType.Function,
          function: { name: 'search', arguments: '{}' },
          toolMessage: {
            error: 'rate limit',
            status: MessageStatus.Complete,
          },
        },
      ];

      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          status: MessageStatus.Complete,
          toolCalls,
        },
      });

      expect(wrapper.find('.mock-toolcall-render').attributes('data-status')).toBe(MessageStatus.Error);
    });

    it('有 toolMessage.status 时应优先使用该 status', () => {
      const toolCalls = [
        {
          id: 'tool-1',
          type: MessageContentType.Function,
          function: { name: 'search', arguments: '{}' },
          toolMessage: {
            status: MessageStatus.Success,
          },
        },
      ];

      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          status: MessageStatus.Streaming,
          toolCalls,
        },
      });

      expect(wrapper.find('.mock-toolcall-render').attributes('data-status')).toBe(MessageStatus.Success);
    });

    it('有 toolMessage 但无 status/error 时应回退到助手 status', () => {
      const toolCalls = [
        {
          id: 'tool-1',
          type: MessageContentType.Function,
          function: { name: 'search', arguments: '{}' },
          toolMessage: {
            content: 'ok',
          },
        },
      ];

      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          status: MessageStatus.Streaming,
          toolCalls,
        },
      });

      expect(wrapper.find('.mock-toolcall-render').attributes('data-status')).toBe(MessageStatus.Streaming);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
        },
        slots: {
          default: ({ content }: { content: string }) => h('div', { class: 'custom-content' }, `Custom: ${content}`),
        },
      });

      expect(wrapper.find('.custom-content').exists()).toBe(true);
    });

    it('使用 slot 时不应该渲染默认 ContentRender', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
        },
        slots: {
          default: () => h('div', { class: 'custom-content' }, '自定义内容'),
        },
      });

      expect(wrapper.find('.mock-content-render').exists()).toBe(false);
      expect(wrapper.find('.custom-content').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 status 属性', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.ai-assistant-message').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '',
        },
      });

      expect(wrapper.find('.ai-assistant-message').exists()).toBe(true);
    });

    it('应该处理 undefined content', () => {
      wrapper = mount(AssistantMessage, {
        props: {},
      });

      expect(wrapper.find('.ai-assistant-message').exists()).toBe(true);
    });

    it('应该处理空的 toolCalls 数组', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
          toolCalls: [],
        },
      });

      expect(wrapper.find('.mock-toolcall-render').exists()).toBe(false);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(AssistantMessage, {
        props: {
          content: '内容',
        },
      });

      expect(wrapper.find('.ai-assistant-message').exists()).toBe(true);
      expect(wrapper.find('.ai-assistant-message-content').exists()).toBe(true);
    });
  });
});
