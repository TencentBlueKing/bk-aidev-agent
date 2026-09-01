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

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock utils
vi.mock('../../../utils/utils', () => ({
  formatDuration: (duration: number) => `${duration}ms`,
  getCookieByName: vi.fn(() => 'zh-cn'),
}));

// Mock 图标：工具调用图标 + 折叠箭头
vi.mock('../../../icons', () => ({
  ToolCallIcon: defineComponent({
    name: 'ToolCallIcon',
    setup() {
      return () => h('span', { class: 'mock-toolcall-icon' });
    },
  }),
  ChevronRightIcon: defineComponent({
    name: 'ChevronRightIcon',
    setup() {
      return () => h('span', { class: 'mock-chevron-icon' });
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

  /** 状态段用 &nbsp; 撑开括号两侧间距，断言前统一归一为普通空格 */
  const getStatusText = () => wrapper.find('.toolcall-header-status').text().replace(/\u00A0/g, ' ');

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
      expect(wrapper.find('.ai-toolcall-render-header').exists()).toBe(true);
      expect(wrapper.find('.ai-toolcall-render-content').exists()).toBe(true);
    });

    it('应该渲染工具调用图标', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
        },
      });

      expect(wrapper.find('.mock-toolcall-icon').exists()).toBe(true);
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

  describe('调用类型前缀测试', () => {
    const mountWithFunction = (fn: Record<string, unknown>) =>
      mount(ToolcallRender, {
        props: {
          toolCall: {
            ...mockToolCall,
            function: { ...mockToolCall.function, ...fn },
          },
          status: MessageStatus.Success,
        },
      });

    it('type 为 function 时应该显示「调用工具」前缀', () => {
      wrapper = mountWithFunction({ type: 'function' });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('调用工具 search');
    });

    it('type 为 mcp 时应该显示「调用 MCP」前缀，标题带 MCP 名', () => {
      wrapper = mountWithFunction({ type: 'mcp', mcpName: 'bk-data-server' });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('调用 MCP bk-data-server / search');
    });

    it('type 为 skill 时应该显示「读取 Skill」前缀', () => {
      wrapper = mountWithFunction({ type: 'skill' });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('读取 Skill search');
    });

    it('无 type 且无 mcpName 时应该显示「调用工具」前缀', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('调用工具 search');
    });

    // 旧版数据兼容：未下发 type 时回退到 mcpName 判定
    it('无 type 但有 mcpName 时应该兼容判定为「调用 MCP」', () => {
      wrapper = mountWithFunction({ mcpName: 'bk-data-server' });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('调用 MCP bk-data-server / search');
    });

    // type 优先于 mcpName：显式 function 不应被 mcpName 覆盖为 MCP
    it('type 显式为 function 时即使有 mcpName 也显示「调用工具」前缀', () => {
      wrapper = mountWithFunction({ type: 'function', mcpName: 'bk-data-server' });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('调用工具 bk-data-server / search');
    });
  });

  describe('状态显示测试', () => {
    it('Pending 状态应该显示「正在调用」，且无状态段与折叠箭头', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('正在调用 search');
      expect(wrapper.find('.toolcall-header-status').exists()).toBe(false);
      expect(wrapper.find('.mock-chevron-icon').exists()).toBe(false);
    });

    it('Streaming 状态应该显示「正在调用」', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('正在调用 search');
    });

    it('skill 进行中应该显示「正在读取」，而非「正在调用」', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: {
            ...mockToolCall,
            function: { ...mockToolCall.function, type: 'skill' },
          },
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.toolcall-header-title').text()).toBe('正在读取 search');
    });

    it('进行中态标题应该带 is-loading 类以启用渐变闪动', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Pending,
        },
      });

      expect(wrapper.find('.toolcall-header-title').classes()).toContain('is-loading');
    });

    it.each([
      ['Complete', MessageStatus.Complete],
      ['Completed', MessageStatus.Completed],
      ['Success', MessageStatus.Success],
    ])('%s 状态应该显示成功', (_name, status) => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status,
        },
      });

      expect(getStatusText()).toBe('( 成功 )');
      expect(wrapper.find('.toolcall-header-result').classes()).toContain('is-success');
    });

    it('Error 状态应该显示失败', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Error,
        },
      });

      expect(getStatusText()).toBe('( 失败 )');
      expect(wrapper.find('.toolcall-header-result').classes()).toContain('is-error');
    });

    // 括号与耗时不参与状态着色，仅状态词着色
    it('着色元素应该只包含状态词，不含括号与耗时', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
          duration: 1500,
        },
      });

      expect(wrapper.find('.toolcall-header-result').text()).toBe('成功');
    });

    // toolMessage.error 优先于 status 判定失败态
    it('toolMessage.error 为真时应该显示失败', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: {
            ...mockToolCall,
            toolMessage: { error: '执行超时' },
          },
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.toolcall-header-result').classes()).toContain('is-error');
    });
  });

  describe('折叠功能测试', () => {
    it('默认应该折叠隐藏内容', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.ai-toolcall-render-content').attributes('style')).toContain('display: none');
      expect(wrapper.find('.ai-toolcall-render-header').classes()).not.toContain('is-expanded');
    });

    it('点击头部应该展开内容并翻转箭头', async () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
        },
      });

      expect(wrapper.find('.mock-chevron-icon').classes()).not.toContain('is-expanded');

      await wrapper.find('.ai-toolcall-render-header').trigger('click');

      const styleAfterClick = wrapper.find('.ai-toolcall-render-content').attributes('style') ?? '';
      expect(styleAfterClick).not.toContain('display: none');
      expect(wrapper.find('.ai-toolcall-render-header').classes()).toContain('is-expanded');
      expect(wrapper.find('.mock-chevron-icon').classes()).toContain('is-expanded');
    });
  });

  describe('Duration 显示测试', () => {
    it('有 duration 时状态段应该带耗时', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
          duration: 1500,
        },
      });

      expect(getStatusText()).toBe('( 成功，耗时：1500ms )');
    });

    it('没有 duration 时不应该显示耗时', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: mockToolCall,
          status: MessageStatus.Success,
        },
      });

      expect(getStatusText()).toBe('( 成功 )');
    });

    it('应该从 toolMessage 获取 duration', () => {
      wrapper = mount(ToolcallRender, {
        props: {
          toolCall: {
            ...mockToolCall,
            toolMessage: {
              content: 'result',
              duration: 2000,
            },
          },
          status: MessageStatus.Success,
        },
      });

      expect(getStatusText()).toBe('( 成功，耗时：2000ms )');
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
          status: MessageStatus.Success,
        },
      });

      // 应该使用 id 作为标题
      expect(wrapper.find('.toolcall-header-title').text()).toBe('调用工具 tool-1');
    });

    it('应该处理 undefined toolCall', () => {
      wrapper = mount(ToolcallRender, {
        props: {},
      });

      expect(wrapper.find('.ai-toolcall-render').exists()).toBe(true);
    });
  });
});
