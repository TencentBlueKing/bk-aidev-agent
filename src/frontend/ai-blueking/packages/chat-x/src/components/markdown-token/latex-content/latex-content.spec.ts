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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import LatexContent from './latex-content.vue';

// Mock katex
vi.mock('katex', () => ({
  default: {
    renderToString: vi.fn((content: string) => `<span class="katex-rendered">${content}</span>`),
  },
}));

// Mock lodash throttle
vi.mock('lodash/throttle', () => ({
  default: (fn: (...args: unknown[]) => void) => fn,
}));

describe('LatexContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_inline',
              content: 'x^2',
            },
          ],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('应该渲染行内公式', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_inline',
              content: 'x + y = z',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-inline-latex-content').exists()).toBe(true);
    });

    it('应该渲染块级公式', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_block',
              content: '\\sum_{i=1}^n x_i',
            },
          ],
        },
      });

      expect(wrapper.find('.ai-block-latex-content').exists()).toBe(true);
    });
  });

  describe('Token 解析测试', () => {
    it('应该解析 math_inline 类型', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_inline',
              content: 'a^2 + b^2 = c^2',
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('inline-katex');
    });

    it('应该解析 math_block 类型', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_block',
              content: '\\int_0^1 x^2 dx',
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('ai-block-latex-wrapper');
    });

    it('应该解析带 meta displayMode 的 token', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_inline',
              content: 'E = mc^2',
              meta: { displayMode: true },
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('block-katex');
    });
  });

  describe('文本渲染测试', () => {
    it('应该渲染 text token', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'text',
              content: 'Hello World',
            },
          ],
        },
      });

      expect(wrapper.text()).toContain('Hello World');
    });

    it('应该渲染 paragraph', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'paragraph_open',
            },
            {
              type: 'text',
              content: '段落内容',
            },
            {
              type: 'paragraph_close',
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('<p>');
    });
  });

  describe('inline children 渲染测试', () => {
    it('应该渲染 inline token 的 children', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'inline',
              children: [
                {
                  type: 'text',
                  content: '文本内容',
                },
              ],
            },
          ],
        },
      });

      expect(wrapper.text()).toContain('文本内容');
    });

    it('应该渲染 strong 标签', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'inline',
              children: [{ type: 'strong_open' }, { type: 'text', content: '加粗' }, { type: 'strong_close' }],
            } as any,
          ],
        },
      });

      expect(wrapper.html()).toContain('<strong>');
    });

    it('应该渲染 em 标签', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'inline',
              children: [{ type: 'em_open' }, { type: 'text', content: '斜体' }, { type: 'em_close' }],
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('<em>');
    });

    it('应该渲染 code_inline', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'inline',
              children: [
                {
                  type: 'code_inline',
                  content: 'const a = 1',
                },
              ],
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('<code>');
    });

    it('应该渲染 softbreak', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'inline',
              children: [{ type: 'text', content: 'line1' }, { type: 'softbreak' }, { type: 'text', content: 'line2' }],
            },
          ],
        },
      });

      expect(wrapper.text()).toContain('line1');
      expect(wrapper.text()).toContain('line2');
    });

    it('应该渲染 hardbreak', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'inline',
              children: [{ type: 'text', content: 'line1' }, { type: 'hardbreak' }, { type: 'text', content: 'line2' }],
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('<br>');
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 token 数组', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('应该处理空内容', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_inline',
              content: '',
            },
          ],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('应该转义 HTML 特殊字符', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'text',
              content: '<script>alert("xss")</script>',
            },
          ],
        },
      });

      expect(wrapper.html()).toContain('&lt;script&gt;');
      expect(wrapper.find('script').exists()).toBe(false);
    });
  });

  describe('样式测试', () => {
    it('块级公式应该使用 div 包装', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_block',
              content: 'x^2',
            },
          ],
        },
      });

      expect(wrapper.element.tagName).toBe('DIV');
    });

    it('行内公式应该使用 span 包装', () => {
      wrapper = mount(LatexContent, {
        props: {
          token: [
            {
              type: 'math_inline',
              content: 'x^2',
            },
          ],
        },
      });

      expect(wrapper.element.tagName).toBe('SPAN');
    });
  });
});
