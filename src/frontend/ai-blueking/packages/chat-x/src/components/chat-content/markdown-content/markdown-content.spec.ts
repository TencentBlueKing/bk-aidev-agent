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
import MarkdownContent from './markdown-content.vue';

// Mock composables
vi.mock('../../../composables', () => ({
  useContainerScrollConsumer: () => ({
    value: {
      autoScrollEnabled: true,
      toScrollBottom: vi.fn(),
    },
  }),
}));

// Mock CommonErrorContent
vi.mock('../common-error-content/common-error-content.vue', () => ({
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

// Mock markdown token components
vi.mock('../../markdown-token', () => ({
  CodeContent: defineComponent({
    name: 'CodeContent',
    props: {
      token: { type: Array, default: () => [] },
    },
    emits: ['mounted'],
    setup() {
      return () => h('div', { class: 'mock-code-content' });
    },
  }),
  MermaidContent: defineComponent({
    name: 'MermaidContent',
    props: {
      token: { type: Array, default: () => [] },
    },
    emits: ['mounted'],
    setup() {
      return () => h('div', { class: 'mock-mermaid-content' });
    },
  }),
}));

vi.mock('../../markdown-token/latex-content/latex-content.vue', () => ({
  default: defineComponent({
    name: 'LatexContent',
    props: {
      token: { type: Array, default: () => [] },
    },
    emits: ['mounted'],
    setup() {
      return () => h('div', { class: 'mock-latex-content' });
    },
  }),
}));

// Mock VNodeRenderer
vi.mock('../vnode-renderer', () => ({
  default: defineComponent({
    name: 'VNodeRenderer',
    props: {
      tokens: { type: Array, default: () => [] },
      options: { type: Object, default: () => ({}) },
    },
    setup() {
      return () => h('div', { class: 'mock-vnode-renderer' });
    },
  }),
}));

// Mock markdown plugins（与 markdown-content.vue 中 .use() 的导入保持一致）
vi.mock('../../../plugins', () => ({
  markdownItBkInlineStyle: vi.fn(() => () => {}),
  markdownItLatex: vi.fn(() => () => {}),
  markdownItMermaid: vi.fn(() => () => {}),
}));

vi.mock('../../../plugins/markdown-container', () => ({
  markdownItContainer: vi.fn(() => () => {}),
}));

// Mock utils
vi.mock('../../../utils/stream-markdown-completer', () => ({
  completeMarkdownSyntax: (content: string) => ({
    content,
    isIncomplete: false,
  }),
}));

// Mock MarkdownIt
vi.mock('../../../markdown-it/index', () => ({
  default: class MockMarkdownIt {
    renderer = {
      render: vi.fn(),
    };
    parse() {
      return [];
    }
    use() {
      return this;
    }
  },
}));

// Mock dompurify
vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
  },
}));

// Mock lodash throttle
vi.mock('lodash/throttle', () => ({
  default: (fn: (...args: unknown[]) => void) => fn,
}));

// Mock markdown-it plugins
vi.mock('markdown-it-footnote', () => ({ default: () => () => {} }));
vi.mock('markdown-it-ins', () => ({ default: () => () => {} }));
vi.mock('markdown-it-mark', () => ({ default: () => () => {} }));
vi.mock('markdown-it-sub', () => ({ default: () => () => {} }));
vi.mock('markdown-it-sup', () => ({ default: () => () => {} }));
vi.mock('markdown-it-task-checkbox', () => ({ default: () => () => {} }));

describe('MarkdownContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: '# Hello' },
      });

      expect(wrapper.find('.ai-markdown-content').exists()).toBe(true);
    });

    it('应该渲染 ai-markdown-body 容器', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: 'Hello World' },
      });

      expect(wrapper.find('.ai-markdown-body').exists()).toBe(true);
    });

    it('ai-markdown-body 应该具有 data-theme="light" 属性', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: 'Hello World' },
      });

      expect(wrapper.find('.ai-markdown-body').attributes('data-theme')).toBe('light');
    });

    it('status 为 Error 时应该渲染 CommonErrorContent', () => {
      wrapper = mount(MarkdownContent, {
        props: {
          content: '错误信息',
          status: MessageStatus.Error,
        },
      });

      expect(wrapper.find('.mock-error-content').exists()).toBe(true);
      expect(wrapper.find('.ai-markdown-body').exists()).toBe(false);
    });

    it('status 不为 Error 时应该渲染正常内容', () => {
      wrapper = mount(MarkdownContent, {
        props: {
          content: '正常内容',
          status: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-error-content').exists()).toBe(false);
      expect(wrapper.find('.ai-markdown-body').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '# Markdown 内容';

      wrapper = mount(MarkdownContent, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });

    it('应该正确接收 status 属性', () => {
      wrapper = mount(MarkdownContent, {
        props: {
          content: '内容',
          status: MessageStatus.Streaming,
        },
      });

      expect((wrapper.props() as { status?: MessageStatus }).status).toBe(MessageStatus.Streaming);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: '' },
      });

      expect(wrapper.find('.ai-markdown-content').exists()).toBe(true);
    });

    it('应该处理普通文本', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: '普通文本，没有 Markdown 语法' },
      });

      expect(wrapper.find('.ai-markdown-content').exists()).toBe(true);
    });

    it('应该处理复杂的 Markdown 内容', () => {
      const content = `
# 标题
## 二级标题

- 列表项 1
- 列表项 2

\`\`\`javascript
console.log('Hello');
\`\`\`
      `;

      wrapper = mount(MarkdownContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-markdown-content').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: 'Hello' },
      });

      expect(wrapper.find('.ai-markdown-content').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持 codeHeader 插槽定义', () => {
      wrapper = mount(MarkdownContent, {
        props: { content: '# Hello' },
        slots: {
          codeHeader: ({ language }: { language: string }) => h('span', { class: 'custom-code-header' }, language),
        },
      });

      expect(wrapper.find('.ai-markdown-content').exists()).toBe(true);
    });
  });
});
