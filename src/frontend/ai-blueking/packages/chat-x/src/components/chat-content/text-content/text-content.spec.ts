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

import TextContent from './text-content.vue';

describe('TextContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(TextContent, {
        props: { content: '文本内容' },
      });

      expect(wrapper.find('.text-content').exists()).toBe(true);
    });

    it('应该正确渲染 content 内容', () => {
      const content = '这是一段文本内容';

      wrapper = mount(TextContent, {
        props: { content },
      });

      expect(wrapper.text()).toBe(content);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '测试文本';

      wrapper = mount(TextContent, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(TextContent, {
        props: { content: '' },
      });

      expect(wrapper.find('.text-content').exists()).toBe(true);
      expect(wrapper.text()).toBe('');
    });

    it('应该处理特殊字符的 content', () => {
      const content = '<script>alert("xss")</script>';

      wrapper = mount(TextContent, {
        props: { content },
      });

      expect(wrapper.text()).toBe(content);
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理很长的 content', () => {
      const content = '这是一个非常长的文本内容'.repeat(50);

      wrapper = mount(TextContent, {
        props: { content },
      });

      expect(wrapper.text()).toBe(content);
    });

    it('应该处理包含换行的 content', () => {
      const content = '第一行\n第二行\n第三行';

      wrapper = mount(TextContent, {
        props: { content },
      });

      expect(wrapper.text()).toBe(content);
    });

    it('应该处理包含空格的 content', () => {
      const content = '  有前导空格和尾随空格  ';

      wrapper = mount(TextContent, {
        props: { content },
      });

      // .text() 会自动 trim，所以检查内容包含核心文本即可
      expect(wrapper.text()).toContain('有前导空格和尾随空格');
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', () => {
      wrapper = mount(TextContent, {
        props: { content: '文本' },
      });

      expect(wrapper.find('.text-content').exists()).toBe(true);
    });
  });
});
