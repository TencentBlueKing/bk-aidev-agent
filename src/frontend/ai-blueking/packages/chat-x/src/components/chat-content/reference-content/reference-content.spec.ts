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

import ReferenceContent from './reference-content.vue';

import type { ReferenceDocumentContent } from '../../../ag-ui/types/contents';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock vue-tippy
vi.mock('vue-tippy', () => ({
  directive: {
    mounted: vi.fn(),
    unmounted: vi.fn(),
  },
}));

// Mock icons
vi.mock('../../../icons', () => ({
  DocLinkIcon: defineComponent({
    name: 'DocLinkIcon',
    props: {
      color: { type: String, default: '' },
    },
    setup() {
      return () => h('span', { class: 'mock-doc-link-icon' });
    },
  }),
  PreviewIcon: defineComponent({
    name: 'PreviewIcon',
    emits: ['click'],
    setup(_, { emit }) {
      return () =>
        h('span', {
          class: 'mock-preview-icon',
          onClick: (e: MouseEvent) => emit('click', e),
        });
    },
  }),
  TargetIcon: defineComponent({
    name: 'TargetIcon',
    emits: ['click'],
    setup(_, { emit }) {
      return () =>
        h('span', {
          class: 'mock-target-icon',
          onClick: (e: MouseEvent) => emit('click', e),
        });
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

describe('ReferenceContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      const content: ReferenceDocumentContent[] = [{ name: '参考链接1', url: 'https://example.com', originFile: '' }];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-reference-item').exists()).toBe(true);
    });

    it('应该正确渲染多个参考链接', () => {
      const content: ReferenceDocumentContent[] = [
        { name: '链接1', url: 'https://example1.com', originFile: '' },
        { name: '链接2', url: 'https://example2.com', originFile: '' },
        { name: '链接3', url: 'https://example3.com', originFile: '' },
      ];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.findAll('.ai-reference-item').length).toBe(3);
    });

    it('应该正确渲染链接标题', () => {
      const content: ReferenceDocumentContent[] = [
        { name: '测试链接标题', url: 'https://example.com', originFile: '' },
      ];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-reference-item-title').text()).toBe('测试链接标题');
    });

    it('应该渲染 DocLinkIcon', () => {
      const content: ReferenceDocumentContent[] = [{ name: '链接', url: 'https://example.com', originFile: '' }];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.find('.mock-doc-link-icon').exists()).toBe(true);
    });
  });

  describe('过滤测试', () => {
    it('应该过滤掉没有 name 的项', () => {
      const content: ReferenceDocumentContent[] = [
        { name: '', url: 'https://example.com', originFile: '' },
        { name: '有名字', url: 'https://example2.com', originFile: '' },
      ];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.findAll('.ai-reference-item').length).toBe(1);
      expect(wrapper.find('.ai-reference-item-title').text()).toBe('有名字');
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 content 数组', () => {
      wrapper = mount(ReferenceContent, {
        props: { content: [] },
      });

      expect(wrapper.findAll('.ai-reference-item').length).toBe(0);
    });

    it('应该处理特殊字符的 name', () => {
      const content: ReferenceDocumentContent[] = [
        { name: '<script>alert("xss")</script>', url: 'https://example.com', originFile: '' },
      ];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-reference-item-title').text()).toBe('<script>alert("xss")</script>');
      expect(wrapper.find('script').exists()).toBe(false);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      const content: ReferenceDocumentContent[] = [{ name: '链接', url: 'https://example.com', originFile: '' }];

      wrapper = mount(ReferenceContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-reference-item').exists()).toBe(true);
      expect(wrapper.find('.ai-reference-item-title').exists()).toBe(true);
    });
  });
});
