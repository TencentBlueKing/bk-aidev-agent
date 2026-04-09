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

import ScrollBtn from './scroll-btn.vue';

vi.mock('bkui-vue', () => ({
  Loading: defineComponent({
    name: 'Loading',
    props: { mode: String, size: String, theme: String },
    setup() {
      return () => h('span', { class: 'mock-bk-loading' });
    },
  }),
}));

describe('ScrollBtn', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ScrollBtn);

      expect(wrapper.find('.ai-scroll-btn').exists()).toBe(true);
    });

    it('应该正确渲染 title 属性', () => {
      const title = '滚动到底部';

      wrapper = mount(ScrollBtn, {
        props: { title },
      });

      expect(wrapper.text()).toContain(title);
    });

    it('title 为空时不应该显示文本内容', () => {
      wrapper = mount(ScrollBtn, {
        props: { title: '' },
      });

      expect(wrapper.text()).toBe('');
    });
  });

  describe('Props 测试', () => {
    it('应该接收 disabled 属性', () => {
      wrapper = mount(ScrollBtn, {
        props: { disabled: true },
      });

      expect((wrapper.props() as Record<string, unknown>).disabled).toBe(true);
    });

    it('disabled 默认值应该为 false', () => {
      wrapper = mount(ScrollBtn);

      expect((wrapper.props() as Record<string, unknown>).disabled).toBe(false);
    });

    it('应该接收 title 属性', () => {
      const title = '测试标题';

      wrapper = mount(ScrollBtn, {
        props: { title },
      });

      expect((wrapper.props() as Record<string, unknown>).title).toBe(title);
    });

    it('应该接收 loading 属性', () => {
      wrapper = mount(ScrollBtn, {
        props: { loading: true },
      });

      expect((wrapper.props() as Record<string, unknown>).loading).toBe(true);
    });

    it('loading 未设置时应为 false（Vue Boolean casting）', () => {
      wrapper = mount(ScrollBtn);

      expect((wrapper.props() as Record<string, unknown>).loading).toBe(false);
    });
  });

  describe('Loading 状态测试', () => {
    it('loading 为 true 时应该显示 Loading 组件', () => {
      wrapper = mount(ScrollBtn, {
        props: { loading: true },
      });

      expect(wrapper.find('.mock-bk-loading').exists()).toBe(true);
    });

    it('loading 为 true 时不应该渲染 icon slot', () => {
      wrapper = mount(ScrollBtn, {
        props: { loading: true },
        slots: {
          icon: () => h('span', { class: 'custom-icon' }, '🔽'),
        },
      });

      expect(wrapper.find('.custom-icon').exists()).toBe(false);
      expect(wrapper.find('.mock-bk-loading').exists()).toBe(true);
    });

    it('loading 为 true 时应该有 is-loading 类', () => {
      wrapper = mount(ScrollBtn, {
        props: { loading: true },
      });

      expect(wrapper.find('.ai-scroll-btn').classes()).toContain('is-loading');
    });

    it('loading 为 true 时点击不应该触发 click 事件', async () => {
      wrapper = mount(ScrollBtn, {
        props: { loading: true },
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeFalsy();
    });

    it('loading 为 false 时应该渲染 icon slot', () => {
      wrapper = mount(ScrollBtn, {
        props: { loading: false },
        slots: {
          icon: () => h('span', { class: 'custom-icon' }, '🔽'),
        },
      });

      expect(wrapper.find('.custom-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-bk-loading').exists()).toBe(false);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持 icon slot', () => {
      wrapper = mount(ScrollBtn, {
        slots: {
          icon: () => h('span', { class: 'custom-icon' }, '🔽'),
        },
      });

      expect(wrapper.find('.custom-icon').exists()).toBe(true);
      expect(wrapper.find('.custom-icon').text()).toBe('🔽');
    });

    it('应该支持 title slot 覆盖 title prop', () => {
      wrapper = mount(ScrollBtn, {
        props: { title: '默认标题' },
        slots: {
          title: () => h('span', { class: 'custom-title' }, '自定义标题'),
        },
      });

      expect(wrapper.find('.custom-title').exists()).toBe(true);
      expect(wrapper.find('.custom-title').text()).toBe('自定义标题');
      // 默认标题不应该显示
      expect(wrapper.text()).not.toContain('默认标题');
    });

    it('同时使用 icon 和 title slot', () => {
      wrapper = mount(ScrollBtn, {
        slots: {
          icon: () => h('span', { class: 'custom-icon' }, '⬇️'),
          title: () => h('span', { class: 'custom-title' }, '滚动'),
        },
      });

      expect(wrapper.find('.custom-icon').exists()).toBe(true);
      expect(wrapper.find('.custom-title').exists()).toBe(true);
    });

    it('没有 title slot 时应该显示 title prop', () => {
      const title = '底部';

      wrapper = mount(ScrollBtn, {
        props: { title },
      });

      expect(wrapper.text()).toContain(title);
    });
  });

  describe('事件测试', () => {
    it('点击时应该触发 click 事件', async () => {
      wrapper = mount(ScrollBtn);

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeTruthy();
      expect(wrapper.emitted('click')?.length).toBe(1);
    });

    it('多次点击应该触发多次 click 事件', async () => {
      wrapper = mount(ScrollBtn);

      await wrapper.trigger('click');
      await wrapper.trigger('click');
      await wrapper.trigger('click');

      expect(wrapper.emitted('click')?.length).toBe(3);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', () => {
      wrapper = mount(ScrollBtn);

      const btn = wrapper.find('.ai-scroll-btn');
      expect(btn.exists()).toBe(true);
    });

    it('disabled 时应该有 is-disabled 类', () => {
      wrapper = mount(ScrollBtn, {
        props: { disabled: true },
      });

      expect(wrapper.find('.ai-scroll-btn').classes()).toContain('is-disabled');
    });

    it('disabled 时点击不应该触发 click 事件', async () => {
      wrapper = mount(ScrollBtn, {
        props: { disabled: true },
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeFalsy();
    });
  });

  describe('边界情况测试', () => {
    it('应该处理 undefined title', () => {
      wrapper = mount(ScrollBtn, {
        props: { title: undefined },
      });

      expect(wrapper.find('.ai-scroll-btn').exists()).toBe(true);
    });

    it('应该处理特殊字符的 title', () => {
      const specialTitle = '<script>alert("xss")</script>';

      wrapper = mount(ScrollBtn, {
        props: { title: specialTitle },
      });

      // Vue 会自动转义 HTML，所以应该是安全的文本
      expect(wrapper.text()).toContain(specialTitle);
      // 确保没有实际执行脚本
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理很长的 title', () => {
      const longTitle = '这是一个非常长的标题'.repeat(10);

      wrapper = mount(ScrollBtn, {
        props: { title: longTitle },
      });

      expect(wrapper.text()).toContain(longTitle);
    });
  });
});
