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

import ToolMessage from './tool-message.vue';

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock DescPanel
vi.mock('../../tool-call/desc-panel/desc-panel.vue', () => ({
  default: defineComponent({
    name: 'DescPanel',
    props: {
      desc: { type: String, default: '' },
      title: { type: String, default: '' },
    },
    setup(props) {
      return () =>
        h('div', { class: 'mock-desc-panel' }, [
          h('div', { class: 'mock-desc-panel-title' }, props.title),
          h('div', { class: 'mock-desc-panel-desc' }, props.desc),
        ]);
    },
  }),
}));

describe('ToolMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ToolMessage, {
        props: {
          content: '工具返回内容',
        },
      });

      expect(wrapper.find('.tool-message').exists()).toBe(true);
    });

    it('应该渲染 DescPanel 组件', () => {
      wrapper = mount(ToolMessage, {
        props: {
          content: '工具返回内容',
        },
      });

      expect(wrapper.find('.mock-desc-panel').exists()).toBe(true);
    });

    it('应该正确传递 content 到 DescPanel', () => {
      const content = '这是工具的返回内容';

      wrapper = mount(ToolMessage, {
        props: { content },
      });

      expect(wrapper.find('.mock-desc-panel-desc').text()).toBe(content);
    });

    it('应该正确传递标题到 DescPanel', () => {
      wrapper = mount(ToolMessage, {
        props: {
          content: '内容',
        },
      });

      expect(wrapper.find('.mock-desc-panel-title').text()).toBe('返回内容');
    });
  });

  describe('Error 处理测试', () => {
    it('有 error 时应该显示 error 内容', () => {
      const error = '工具执行出错';

      wrapper = mount(ToolMessage, {
        props: {
          content: '',
          error,
        },
      });

      expect(wrapper.find('.mock-desc-panel-desc').text()).toBe(error);
    });

    it('有 content 和 error 时应该优先显示 content', () => {
      const content = '工具返回内容';
      const error = '工具执行出错';

      wrapper = mount(ToolMessage, {
        props: {
          content,
          error,
        },
      });

      expect(wrapper.find('.mock-desc-panel-desc').text()).toBe(content);
    });

    it('error 为非 string 类型时不应传递给 DescPanel', () => {
      wrapper = mount(ToolMessage, {
        props: {
          content: '',
          error: { message: '错误对象' } as unknown as string,
        },
      });

      expect(wrapper.find('.mock-desc-panel-desc').text()).toBe('');
    });

    it('error 为 string 且 content 为空时应显示 error', () => {
      const error = '字符串错误信息';

      wrapper = mount(ToolMessage, {
        props: {
          content: '',
          error,
        },
      });

      expect(wrapper.find('.mock-desc-panel-desc').text()).toBe(error);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '测试内容';

      wrapper = mount(ToolMessage, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });

    it('应该正确接收 error 属性', () => {
      const error = '错误信息';

      wrapper = mount(ToolMessage, {
        props: { error },
      });

      expect((wrapper.props() as { error: string }).error).toBe(error);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(ToolMessage, {
        props: {
          content: '',
        },
      });

      expect(wrapper.find('.tool-message').exists()).toBe(true);
    });

    it('应该处理 undefined content', () => {
      wrapper = mount(ToolMessage, {
        props: {},
      });

      expect(wrapper.find('.tool-message').exists()).toBe(true);
    });

    it('应该处理特殊字符的 content', () => {
      const content = '<script>alert("xss")</script>';

      wrapper = mount(ToolMessage, {
        props: { content },
      });

      expect(wrapper.find('.mock-desc-panel-desc').text()).toBe(content);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', () => {
      wrapper = mount(ToolMessage, {
        props: {
          content: '内容',
        },
      });

      expect(wrapper.find('.tool-message').exists()).toBe(true);
    });
  });
});
