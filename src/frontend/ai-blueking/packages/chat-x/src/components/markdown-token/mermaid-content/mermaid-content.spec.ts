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

import { nextTick } from 'vue';

import { type VueWrapper, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import MermaidContent from './mermaid-content.vue';

// Mock mermaid
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    parse: vi.fn().mockResolvedValue(true),
    render: vi.fn().mockResolvedValue({
      svg: '<svg class="mock-mermaid-svg"></svg>',
    }),
  },
}));

// Mock lodash throttle
vi.mock('lodash/throttle', () => ({
  default: (fn: (...args: unknown[]) => void) => fn,
}));

describe('MermaidContent', () => {
  let wrapper: VueWrapper;

  beforeEach(async () => {
    vi.clearAllMocks();
    // 预加载 mock 模块到缓存，确保组件内 dynamic import('mermaid') 能同步解析
    await import('mermaid');
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'mermaid',
              content: 'graph TD\nA-->B',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });
  });

  describe('Token 解析测试', () => {
    it('应该解析 mermaid fence token', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'mermaid',
              content: 'graph LR\nA-->B',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });

    it('应该忽略非 mermaid fence', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'javascript',
              content: 'const a = 1;',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('应该发出 mounted 事件', async () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'mermaid',
              content: 'graph TD\nA-->B',
            },
          ],
        },
      });

      await flushPromises();
      await nextTick();

      expect(wrapper.emitted('mounted')).toBeTruthy();
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 token 数组', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });

    it('应该处理空内容', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'mermaid',
              content: '',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });

    it('应该处理没有 info 的 token', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              content: 'graph TD\nA-->B',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', () => {
      wrapper = mount(MermaidContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'mermaid',
              content: 'graph TD\nA-->B',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-mermaid-content').exists()).toBe(true);
    });
  });
});
