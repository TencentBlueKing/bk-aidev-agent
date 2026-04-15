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

// 2026-02-03: 已审查 ai-selection.vue 的 CSS 格式变化（box-shadow 和 transition 属性分行），不影响功能
// 2026-03-26: 已审查 ai-selection.vue 的 Props 顺序调整（excludeSelectors 按字母序前移），不影响功能

import { defineComponent, h, nextTick } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AiSelection from './ai-selection.vue';

import type { Shortcut } from '../../types';

// Mock vue-tippy
vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'TippyComponent',
    props: {
      arrow: { type: Boolean, default: false },
      interactive: { type: Boolean, default: false },
      offset: { type: Array, default: () => [0, 6] },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'click' },
    },
    emits: ['show', 'hidden'],
    setup(_, { slots }) {
      return () => h('div', { class: 'mock-tippy' }, [slots.default?.(), slots.content?.()]);
    },
  }),
  useTippy: vi.fn(() => ({
    show: vi.fn(),
    hide: vi.fn(),
  })),
}));

// Mock ShortcutBtn
vi.mock('../ai-shortcut/shortcut-btn/shortcut-btn.vue', () => ({
  default: defineComponent({
    name: 'ShortcutBtn',
    props: {
      shortcut: { type: Object, default: null },
      mode: { type: String, default: 'btn' },
    },
    emits: ['click'],
    setup(props, { emit, slots }) {
      return () =>
        h(
          'button',
          {
            class: 'mock-shortcut-btn',
            'data-shortcut-id': props.shortcut?.id,
            onClick: () => emit('click', props.shortcut),
          },
          [slots.default?.() || props.shortcut?.name],
        );
    },
  }),
}));

// Mock common constants
vi.mock('../../common', () => ({
  DEFAULT_SHORTCUTS: [{ id: 'ai-chat', name: '问问小鲸' }],
  SELECTION_Z_INDEX: 9999,
}));

// Mock icons
vi.mock('../../icons/messages', () => ({
  CollapsedIcon: defineComponent({
    name: 'CollapsedIcon',
    setup() {
      return () => h('span', { class: 'mock-collapsed-icon' });
    },
  }),
}));

// Helper function to create test shortcuts
const createShortcut = (id: string, name: string): Shortcut => ({
  id,
  name,
});

describe('AiSelection', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('visible 为 false 时不应该渲染弹窗', () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: false,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      expect(wrapper.find('.ai-selection-popover').exists()).toBe(false);
    });

    it('visible 为 true 时应该渲染弹窗', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      expect(wrapper.find('.ai-selection-popover').exists()).toBe(true);
    });

    it('应该渲染默认的快捷指令', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      expect(wrapper.find('.mock-shortcut-btn').exists()).toBe(true);
    });

    it('应该渲染自定义的快捷指令', async () => {
      const shortcuts = [createShortcut('custom-1', '自定义指令1'), createShortcut('custom-2', '自定义指令2')];

      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          shortcuts,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      const btns = wrapper.findAll('.mock-shortcut-btn');
      expect(btns.length).toBe(2);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 offset 属性', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          offset: 20,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      expect((wrapper.props() as Record<string, unknown>).offset).toBe(20);
    });

    it('应该正确接收 maxShortcutCount 属性', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          maxShortcutCount: 5,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      expect((wrapper.props() as Record<string, unknown>).maxShortcutCount).toBe(5);
    });

    it('maxShortcutCount 默认值应该为 3', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      expect((wrapper.props() as Record<string, unknown>).maxShortcutCount).toBe(3);
    });
  });

  describe('快捷指令数量限制测试', () => {
    it('当快捷指令数量小于等于 maxShortcutCount 时应该全部显示', async () => {
      const shortcuts = [createShortcut('1', '指令1'), createShortcut('2', '指令2')];

      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          shortcuts,
          maxShortcutCount: 3,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      const btns = wrapper.findAll('.mock-shortcut-btn');
      expect(btns.length).toBe(2);
    });

    it('当快捷指令数量大于 maxShortcutCount 时应该显示更多按钮', async () => {
      const shortcuts = [
        createShortcut('1', '指令1'),
        createShortcut('2', '指令2'),
        createShortcut('3', '指令3'),
        createShortcut('4', '指令4'),
      ];

      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          shortcuts,
          maxShortcutCount: 3,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      // 应该有 3 个主要按钮 + 1 个更多按钮 + 更多菜单中的 1 个
      expect(wrapper.find('.mock-tippy').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击快捷指令应该触发 selectShortcut 事件', async () => {
      const shortcuts = [createShortcut('test', '测试指令')];

      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          shortcuts,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      await wrapper.find('.mock-shortcut-btn').trigger('click');

      expect(wrapper.emitted('selectShortcut')).toBeTruthy();
    });
  });

  describe('Slot 测试', () => {
    it('应该支持自定义内容 slot', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        slots: {
          default: ({ shortcuts }: { shortcuts: Shortcut[] }) =>
            h('div', { class: 'custom-content' }, `Custom: ${shortcuts.length}`),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      expect(wrapper.find('.custom-content').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      expect(wrapper.find('.ai-selection-popover').exists()).toBe(true);
      expect(wrapper.find('.ai-selection-popover-content').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的快捷指令数组', async () => {
      wrapper = mount(AiSelection, {
        props: {
          visible: true,
          shortcuts: [],
          'onUpdate:visible': (val: boolean) => wrapper.setProps({ visible: val }),
        },
        global: {
          stubs: {
            Teleport: true,
          },
        },
      });

      await nextTick();
      expect(wrapper.find('.ai-selection-popover').exists()).toBe(true);
      expect(wrapper.findAll('.mock-shortcut-btn').length).toBe(0);
    });
  });
});
