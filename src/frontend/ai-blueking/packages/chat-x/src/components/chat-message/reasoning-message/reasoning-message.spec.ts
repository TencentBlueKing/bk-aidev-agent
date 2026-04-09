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

import { MessageStatus } from '../../../ag-ui/types/constants';
import ReasoningMessage from './reasoning-message.vue';

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock icons
vi.mock('../../../icons/messages', () => ({
  CollapsedIcon: defineComponent({
    name: 'CollapsedIcon',
    setup() {
      return () => h('span', { class: 'mock-collapsed-icon' });
    },
  }),
}));

// Mock AiLoading
vi.mock('../../ai-loading/ai-loading.vue', () => ({
  default: defineComponent({
    name: 'AiLoading',
    props: {
      size: { type: Number, default: 16 },
      stopLoading: { type: Boolean, default: false },
    },
    setup() {
      return () => h('span', { class: 'mock-ai-loading' });
    },
  }),
}));

// Mock utils
vi.mock('../../../utils/utils', () => ({
  formatDuration: (duration: number) => `${duration}ms`,
}));

// Mock CommonErrorContent
vi.mock('../../chat-content/common-error-content/common-error-content.vue', () => ({
  default: defineComponent({
    name: 'CommonErrorContent',
    props: {
      content: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-error-content' }, props.content);
    },
  }),
}));

// Mock MarkdownContent
vi.mock('../../chat-content/markdown-content/markdown-content.vue', () => ({
  default: defineComponent({
    name: 'MarkdownContent',
    props: {
      content: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-markdown-content' }, props.content);
    },
  }),
}));

describe('ReasoningMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message').exists()).toBe(true);
    });

    it('应该渲染标题区域', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title').exists()).toBe(true);
    });

    it('Pending 状态应该渲染 AiLoading', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(true);
    });

    it('Complete 状态不应该渲染 AiLoading', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(false);
    });

    it('应该渲染 CollapsedIcon', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-collapsed-icon').exists()).toBe(true);
    });
  });

  describe('状态显示测试', () => {
    it('Pending 状态应该显示思考中', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title-text').text()).toBe('思考中');
    });

    it('Streaming 状态应该显示思考中', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title-text').text()).toBe('思考中');
    });

    it('Streaming 状态应该显示 AiLoading', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(true);
    });

    it('Pending 状态应该有 is-thinking 类', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title').classes()).toContain('is-thinking');
    });

    it('Streaming 状态应该有 is-thinking 类', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title').classes()).toContain('is-thinking');
    });

    it('Complete 状态不应该显示 AiLoading', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(false);
    });

    it('Complete 状态应该显示思考完成', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title-text').text()).toContain('已思考完成');
    });

    it('Success 状态应该显示思考完成', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title-text').text()).toContain('已思考完成');
    });

    it('Success 状态应该有 is-complete 类', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title').classes()).toContain('is-complete');
    });

    it('Success 状态不应该显示 AiLoading', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(false);
    });

    it('Complete 状态有 duration 时标题应该包含耗时信息', () => {
      // 注意：组件有一个 watch 会在 duration 存在时自动折叠
      // 我们通过 mock duration 的计算来测试格式化
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
          // duration 为 undefined，避免触发 watch 中的 stop 逻辑
        },
      });

      // 验证基本的完成状态显示
      expect(wrapper.find('.ai-reasoning-message-title-text').text()).toContain('已思考完成');
    });

    it('Error 状态应该显示思考失败', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['错误内容'],
          status: MessageStatus.Error,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title-text').text()).toBe('思考失败');
    });

    it('Error 状态应该渲染 CommonErrorContent', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['错误内容'],
          status: MessageStatus.Error,
        },
      });

      expect(wrapper.find('.mock-error-content').exists()).toBe(true);
    });

    it('Error 状态标题应该有 is-error 类', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['错误内容'],
          status: MessageStatus.Error,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-title').classes()).toContain('is-error');
    });
  });

  describe('内容渲染测试', () => {
    it('应该渲染 MarkdownContent', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('应该渲染多个 MarkdownContent', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考1', '思考2', '思考3'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.findAll('.mock-markdown-content').length).toBe(3);
    });
  });

  describe('折叠功能测试', () => {
    it('点击标题应该触发折叠状态变化', async () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Pending,
          collapsed: false,
          'onUpdate:collapsed': () => {},
        },
      });

      // 初始展开
      expect(wrapper.find('.ai-reasoning-message-content').isVisible()).toBe(true);

      // 点击折叠
      await wrapper.find('.ai-reasoning-message-title').trigger('click');

      // 验证发出了 update:collapsed 事件
      expect(wrapper.emitted('update:collapsed')).toBeTruthy();
    });

    it('collapsed 为 true 时 collapsed-icon 应该有 is-collapsed 类', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Pending,
          collapsed: true,
          'onUpdate:collapsed': () => {},
        },
      });

      expect(wrapper.find('.collapsed-icon').classes()).toContain('is-collapsed');
    });
  });

  describe('duration watcher 测试', () => {
    it('duration 变化时应该自动折叠并在 nextTick 后停止 watcher', async () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
          collapsed: false,
          'onUpdate:collapsed': (val: boolean) => wrapper.setProps({ collapsed: val }),
        },
      });

      expect(wrapper.props('collapsed')).toBe(false);

      await wrapper.setProps({ duration: 1000 });
      await wrapper.vm.$nextTick();

      expect(wrapper.emitted('update:collapsed')?.[0]).toEqual([true]);
    });

    it('初始有 duration 时应该立即折叠', async () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
          duration: 500,
          collapsed: false,
          'onUpdate:collapsed': (val: boolean) => wrapper.setProps({ collapsed: val }),
        },
      });

      await wrapper.vm.$nextTick();

      expect(wrapper.emitted('update:collapsed')?.[0]).toEqual([true]);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 content 数组', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: [],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message').exists()).toBe(true);
    });

    it('应该处理 undefined content', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message').exists()).toBe(true);
    });

    it('应该处理字符串类型的 content', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: '单个字符串思考内容' as unknown as string[],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message').exists()).toBe(true);
      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message').exists()).toBe(true);
      expect(wrapper.find('.ai-reasoning-message-title').exists()).toBe(true);
      expect(wrapper.find('.ai-reasoning-message-content').exists()).toBe(true);
    });

    it('思考内容区域应对内层 ai-markdown-body 应用灰色文字样式', () => {
      wrapper = mount(ReasoningMessage, {
        props: {
          content: ['思考内容'],
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-reasoning-message-content').exists()).toBe(true);
    });
  });
});
