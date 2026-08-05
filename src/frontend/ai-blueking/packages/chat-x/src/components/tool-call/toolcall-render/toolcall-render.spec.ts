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

import { MessageContentType, MessageStatus } from '../../../ag-ui/types/constants';
import ToolcallRender from './toolcall-render.vue';

import type { ToolCall } from '../../../ag-ui/types/messages';

// Mock bkui-vue Loading
vi.mock('bkui-vue', () => ({
  Loading: defineComponent({
    name: 'Loading',
    props: {
      mode: { type: String, default: 'default' },
      size: { type: String, default: 'default' },
      theme: { type: String, default: 'default' },
    },
    setup() {
      return () => h('span', { class: 'mock-loading' });
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock utils
vi.mock('../../../utils/utils', () => ({
  formatDuration: (duration: number) => `${duration}ms`,
  getCookieByName: vi.fn(() => 'zh-cn'),
}));

// Mock icons
vi.mock('../../../icons/content', () => ({
  ArrowRightIcon: defineComponent({
    name: 'ArrowRightIcon',
    setup() {
      return () => h('span', { class: 'mock-arrow-icon' });
    },
  }),
}));

// Mock ToolMessage
vi.mock('../../chat-message/tool-message/tool-message.vue', () => ({
  default: defineComponent({
    name: 'ToolMessage',
    props: {
      content: { type: String, default: '' },
      error: { type: String, default: '' },
    },
    setup() {
      return () => h('div', { class: 'mock-tool-message' });
    },
  }),
}));

// Mock DescPanel
vi.mock('../desc-panel/desc-panel.vue', () => ({
  default: defineComponent({
    name: 'DescPanel',
    props: {
      desc: { type: String, default: '' },
      title: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-desc-panel' }, [h('div', { class: 'mock-desc-panel-title' }, props.title)]);
    },
  }),
}));

vi.mock('../../../composables/use-common', () => ({
  useCommonTippyInject: vi.fn(() => undefined),
  useKeywordInject: vi.fn(() => undefined),
  useKeywordMatch: vi.fn(() => ({ keywordMatched: { value: null }, keyword: { value: '' } })),
}));

describe('ToolcallRender', () => {
  let wrapper: VueWrapper;

  const mockToolCall = {
    id: 'tool-1',
    type: 'function' as const,
    function: {
      name: 'search',
      description: '搜索工具',
      arguments: '{"query": "test"}',
    },
  } as unknown as ToolCall;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.ai-toolcall-render').exists()).toBe(true);
    });

    it('应该渲染标题区域', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.ai-toolcall-render-header').exists()).toBe(true);
    });

    it('应该显示工具名称', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('search');
    });

    it('应该渲染 ArrowRightIcon', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.mock-arrow-icon').exists()).toBe(true);
    });

    it('应该渲染 DescPanel 组件', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.findAll('.mock-desc-panel').length).toBe(2);
    });
  });

  describe('状态显示测试', () => {
    it('Pending 状态应该显示调用中', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.toolcall-status-title').text()).toContain('调用中');
    });

    it('Pending 状态应该显示 Loading', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.mock-loading').exists()).toBe(true);
    });

    it('Streaming 状态应该显示 Loading', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.mock-loading').exists()).toBe(true);
    });

    it('Complete 状态应该显示调用成功', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.toolcall-status-title').text()).toContain('调用成功');
    });

    // Completed 与 Complete 同为完成态，兼容协议/后端返回的 completed
    it('Completed 状态应该显示调用成功', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Completed,
        },
      });

      expect(wrapper.find('.toolcall-status-title').text()).toContain('调用成功');
    });

    it('Success 状态应该显示调用成功', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.toolcall-status-title').text()).toContain('调用成功');
    });

    it('Success 状态不应该显示 Loading', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.mock-loading').exists()).toBe(false);
    });

    it('Complete 状态不应该显示 Loading', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-loading').exists()).toBe(false);
    });

    it('Completed 状态不应该显示 Loading', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Completed,
        },
      });

      expect(wrapper.find('.mock-loading').exists()).toBe(false);
    });

    it('Error 状态应该显示调用失败', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Error,
        },
      });

      expect(wrapper.find('.toolcall-status-title').text()).toContain('调用失败');
    });
  });

  describe('折叠功能测试', () => {
    it('默认应该折叠隐藏内容', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.ai-toolcall-render-content').attributes('style')).toContain('display: none');
    });

    it('点击头部应该触发折叠状态变化', async () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.ai-toolcall-render-content').attributes('style')).toContain('display: none');
      expect(wrapper.find('.mock-arrow-icon').classes()).toContain('is-collapsed');

      await wrapper.find('.ai-toolcall-render-header').trigger('click');
      const styleAfterClick = wrapper.find('.ai-toolcall-render-content').attributes('style') ?? '';
      expect(styleAfterClick).not.toContain('display: none');
      expect(wrapper.find('.mock-arrow-icon').classes()).not.toContain('is-collapsed');
    });

    it('折叠时箭头应该有 is-collapsed 类', async () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.mock-arrow-icon').classes()).toContain('is-collapsed');

      await wrapper.find('.ai-toolcall-render-header').trigger('click');

      expect(wrapper.find('.mock-arrow-icon').classes()).not.toContain('is-collapsed');
    });
  });

  describe('Duration 显示测试', () => {
    it('有 duration 时应该显示耗时', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          duration: 1500,
        },
      });

      expect(wrapper.find('.toolcall-duration').text()).toContain('1500ms');
    });

    it('没有 duration 时不应该显示耗时', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.toolcall-duration').exists()).toBe(false);
    });

    it('从 toolMessage 获取 duration', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: {
            ...mockToolCall,
            toolMessage: {
              content: 'result',
              duration: 2000,
            },
          },
        },
      });

      expect(wrapper.find('.toolcall-duration').text()).toContain('2000ms');
    });
  });

  describe('ToolMessage 渲染测试', () => {
    it('有 toolMessage 时应该渲染 ToolMessage', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: {
            ...mockToolCall,
            toolMessage: {
              content: 'result',
            },
          },
        },
      });

      expect(wrapper.find('.mock-tool-message').exists()).toBe(true);
    });

    it('没有 toolMessage 时不应该渲染 ToolMessage', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.mock-tool-message').exists()).toBe(false);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理没有 function.name 的情况', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: {
            id: 'tool-1',
            type: MessageContentType.Function,
            function: {
              name: '',
              arguments: '{}',
            },
          },
        },
      });

      // 应该使用 id 作为标题
      expect(wrapper.find('.toolcall-header-title').text()).toBe('tool-1');
    });

    it('应该处理 undefined toolCall', () => {
      wrapper = mount(ToolcallRender, {
        props: {},
      });

      expect(wrapper.find('.ai-toolcall-render').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.ai-toolcall-render').exists()).toBe(true);
      expect(wrapper.find('.ai-toolcall-render-header').exists()).toBe(true);
      expect(wrapper.find('.ai-toolcall-render-content').exists()).toBe(true);
    });

    it('状态 class 应该正确应用', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.ai-toolcall-render-header').classes()).toContain('toolcall-status-complete');
    });

    it('Completed 状态 class 应该正确应用', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Completed,
        },
      });

      expect(wrapper.find('.ai-toolcall-render-header').classes()).toContain('toolcall-status-completed');
    });
  });
});
