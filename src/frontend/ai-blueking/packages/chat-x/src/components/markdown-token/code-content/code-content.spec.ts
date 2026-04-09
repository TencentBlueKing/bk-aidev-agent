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

import CodeContent from './code-content.vue';

vi.mock('highlight.js/styles/github-dark.css', () => ({}));

// Mock highlight.js
vi.mock('highlight.js', () => ({
  default: {
    highlight: vi.fn((code: string, _options: { language: string }) => ({
      value: `<span class="hljs-highlighted">${code}</span>`,
    })),
    getLanguage: vi.fn((lang: string) => {
      if (['javascript', 'typescript', 'python', 'java'].includes(lang)) {
        return { name: lang };
      }
      return null;
    }),
  },
}));

// Mock MarkdownLanguageMap
vi.mock('../../../common', async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    MarkdownLanguageMap: {
      js: 'javascript',
      ts: 'typescript',
      py: 'python',
    },
  };
});

// Mock ToolBtn
vi.mock('../../ai-buttons/tool-btn/tool-btn.vue', () => ({
  default: defineComponent({
    name: 'ToolBtn',
    props: {
      id: { type: String, default: '' },
      description: { type: String, default: '' },
      name: { type: String, default: '' },
    },
    emits: ['click'],
    setup(props, { emit }) {
      return () =>
        h(
          'button',
          {
            class: 'mock-tool-btn',
            'data-id': props.id,
            onClick: () => emit('click'),
          },
          props.name,
        );
    },
  }),
}));

describe('CodeContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(CodeContent, {
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

      expect(wrapper.find('.code-content-wrapper').exists()).toBe(true);
    });

    it('应该渲染 pre 和 code 元素', () => {
      wrapper = mount(CodeContent, {
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

      expect(wrapper.find('.hljs-pre').exists()).toBe(true);
      expect(wrapper.find('code').exists()).toBe(true);
    });

    it('应该正确设置语言 class', () => {
      wrapper = mount(CodeContent, {
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

      expect(wrapper.find('code').classes()).toContain('hljs');
      expect(wrapper.find('code').classes()).toContain('language-javascript');
    });
  });

  describe('代码高亮测试', () => {
    it('应该渲染代码行', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'javascript',
              content: 'const a = 1;\nconst b = 2;',
            },
          ],
        },
      });

      expect(wrapper.findAll('.code-line').length).toBeGreaterThan(0);
    });

    it('应该渲染当前行（实时高亮）', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'javascript',
              content: 'const a = 1',
            },
          ],
        },
      });

      // 单行情况下应该显示为当前行
      const currentLine = wrapper.find('.current-line');
      expect(currentLine.exists()).toBe(true);
    });
  });

  describe('Token 解析测试', () => {
    it('应该解析 fence 类型 token', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'typescript',
              content: 'const x: number = 1;',
            },
          ],
        },
      });

      expect(wrapper.find('code').classes()).toContain('language-typescript');
    });

    it('应该解析 code_block 类型 token', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'code_block',
              info: 'python',
              content: 'print("hello")',
            },
          ],
        },
      });

      expect(wrapper.find('code').classes()).toContain('language-python');
    });

    it('应该处理语言映射', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'js',
              content: 'const a = 1;',
            },
          ],
        },
      });

      expect(wrapper.find('code').classes()).toContain('language-js');
    });
  });

  describe('事件测试', () => {
    it('应该在挂载后发出 mounted 事件', async () => {
      wrapper = mount(CodeContent, {
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

      // 等待 nextTick
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(wrapper.emitted('mounted')).toBeTruthy();
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 token 数组', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [],
        },
      });

      expect(wrapper.find('.code-content-wrapper').exists()).toBe(true);
    });

    it('应该处理空内容', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'javascript',
              content: '',
            },
          ],
        },
      });

      expect(wrapper.find('.code-content-wrapper').exists()).toBe(true);
    });

    it('应该处理没有语言的代码块', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: '',
              content: 'plain text',
            },
          ],
        },
      });

      expect(wrapper.find('code').classes()).toContain('hljs');
    });

    it('应该处理未知语言', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'unknown-lang',
              content: 'some code',
            },
          ],
        },
      });

      expect(wrapper.find('.code-content-wrapper').exists()).toBe(true);
    });

    it('应该处理多行代码', () => {
      const multilineCode = 'line1\nline2\nline3\nline4';

      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'javascript',
              content: multilineCode,
            },
          ],
        },
      });

      expect(wrapper.findAll('.code-line').length).toBeGreaterThan(0);
    });

    it('应该处理特殊字符', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'html',
              content: '<div>&</div>',
            },
          ],
        },
      });

      expect(wrapper.find('.code-content-wrapper').exists()).toBe(true);
    });
  });

  describe('Header 测试', () => {
    it('应该渲染 code-content-header', () => {
      wrapper = mount(CodeContent, {
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

      expect(wrapper.find('.code-content-header').exists()).toBe(true);
    });

    it('应该正确显示语言名称', () => {
      wrapper = mount(CodeContent, {
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

      expect(wrapper.find('.code-header-language').text()).toBe('javascript');
    });

    it('应该渲染复制按钮', () => {
      wrapper = mount(CodeContent, {
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

      const copyBtn = wrapper.find('.mock-tool-btn[data-id="copy"]');
      expect(copyBtn.exists()).toBe(true);
    });

    it('点击复制按钮应该调用 clipboard API', async () => {
      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: writeTextMock },
        writable: true,
        configurable: true,
      });

      wrapper = mount(CodeContent, {
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

      const copyBtn = wrapper.find('.mock-tool-btn[data-id="copy"]');
      await copyBtn.trigger('click');

      expect(writeTextMock).toHaveBeenCalled();
    });

    it('应该支持 header 插槽自定义内容', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'javascript',
              content: 'const a = 1;',
            },
          ],
        },
        slots: {
          header: ({ language }: { language: string }) =>
            h('span', { class: 'custom-header-action' }, `插入 ${language}`),
        },
      });

      const customAction = wrapper.find('.custom-header-action');
      expect(customAction.exists()).toBe(true);
      expect(customAction.text()).toBe('插入 javascript');
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(CodeContent, {
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

      expect(wrapper.find('.code-content-wrapper').exists()).toBe(true);
      expect(wrapper.find('.hljs-pre').exists()).toBe(true);
    });

    it('header 区域应包含语言标签和复制按钮', () => {
      wrapper = mount(CodeContent, {
        props: {
          token: [
            {
              type: 'fence',
              info: 'typescript',
              content: 'const x = 1;',
            },
          ],
        },
      });

      expect(wrapper.find('.code-content-header').exists()).toBe(true);
      expect(wrapper.find('.code-header-language').text()).toBe('typescript');
      expect(wrapper.find('.mock-tool-btn[data-id="copy"]').exists()).toBe(true);
    });
  });
});
