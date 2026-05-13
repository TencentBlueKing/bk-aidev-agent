/* eslint-disable @typescript-eslint/no-explicit-any */
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

import { MessageRole } from '../../../ag-ui/types';
import { MessageToolsStatus } from '../../../types/tool';
import MessageRender from './message-render.vue';

// Mock all message components
vi.mock('../user-message/user-message.vue', () => ({
  default: defineComponent({
    name: 'UserMessage',
    props: {
      content: { type: [String, Array], default: '' },
      messageToolsStatus: { type: String, default: undefined },
      onAction: { type: Function, default: null },
      tippyOptions: { type: Object, default: undefined },
    },
    setup(props) {
      return () =>
        h(
          'div',
          {
            class: 'mock-user-message',
            'data-message-tools-status': props.messageToolsStatus,
            'data-has-tippy-options': props.tippyOptions !== undefined ? 'true' : undefined,
          },
          props.content as string,
        );
    },
  }),
}));

vi.mock('../assistant-message/assistant-message.vue', () => ({
  default: defineComponent({
    name: 'AssistantMessage',
    props: {
      content: { type: [String, Array], default: '' },
      status: { type: String, default: '' },
    },
    setup(props, { slots }) {
      return () => h('div', { class: 'mock-assistant-message' }, slots.default?.() || (props.content as string));
    },
  }),
}));

vi.mock('../info-message/info-message.vue', () => ({
  default: defineComponent({
    name: 'InfoMessage',
    props: {
      content: { type: [String, Array], default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-info-message' }, props.content as string);
    },
  }),
}));

vi.mock('../reasoning-message/reasoning-message.vue', () => ({
  default: defineComponent({
    name: 'ReasoningMessage',
    props: {
      content: { type: Array, default: () => [] },
      status: { type: String, default: '' },
    },
    setup() {
      return () => h('div', { class: 'mock-reasoning-message' });
    },
  }),
}));

vi.mock('../tool-message/tool-message.vue', () => ({
  default: defineComponent({
    name: 'ToolMessage',
    props: {
      content: { type: String, default: '' },
    },
    setup() {
      return () => h('div', { class: 'mock-tool-message' });
    },
  }),
}));

vi.mock('../activity-message/activity-message.vue', () => ({
  default: defineComponent({
    name: 'ActivityMessage',
    props: {
      content: { type: Array, default: () => [] },
    },
    setup() {
      return () => h('div', { class: 'mock-activity-message' });
    },
  }),
}));

/** 与 message-render 中 `InterruptMessageRender` 命名导出一致，避免真实中断组件链路过重 */
vi.mock('../interrupt-message', () => ({
  InterruptMessageRender: defineComponent({
    name: 'InterruptMessageRender',
    props: {
      onInterruptResume: { type: Function, default: undefined },
    },
    setup(props) {
      return () =>
        h('div', {
          class: 'mock-interrupt-message-render',
          'data-has-on-interrupt-resume': props.onInterruptResume ? 'true' : undefined,
        });
    },
  }),
}));

vi.mock('../loading-message/loading-message.vue', () => ({
  default: defineComponent({
    name: 'LoadingMessage',
    props: {
      content: { type: String, default: '' },
    },
    setup() {
      return () => h('div', { class: 'mock-loading-message' });
    },
  }),
}));

vi.mock('../../chat-content/content-render/content-render.vue', () => ({
  default: defineComponent({
    name: 'ContentRender',
    props: {
      content: { type: [String, Array], default: '' },
      status: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-content-render' }, props.content as string);
    },
  }),
}));

describe('MessageRender', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('User 消息渲染测试', () => {
    it('应该正确渲染 User 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
        },
      });

      expect(wrapper.find('.mock-user-message').exists()).toBe(true);
    });
  });

  describe('Assistant 消息渲染测试', () => {
    it('应该正确渲染 Assistant 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Assistant,
            content: '助手消息',
          },
        },
      });

      expect(wrapper.find('.mock-assistant-message').exists()).toBe(true);
    });
  });

  describe('Info 消息渲染测试', () => {
    it('应该正确渲染 Info 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Info,
            content: '信息消息',
          },
        },
      });

      expect(wrapper.find('.mock-info-message').exists()).toBe(true);
    });
  });

  describe('Reasoning 消息渲染测试', () => {
    it('应该正确渲染 Reasoning 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Reasoning,
            content: ['思考内容'],
          },
        },
      });

      expect(wrapper.find('.mock-reasoning-message').exists()).toBe(true);
    });
  });

  describe('Tool 消息渲染测试', () => {
    it('应该正确渲染 Tool 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Tool,
            content: '工具消息',
          },
        },
      });

      expect(wrapper.find('.mock-tool-message').exists()).toBe(true);
    });
  });

  describe('Activity 消息渲染测试', () => {
    it('应该正确渲染 Activity 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Activity,
            content: [],
          },
        },
      });

      expect(wrapper.find('.mock-activity-message').exists()).toBe(true);
    });
  });

  describe('Interrupt 消息渲染测试', () => {
    it('应该通过 InterruptMessageRender 渲染 Interrupt 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Interrupt,
            content: '',
          },
        },
      });

      expect(wrapper.find('.mock-interrupt-message-render').exists()).toBe(true);
    });

    it('应该将 onInterruptResume 传递给 InterruptMessageRender', () => {
      const onInterruptResume = vi.fn();

      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Interrupt,
            content: '',
          },
          onInterruptResume,
        },
      });

      const interrupt = wrapper.find('.mock-interrupt-message-render');
      expect(interrupt.exists()).toBe(true);
      expect(interrupt.attributes('data-has-on-interrupt-resume')).toBe('true');
    });
  });

  describe('Loading 消息渲染测试', () => {
    it('应该正确渲染 Loading 消息', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Loading,
            content: '',
          },
        },
      });

      expect(wrapper.find('.mock-loading-message').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确传递 onAction 到 UserMessage', () => {
      const onAction = vi.fn();

      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
          onAction,
        },
      });

      expect(wrapper.find('.mock-user-message').exists()).toBe(true);
    });
  });

  describe('tippyOptions 透传测试', () => {
    it('应该正确将 tippyOptions 传递给 UserMessage', () => {
      const tippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
          tippyOptions,
        },
      });

      const userMessage = wrapper.find('.mock-user-message');
      expect(userMessage.exists()).toBe(true);
      expect(userMessage.attributes('data-has-tippy-options')).toBe('true');
    });

    it('不传 tippyOptions 时 UserMessage 不应有 tippyOptions', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
        },
      });

      const userMessage = wrapper.find('.mock-user-message');
      expect(userMessage.attributes('data-has-tippy-options')).toBeUndefined();
    });
  });

  describe('边界情况测试', () => {
    it('未知角色应该不渲染任何内容', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: 'unknown',
            content: '未知消息',
          } as any,
        },
      });

      expect(wrapper.find('.mock-user-message').exists()).toBe(false);
      expect(wrapper.find('.mock-assistant-message').exists()).toBe(false);
      expect(wrapper.find('.mock-info-message').exists()).toBe(false);
      expect(wrapper.find('.mock-interrupt-message-render').exists()).toBe(false);
    });

    it('应该处理空 message', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {},
        },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });

  describe('messageToolsStatus 传递测试', () => {
    it('应该正确将 messageToolsStatus 传递给 UserMessage', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      const userMessage = wrapper.find('.mock-user-message');
      expect(userMessage.exists()).toBe(true);
      expect(userMessage.attributes('data-message-tools-status')).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 为 Hidden 时应该传递给 UserMessage', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
          messageToolsStatus: MessageToolsStatus.Hidden,
        },
      });

      const userMessage = wrapper.find('.mock-user-message');
      expect(userMessage.attributes('data-message-tools-status')).toBe(MessageToolsStatus.Hidden);
    });

    it('messageToolsStatus 未设置时不应该传递给 UserMessage', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.User,
            content: '用户消息',
          },
        },
      });

      const userMessage = wrapper.find('.mock-user-message');
      expect(userMessage.attributes('data-message-tools-status')).toBeUndefined();
    });
  });

  describe('codeHeader 插槽透传测试', () => {
    it('应该支持 codeHeader 插槽', () => {
      wrapper = mount(MessageRender, {
        props: {
          message: {
            role: MessageRole.Assistant,
            content: '助手消息',
          },
        },
        slots: {
          codeHeader: ({ language }: { language: string }) => h('span', { class: 'custom-code-header' }, language),
        },
      });

      expect(wrapper.find('.mock-assistant-message').exists()).toBe(true);
    });
  });
});
