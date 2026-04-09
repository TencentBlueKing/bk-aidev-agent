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

import CommonErrorContent from './common-error-content.vue';

// Mock icons
vi.mock('../../../icons/messages', () => ({
  ErrorIcon: defineComponent({
    name: 'ErrorIcon',
    setup() {
      return () => h('span', { class: 'mock-error-icon' });
    },
  }),
}));

describe('CommonErrorContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(CommonErrorContent, {
        props: { content: '错误信息' },
      });

      expect(wrapper.find('.ai-error-content').exists()).toBe(true);
    });

    it('应该正确渲染 content 内容', () => {
      const content = '发生了一个错误';

      wrapper = mount(CommonErrorContent, {
        props: { content },
      });

      expect(wrapper.text()).toContain(content);
    });

    it('应该渲染 ErrorIcon', () => {
      wrapper = mount(CommonErrorContent, {
        props: { content: '错误信息' },
      });

      expect(wrapper.find('.mock-error-icon').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '测试错误内容';

      wrapper = mount(CommonErrorContent, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(CommonErrorContent, {
        props: { content: '' },
      });

      expect(wrapper.find('.ai-error-content').exists()).toBe(true);
    });

    it('应该处理特殊字符的 content', () => {
      const content = '<script>alert("xss")</script>';

      wrapper = mount(CommonErrorContent, {
        props: { content },
      });

      expect(wrapper.text()).toContain(content);
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理很长的 content', () => {
      const content = '这是一个非常长的错误信息'.repeat(20);

      wrapper = mount(CommonErrorContent, {
        props: { content },
      });

      expect(wrapper.text()).toContain(content);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', () => {
      wrapper = mount(CommonErrorContent, {
        props: { content: '错误' },
      });

      expect(wrapper.find('.ai-error-content').exists()).toBe(true);
    });

    it('ai-error-content 应该使用 flex 布局包含图标和文本', () => {
      wrapper = mount(CommonErrorContent, {
        props: { content: '错误信息' },
      });

      const root = wrapper.find('.ai-error-content');
      expect(root.find('.mock-error-icon').exists()).toBe(true);
      expect(root.text()).toContain('错误信息');
    });

    it('content 文本应该被 ai-error-content-text 包裹', () => {
      wrapper = mount(CommonErrorContent, {
        props: { content: '错误信息' },
      });

      const textDiv = wrapper.find('.ai-error-content-text');
      expect(textDiv.exists()).toBe(true);
      expect(textDiv.text()).toContain('错误信息');
    });
  });
});
