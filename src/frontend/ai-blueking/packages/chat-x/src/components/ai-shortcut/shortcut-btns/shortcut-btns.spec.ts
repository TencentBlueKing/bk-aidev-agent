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

import { defineComponent, h, nextTick, ref } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ShortcutBtns from './shortcut-btns.vue';

import type { Shortcut } from '../../../types';

// Mock vue-tippy
vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    props: {
      appendTo: { type: Object, default: null },
      arrow: { type: Boolean, default: false },
      interactive: { type: Boolean, default: false },
      offset: { type: Array, default: () => [0, 6] },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'click' },
      zIndex: { type: Number, default: 9999 },
    },
    emits: ['show', 'hidden'],
    setup(_, { slots, expose }) {
      const show = vi.fn();
      const hide = vi.fn();
      expose({ show, hide });
      return () => h('div', { class: 'mock-tippy' }, [slots.default?.(), slots.content?.()]);
    },
  }),
  useTippy: vi.fn(() => ({
    show: vi.fn(),
    hide: vi.fn(),
  })),
}));

// Mock ShortcutBtn
vi.mock('../shortcut-btn/shortcut-btn.vue', () => ({
  default: defineComponent({
    name: 'ShortcutBtn',
    props: {
      shortcut: { type: Object, default: null },
      mode: { type: String, default: 'btn' },
    },
    emits: ['click'],
    setup(props, { emit, slots, expose }) {
      const el = ref<HTMLElement>();
      expose({
        get $el() {
          return el.value;
        },
      });
      return () =>
        h(
          'button',
          {
            ref: el,
            class: 'mock-shortcut-btn',
            'data-shortcut-id': props.shortcut?.id,
            'data-mode': props.mode,
            onClick: () => emit('click', props.shortcut),
          },
          [slots.default?.() || props.shortcut?.name],
        );
    },
  }),
}));

// Mock composables
vi.mock('../../../composables/use-observer-visible-list', () => ({
  useObserverVisibleList: <T>(_containerRef: unknown, _itemRefs: unknown, options: { items: { value: T[] } }) => ({
    visibleItems: ref(options.items.value),
  }),
}));

// Mock common constants
vi.mock('../../../common', () => ({
  SHORTCUT_MENU_Z_INDEX: 9999,
}));

// Mock icons
vi.mock('../../../icons/shortcuts', () => ({
  MoreAgentIcon: defineComponent({
    name: 'MoreAgentIcon',
    setup() {
      return () => h('span', { class: 'mock-more-agent-icon' });
    },
  }),
}));

// Mock lang
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Helper function to create test shortcuts
const createShortcut = (id: string, name: string): Shortcut => ({
  id,
  name,
});

describe('ShortcutBtns', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      const shortcuts = [createShortcut('1', '指令1')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      expect(wrapper.find('.shortcut-btns').exists()).toBe(true);
    });

    it('应该渲染所有快捷指令按钮', () => {
      const shortcuts = [createShortcut('1', '指令1'), createShortcut('2', '指令2'), createShortcut('3', '指令3')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      const btns = wrapper.findAll('.mock-shortcut-btn');
      expect(btns.length).toBe(3);
    });

    it('应该为每个按钮设置正确的 shortcut 数据', () => {
      const shortcuts = [createShortcut('test-1', '测试1'), createShortcut('test-2', '测试2')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      const btns = wrapper.findAll('.mock-shortcut-btn');
      expect(btns[0].attributes('data-shortcut-id')).toBe('test-1');
      expect(btns[1].attributes('data-shortcut-id')).toBe('test-2');
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 shortcuts 属性', () => {
      const shortcuts = [createShortcut('1', '指令1'), createShortcut('2', '指令2')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      expect((wrapper.props() as { shortcuts: Shortcut[] }).shortcuts).toEqual(shortcuts);
    });
  });

  describe('事件测试', () => {
    it('点击快捷指令应该触发 selectShortcut 事件', async () => {
      const shortcuts = [createShortcut('test', '测试')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      await wrapper.find('.mock-shortcut-btn').trigger('click');

      expect(wrapper.emitted('selectShortcut')).toBeTruthy();
      expect(wrapper.emitted('selectShortcut')?.[0]).toEqual([shortcuts[0]]);
    });

    it('点击不同的快捷指令应该传递对应的 shortcut', async () => {
      const shortcuts = [createShortcut('first', '第一个'), createShortcut('second', '第二个')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      const btns = wrapper.findAll('.mock-shortcut-btn');
      await btns[1].trigger('click');

      expect(wrapper.emitted('selectShortcut')?.[0]).toEqual([shortcuts[1]]);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的容器类名', () => {
      const shortcuts = [createShortcut('1', '指令1')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      expect(wrapper.find('.shortcut-btns').exists()).toBe(true);
    });

    it('每个按钮应该有 shortcut-btns-item 类名', () => {
      const shortcuts = [createShortcut('1', '指令1')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      expect(wrapper.find('.shortcut-btns-item').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的快捷指令数组', () => {
      wrapper = mount(ShortcutBtns, {
        props: { shortcuts: [] },
      });

      expect(wrapper.find('.shortcut-btns').exists()).toBe(true);
      expect(wrapper.findAll('.mock-shortcut-btn').length).toBe(0);
    });

    it('应该处理单个快捷指令', () => {
      const shortcuts = [createShortcut('only', '唯一指令')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      expect(wrapper.findAll('.mock-shortcut-btn').length).toBe(1);
    });

    it('应该处理大量快捷指令', () => {
      const shortcuts = Array.from({ length: 20 }, (_, i) => createShortcut(`id-${i}`, `指令${i}`));

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts },
      });

      expect(wrapper.find('.shortcut-btns').exists()).toBe(true);
    });
  });

  describe('快捷指令更新测试', () => {
    it('更新 shortcuts 属性时应该重新渲染', async () => {
      const shortcuts1 = [createShortcut('1', '指令1')];
      const shortcuts2 = [createShortcut('1', '指令1'), createShortcut('2', '指令2'), createShortcut('3', '指令3')];

      wrapper = mount(ShortcutBtns, {
        props: { shortcuts: shortcuts1 },
      });

      // 初始状态应该有按钮
      expect(wrapper.findAll('.mock-shortcut-btn').length).toBeGreaterThanOrEqual(1);

      await wrapper.setProps({ shortcuts: shortcuts2 });
      await nextTick();

      // 更新后按钮数量应该增加
      expect(wrapper.findAll('.mock-shortcut-btn').length).toBeGreaterThanOrEqual(3);
    });
  });
});
