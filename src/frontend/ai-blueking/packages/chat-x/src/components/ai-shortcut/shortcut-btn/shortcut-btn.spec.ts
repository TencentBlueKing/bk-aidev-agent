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

import { defineComponent, h, nextTick } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ShortcutBtn from './shortcut-btn.vue';

import type { Shortcut } from '../../../types';

// Mock AgentIcon
vi.mock('../../../icons', () => ({
  AgentIcon: defineComponent({
    name: 'AgentIcon',
    setup() {
      return () => h('span', { class: 'mock-agent-icon ai-shortcut-btn-icon' });
    },
  }),
}));

// Helper function to create test shortcuts
const createShortcut = (id: string, name: string, icon?: string): Shortcut => ({
  id,
  name,
  icon,
});

describe('ShortcutBtn', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ShortcutBtn);

      expect(wrapper.find('.ai-shortcut-btn').exists()).toBe(true);
    });

    it('应该正确渲染 shortcut 的 name', () => {
      const shortcut = createShortcut('test', '测试按钮');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.text()).toContain('测试按钮');
    });

    it('无 shortcut 时应该渲染空内容', () => {
      wrapper = mount(ShortcutBtn);

      expect(wrapper.find('.ai-shortcut-btn').exists()).toBe(true);
    });

    it('应该正确渲染字符串类型的图标', () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        icon: 'icon-test',
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.icon-test').exists()).toBe(true);
    });

    it('应该正确渲染 URL 类型的图标', () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        icon: 'https://example.com/icon.png',
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      const img = wrapper.find('img');
      expect(img.exists()).toBe(true);
      expect(img.attributes('src')).toBe('https://example.com/icon.png');
    });

    it('HTTP 图标加载失败时应回退显示 AgentIcon', async () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        icon: 'https://example.com/icon.png',
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      await wrapper.find('img').trigger('error');
      await nextTick();
      expect(wrapper.find('.mock-agent-icon').exists()).toBe(true);
    });

    it('shortcut.icon 切换时应重置错误状态并重新显示 img', async () => {
      wrapper = mount(ShortcutBtn, {
        props: {
          shortcut: {
            id: 'test',
            name: '测试',
            icon: 'https://example.com/bad.png',
          },
        },
      });

      await wrapper.find('img').trigger('error');
      await nextTick();
      expect(wrapper.find('.mock-agent-icon').exists()).toBe(true);

      await wrapper.setProps({
        shortcut: {
          id: 'test',
          name: '测试',
          icon: 'https://example.com/good.png',
        },
      });
      await nextTick();
      expect(wrapper.find('img').exists()).toBe(true);
      expect(wrapper.find('img').attributes('src')).toBe('https://example.com/good.png');
    });

    it('应该正确渲染函数类型的图标', () => {
      const MockIcon = defineComponent({
        name: 'MockIcon',
        setup() {
          return () => h('span', { class: 'mock-icon' });
        },
      });

      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        icon: () => MockIcon,
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.mock-icon').exists()).toBe(true);
    });

    it('当 shortcut 无 icon 且无 components 时应该显示默认 AgentIcon', () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.mock-agent-icon').exists()).toBe(true);
    });

    it('当 shortcut 有 icon 时不应该显示默认 AgentIcon', () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        icon: 'icon-test',
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.mock-agent-icon').exists()).toBe(false);
    });

    it('当 shortcut 有 components 时不应该显示默认 AgentIcon', () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        components: [{ id: 'comp1', name: 'Component 1' }],
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.mock-agent-icon').exists()).toBe(false);
    });

    it('当 shortcut.components 为空数组时应该显示默认 AgentIcon', () => {
      const shortcut: Shortcut = {
        id: 'test',
        name: '测试',
        components: [],
      };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.mock-agent-icon').exists()).toBe(true);
    });
  });

  describe('Mode 测试', () => {
    it('默认 mode 应该是 btn', () => {
      wrapper = mount(ShortcutBtn);

      expect(wrapper.find('.ai-shortcut-btn').classes()).not.toContain('is-menu-mode');
    });

    it('mode 为 menu 时应该添加 is-menu-mode 类', () => {
      const shortcut = createShortcut('test', '测试');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut, mode: 'menu' },
      });

      expect(wrapper.find('.ai-shortcut-btn').classes()).toContain('is-menu-mode');
    });

    it('mode 为 btn 时不应该添加 is-menu-mode 类', () => {
      const shortcut = createShortcut('test', '测试');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut, mode: 'btn' },
      });

      expect(wrapper.find('.ai-shortcut-btn').classes()).not.toContain('is-menu-mode');
    });
  });

  describe('事件测试', () => {
    it('点击时应该触发 click 事件并传递 shortcut', async () => {
      const shortcut = createShortcut('test', '测试');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeTruthy();
      expect(wrapper.emitted('click')?.[0]).toEqual([shortcut]);
    });

    it('无 shortcut 时点击应该传递 undefined', async () => {
      wrapper = mount(ShortcutBtn);

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeTruthy();
      expect(wrapper.emitted('click')?.[0]).toEqual([undefined]);
    });

    it('多次点击应该触发多次 click 事件', async () => {
      const shortcut = createShortcut('test', '测试');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      await wrapper.trigger('click');
      await wrapper.trigger('click');
      await wrapper.trigger('click');

      expect(wrapper.emitted('click')?.length).toBe(3);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot 覆盖内容', () => {
      wrapper = mount(ShortcutBtn, {
        slots: {
          default: () => h('span', { class: 'custom-content' }, '自定义内容'),
        },
      });

      expect(wrapper.find('.custom-content').exists()).toBe(true);
      expect(wrapper.find('.custom-content').text()).toBe('自定义内容');
    });

    it('使用默认 slot 时应该忽略 shortcut 内容', () => {
      const shortcut = createShortcut('test', '测试按钮');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
        slots: {
          default: () => h('span', { class: 'custom-content' }, '自定义'),
        },
      });

      expect(wrapper.text()).not.toContain('测试按钮');
      expect(wrapper.find('.custom-content').exists()).toBe(true);
    });

    it('应该支持 append slot', () => {
      const shortcut = createShortcut('test', '测试按钮');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
        slots: {
          append: () => h('span', { class: 'append-content' }, '追加内容'),
        },
      });

      expect(wrapper.find('.append-content').exists()).toBe(true);
      expect(wrapper.find('.append-content').text()).toBe('追加内容');
    });

    it('append slot 应该渲染在按钮内容之后', () => {
      const shortcut = createShortcut('test', '测试按钮');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
        slots: {
          append: () => h('span', { class: 'append-icon' }, 'X'),
        },
      });

      // 确保按钮文本和 append 内容都存在
      expect(wrapper.text()).toContain('测试按钮');
      expect(wrapper.find('.append-icon').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 shortcut 属性', () => {
      const shortcut = createShortcut('test-id', '测试名称');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect((wrapper.props() as { shortcut: Shortcut }).shortcut).toEqual(shortcut);
    });

    it('应该正确接收 mode 属性', () => {
      wrapper = mount(ShortcutBtn, {
        props: { mode: 'menu' },
      });

      expect((wrapper.props() as { mode: string }).mode).toBe('menu');
    });
  });

  describe('Expose 测试', () => {
    it('应该暴露 $el 属性', () => {
      wrapper = mount(ShortcutBtn);

      const vm = wrapper.vm as unknown as { $el: HTMLElement };
      expect(vm.$el).toBeDefined();
      expect(vm.$el).toBeInstanceOf(HTMLElement);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 name 的 shortcut', () => {
      const shortcut: Shortcut = { id: 'test', name: '' };

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.find('.ai-shortcut-btn').exists()).toBe(true);
    });

    it('应该处理特殊字符的 name', () => {
      const shortcut = createShortcut('test', '<script>alert("xss")</script>');

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      // Vue 会自动转义 HTML
      expect(wrapper.text()).toContain('<script>alert("xss")</script>');
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理很长的 name', () => {
      const longName = '这是一个非常长的名称'.repeat(10);
      const shortcut = createShortcut('test', longName);

      wrapper = mount(ShortcutBtn, {
        props: { shortcut },
      });

      expect(wrapper.text()).toContain(longName);
    });
  });

  describe('样式测试', () => {
    it('应该是一个 button 元素', () => {
      wrapper = mount(ShortcutBtn);

      expect(wrapper.element.tagName.toLowerCase()).toBe('button');
    });

    it('应该具有正确的基础类名', () => {
      wrapper = mount(ShortcutBtn);

      expect(wrapper.find('.ai-shortcut-btn').exists()).toBe(true);
    });
  });
});
