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

import DescPanel from './desc-panel.vue';

describe('DescPanel', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc: '描述内容',
        },
      });

      expect(wrapper.find('.toolcall-desc').exists()).toBe(true);
    });

    it('应该渲染标题', () => {
      const title = '测试标题';

      wrapper = mount(DescPanel, {
        props: {
          title,
          desc: '描述',
        },
      });

      expect(wrapper.find('.desc-title').text()).toBe(title);
    });

    it('应该渲染字符串描述', () => {
      const desc = '这是一段描述文本';

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect(wrapper.find('.desc-panel').text()).toBe(desc);
    });
  });

  describe('JSON 数据渲染测试', () => {
    it('应该解析并渲染 JSON 字符串', () => {
      const desc = JSON.stringify({ key1: 'value1', key2: 'value2' });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      const items = wrapper.findAll('.desc-panel-item');
      expect(items.length).toBe(2);
    });

    it('应该正确显示 JSON 键值对', () => {
      const desc = JSON.stringify({ name: '张三', age: '25' });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect(wrapper.find('.desc-label').text()).toContain('name');
      expect(wrapper.find('.desc-value').text()).toBe('张三');
    });

    it('无效 JSON 应该作为普通字符串显示', () => {
      const desc = '这不是有效的 JSON';

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect(wrapper.find('.desc-panel').text()).toBe(desc);
      expect(wrapper.find('.desc-panel-item').exists()).toBe(false);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 title 属性', () => {
      const title = '测试标题';

      wrapper = mount(DescPanel, {
        props: {
          title,
        },
      });

      expect((wrapper.props() as { title: string }).title).toBe(title);
    });

    it('应该正确接收 desc 属性', () => {
      const desc = '测试描述';

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect((wrapper.props() as { desc: string }).desc).toBe(desc);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 desc', () => {
      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc: '',
        },
      });

      expect(wrapper.find('.toolcall-desc').exists()).toBe(true);
    });

    it('应该处理 undefined desc', () => {
      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
        },
      });

      expect(wrapper.find('.toolcall-desc').exists()).toBe(true);
    });

    it('应该处理空对象 JSON', () => {
      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc: '{}',
        },
      });

      expect(wrapper.findAll('.desc-panel-item').length).toBe(0);
    });

    it('应该处理嵌套 JSON', () => {
      const desc = JSON.stringify({ nested: { key: 'value' } });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect(wrapper.find('.desc-panel-item').exists()).toBe(true);
    });

    it('应该处理特殊字符', () => {
      const desc = '<script>alert("xss")</script>';

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect(wrapper.find('script').exists()).toBe(false);
      expect(wrapper.find('.desc-panel').text()).toBe(desc);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc: '描述',
        },
      });

      expect(wrapper.find('.toolcall-desc').exists()).toBe(true);
      expect(wrapper.find('.desc-title').exists()).toBe(true);
      expect(wrapper.find('.desc-panel').exists()).toBe(true);
    });

    it('desc-value 应该存在于 JSON 数据渲染中', () => {
      const desc = JSON.stringify({ name: '张三', age: '25' });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      const descValues = wrapper.findAll('.desc-value');
      expect(descValues.length).toBeGreaterThan(0);
    });
  });

  describe('word-break 样式测试', () => {
    it('JSON 数据中 HighlightKeyword 应该有 word-break: break-all 样式', () => {
      const desc = JSON.stringify({ longText: '这是一段很长的文本内容用于测试换行' });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      const descValue = wrapper.find('.desc-value');
      expect(descValue.exists()).toBe(true);
      const highlightKeyword = descValue.find('[style]');
      expect(highlightKeyword.exists()).toBe(true);
      expect(highlightKeyword.attributes('style')).toContain('word-break');
    });
  });

  describe('长文本展示测试', () => {
    it('JSON 数据的 value 应在 desc-value 内展示 HighlightKeyword', () => {
      const desc = JSON.stringify({ longText: '这是一段很长的文本内容用于测试换行展示' });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      expect(wrapper.find('.desc-value').exists()).toBe(true);
    });

    it('嵌套对象应该被正确 stringify', () => {
      const desc = JSON.stringify({ nested: { key: 'value', deep: { level: 2 } } });

      wrapper = mount(DescPanel, {
        props: {
          title: '标题',
          desc,
        },
      });

      // 验证嵌套对象被渲染
      const descValue = wrapper.find('.desc-value');
      expect(descValue.exists()).toBe(true);
      expect(descValue.text()).toContain('key');
    });
  });
});
