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

import CiteContent from './cite-content.vue';

// Mock icons
vi.mock('../../../icons', () => ({
  CiteIcon: defineComponent({
    name: 'CiteIcon',
    setup() {
      return () => h('span', { class: 'mock-cite-icon' });
    },
  }),
  CloseIcon: defineComponent({
    name: 'CloseIcon',
    emits: ['click'],
    setup(_, { emit }) {
      return () =>
        h('span', {
          class: 'mock-close-icon',
          onClick: () => emit('click'),
        });
    },
  }),
}));

describe('CiteContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(CiteContent, {
        props: { content: '引用内容' },
      });

      expect(wrapper.find('.ai-cite-content').exists()).toBe(true);
    });

    it('应该正确渲染 content 内容', () => {
      const content = '这是引用的文本内容';

      wrapper = mount(CiteContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-cite-content-text').text()).toBe(content);
    });

    it('应该渲染 CiteIcon', () => {
      wrapper = mount(CiteContent, {
        props: { content: '引用内容' },
      });

      expect(wrapper.find('.mock-cite-icon').exists()).toBe(true);
    });

    it('没有 onClose 时不应该渲染 CloseIcon', () => {
      wrapper = mount(CiteContent, {
        props: { content: '引用内容' },
      });

      expect(wrapper.find('.mock-close-icon').exists()).toBe(false);
    });

    it('有 onClose 时应该渲染 CloseIcon', () => {
      wrapper = mount(CiteContent, {
        props: {
          content: '引用内容',
          onClose: vi.fn(),
        },
      });

      expect(wrapper.find('.mock-close-icon').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击 CloseIcon 应该调用 onClose', async () => {
      const onClose = vi.fn();

      wrapper = mount(CiteContent, {
        props: {
          content: '引用内容',
          onClose,
        },
      });

      await wrapper.find('.mock-close-icon').trigger('click');

      expect(onClose).toHaveBeenCalledWith('引用内容');
    });

    it('onClose 应该接收正确的 content 参数', async () => {
      const onClose = vi.fn();
      const content = '特定的引用内容';

      wrapper = mount(CiteContent, {
        props: {
          content,
          onClose,
        },
      });

      await wrapper.find('.mock-close-icon').trigger('click');

      expect(onClose).toHaveBeenCalledWith(content);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '测试内容';

      wrapper = mount(CiteContent, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(CiteContent, {
        props: { content: '' },
      });

      expect(wrapper.find('.ai-cite-content').exists()).toBe(true);
    });

    it('应该处理特殊字符的 content', () => {
      const content = '<script>alert("xss")</script>';

      wrapper = mount(CiteContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-cite-content-text').text()).toBe(content);
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理很长的 content', () => {
      const content = '这是一个非常长的引用内容'.repeat(20);

      wrapper = mount(CiteContent, {
        props: { content },
      });

      expect(wrapper.find('.ai-cite-content-text').text()).toBe(content);
    });
  });
});
