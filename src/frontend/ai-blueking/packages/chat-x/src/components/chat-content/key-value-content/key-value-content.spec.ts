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

import KeyValueContent from './key-value-content.vue';

// Mock icons
vi.mock('../../../icons', () => ({
  ThinkingIcon: defineComponent({
    name: 'ThinkingIcon',
    setup() {
      return () => h('span', { class: 'mock-thinking-icon' });
    },
  }),
}));

describe('KeyValueContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: 'name', value: 'test' }],
        },
      });

      expect(wrapper.find('.ai-key-value-content').exists()).toBe(true);
    });

    it('应该正确渲染键值对内容', () => {
      const content = [
        { key: '姓名', value: '张三' },
        { key: '年龄', value: '25' },
      ];

      wrapper = mount(KeyValueContent, {
        props: { content },
      });

      const items = wrapper.findAll('.key-value-item');
      expect(items.length).toBe(2);
      expect(items[0].find('.item-key').text()).toBe('姓名');
      expect(items[0].find('.item-value').text()).toBe('张三');
      expect(items[1].find('.item-key').text()).toBe('年龄');
      expect(items[1].find('.item-value').text()).toBe('25');
    });

    it('有 title 时应该渲染标题', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: 'key', value: 'value' }],
          title: '信息概览',
        },
      });

      expect(wrapper.find('.ai-key-value-title').exists()).toBe(true);
      expect(wrapper.find('.ai-key-value-title').text()).toContain('信息概览');
    });

    it('没有 title 时不应该渲染标题', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: 'key', value: 'value' }],
        },
      });

      expect(wrapper.find('.ai-key-value-title').exists()).toBe(false);
    });

    it('有 title 时应该渲染 ThinkingIcon', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: 'key', value: 'value' }],
          title: '标题',
        },
      });

      expect(wrapper.find('.mock-thinking-icon').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = [{ key: 'test', value: 'value' }];

      wrapper = mount(KeyValueContent, {
        props: { content },
      });

      expect((wrapper.props() as { content: typeof content }).content).toEqual(content);
    });

    it('应该正确接收 title 属性', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: 'key', value: 'value' }],
          title: '测试标题',
        },
      });

      expect((wrapper.props() as { title?: string }).title).toBe('测试标题');
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 content 数组', () => {
      wrapper = mount(KeyValueContent, {
        props: { content: [] },
      });

      expect(wrapper.find('.ai-key-value-content').exists()).toBe(true);
      expect(wrapper.findAll('.key-value-item').length).toBe(0);
    });

    it('应该处理单个键值对', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: '唯一键', value: '唯一值' }],
        },
      });

      expect(wrapper.findAll('.key-value-item').length).toBe(1);
    });

    it('应该处理很多键值对', () => {
      const content = Array.from({ length: 20 }, (_, i) => ({
        key: `键${i}`,
        value: `值${i}`,
      }));

      wrapper = mount(KeyValueContent, {
        props: { content },
      });

      expect(wrapper.findAll('.key-value-item').length).toBe(20);
    });

    it('应该处理特殊字符的键和值', () => {
      const content = [{ key: '<script>', value: 'alert("xss")' }];

      wrapper = mount(KeyValueContent, {
        props: { content },
      });

      expect(wrapper.find('.item-key').text()).toBe('<script>');
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理空的键或值', () => {
      const content = [
        { key: '', value: '有值' },
        { key: '有键', value: '' },
      ];

      wrapper = mount(KeyValueContent, {
        props: { content },
      });

      expect(wrapper.findAll('.key-value-item').length).toBe(2);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(KeyValueContent, {
        props: {
          content: [{ key: 'k', value: 'v' }],
        },
      });

      expect(wrapper.find('.ai-key-value-content').exists()).toBe(true);
      expect(wrapper.find('.key-value-item').exists()).toBe(true);
      expect(wrapper.find('.item-key').exists()).toBe(true);
      expect(wrapper.find('.item-value').exists()).toBe(true);
    });
  });
});
