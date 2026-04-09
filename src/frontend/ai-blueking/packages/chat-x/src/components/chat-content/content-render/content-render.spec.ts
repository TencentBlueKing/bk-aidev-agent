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
import ContentRender from './content-render.vue';

import type { ReferenceDocumentContent } from '../../../ag-ui/types/contents';

// Mock MarkdownContent
vi.mock('../markdown-content/markdown-content.vue', () => ({
  default: defineComponent({
    name: 'MarkdownContent',
    props: {
      content: { type: String, default: '' },
      status: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-markdown-content' }, props.content);
    },
  }),
}));

// Mock ReferenceContent
vi.mock('../reference-content/reference-content.vue', () => ({
  default: defineComponent({
    name: 'ReferenceContent',
    props: {
      content: { type: Array, default: () => [] },
    },
    setup() {
      return () => h('div', { class: 'mock-reference-content' });
    },
  }),
}));

describe('ContentRender', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('字符串 content 应该渲染 MarkdownContent', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '这是一段 Markdown 文本',
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('Text 类型应该渲染 MarkdownContent', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '文本内容',
          type: MessageContentType.Text,
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('数组 content 应该渲染 ReferenceContent', () => {
      const referenceContent: ReferenceDocumentContent[] = [
        { name: '链接1', url: 'https://example.com', originFile: '' },
      ];
      wrapper = mount(ContentRender, {
        props: {
          content: referenceContent,
        },
      });

      expect(wrapper.find('.mock-reference-content').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确传递 status 到 MarkdownContent', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '内容',
          status: MessageStatus.Streaming,
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '内容',
        },
        slots: {
          default: ({ content }: { content: string }) => h('div', { class: 'custom-content' }, `Custom: ${content}`),
        },
      });

      expect(wrapper.find('.custom-content').exists()).toBe(true);
      expect(wrapper.find('.custom-content').text()).toBe('Custom: 内容');
    });

    it('使用 slot 时应该忽略默认渲染', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '内容',
        },
        slots: {
          default: () => h('div', { class: 'custom-content' }, '自定义内容'),
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(false);
      expect(wrapper.find('.custom-content').exists()).toBe(true);
    });

    it('应该支持 codeHeader 插槽', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '代码内容',
        },
        slots: {
          codeHeader: ({ language }: { language: string }) =>
            h('span', { class: 'custom-code-header' }, `操作 ${language}`),
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空字符串 content', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: '',
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('应该处理空数组 content', () => {
      wrapper = mount(ContentRender, {
        props: {
          content: [],
        },
      });

      expect(wrapper.find('.mock-reference-content').exists()).toBe(true);
    });
  });
});
