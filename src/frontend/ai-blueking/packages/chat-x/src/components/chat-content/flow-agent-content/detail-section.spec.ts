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
import { h } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DetailSection from './detail-section.vue';

describe('DetailSection', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(DetailSection, {
        props: { title: '测试标题' },
      });

      expect(wrapper.find('.ai-detail-section').exists()).toBe(true);
    });

    it('应该渲染标题文本', () => {
      const title = '基础信息';

      wrapper = mount(DetailSection, {
        props: { title },
      });

      expect(wrapper.find('.section-text').text()).toBe(title);
    });

    it('应该渲染装饰条', () => {
      wrapper = mount(DetailSection, {
        props: { title: '标题' },
      });

      expect(wrapper.find('.section-bar').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该渲染默认 slot 内容', () => {
      wrapper = mount(DetailSection, {
        props: { title: '标题' },
        slots: {
          default: () => h('div', { class: 'custom-content' }, '自定义内容'),
        },
      });

      expect(wrapper.find('.custom-content').exists()).toBe(true);
      expect(wrapper.find('.custom-content').text()).toBe('自定义内容');
    });

    it('没有 slot 内容时应该正常渲染', () => {
      wrapper = mount(DetailSection, {
        props: { title: '标题' },
      });

      expect(wrapper.find('.ai-detail-section').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 title 属性', () => {
      const title = '输入参数';

      wrapper = mount(DetailSection, {
        props: { title },
      });

      expect(wrapper.props().title).toBe(title);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空标题', () => {
      wrapper = mount(DetailSection, {
        props: { title: '' },
      });

      expect(wrapper.find('.ai-detail-section').exists()).toBe(true);
      expect(wrapper.find('.section-text').text()).toBe('');
    });

    it('应该处理长标题', () => {
      const longTitle = '这是一个非常长的标题'.repeat(5);

      wrapper = mount(DetailSection, {
        props: { title: longTitle },
      });

      expect(wrapper.find('.section-text').text()).toBe(longTitle);
    });
  });
});
