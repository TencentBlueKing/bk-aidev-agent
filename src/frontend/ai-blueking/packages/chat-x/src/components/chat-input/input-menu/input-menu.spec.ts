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
import { afterEach, describe, expect, it, vi } from 'vitest';

import { EDITOR_MENU_Z_INDEX } from '../../../common';
import InputMenu from './input-menu.vue';

import type { IInputMenuGroup, IInputMenuItem } from '../../../types/input-menu';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    props: {
      appendTo: { type: [Function, String, Object], default: undefined },
      arrow: { type: Boolean, default: true },
      duration: { type: [Number, Array], default: undefined },
      hideOnClick: { type: [Boolean, String], default: true },
      interactive: { type: Boolean, default: false },
      maxWidth: { type: [String, Number], default: 350 },
      offset: { type: Array, default: () => [0, 0] },
      onClickOutside: { type: Function, default: undefined },
      placement: { type: String, default: 'top' },
      popperOptions: { type: Object, default: undefined },
      tag: { default: undefined },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'mouseenter focus' },
      zIndex: { type: Number, default: undefined },
    },
    setup() {
      // 用 setup 返回值挂到实例上，VTU 的 vm / 父组件 ref 才能拿到 show/hide
      return { show: vi.fn(), hide: vi.fn() };
    },
    render() {
      return h('div', { class: 'mock-tippy' }, [
        this.$slots.default?.(),
        h('div', { class: 'mock-tippy-content' }, this.$slots.content?.()),
      ]);
    },
  }),
}));

vi.mock('./input-menu-panel.vue', () => ({
  default: defineComponent({
    name: 'InputMenuPanel',
    props: {
      flatItems: { type: Array, default: () => [] },
      groups: { type: Array, default: () => [] },
    },
    emits: ['select', 'toggleGroup', 'close'],
    setup(props) {
      return () =>
        h('div', {
          class: 'mock-input-menu-panel',
          'data-group-count': String((props.groups as unknown[]).length),
        });
    },
  }),
}));

const groups: IInputMenuGroup[] = [
  {
    key: 'skill',
    name: 'Skill',
    divided: false,
    expanded: false,
    restCount: 0,
    items: [{ id: 's1', type: 'skill', name: 'Code Review' }],
  },
];
const flatItems: IInputMenuItem[] = groups[0].items;

const mountMenu = (visible = true, extra: Record<string, unknown> = {}) =>
  mount(InputMenu, {
    props: { visible, groups, flatItems, ...extra },
    slots: { default: '<div class="mock-chat-input">input</div>' },
  });

describe('InputMenu', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('应把默认 slot 作为 tippy 的 reference 渲染', () => {
    wrapper = mountMenu(false);
    expect(wrapper.find('.mock-chat-input').exists()).toBe(true);
  });

  it('visible 为 false 时不渲染菜单面板', () => {
    wrapper = mountMenu(false);
    expect(wrapper.find('.mock-input-menu-panel').exists()).toBe(false);
  });

  it('visible 为 true 时应渲染面板并传入分组数据', () => {
    wrapper = mountMenu(true);
    expect(wrapper.find('.mock-input-menu-panel').exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'InputMenuPanel' }).props('groups')).toEqual(groups);
    expect(wrapper.findComponent({ name: 'InputMenuPanel' }).props('flatItems')).toEqual(flatItems);
  });

  it('Tippy 应为手动触发、贴着输入框上方且与框体等宽', () => {
    wrapper = mountMenu(true);
    const tippy = wrapper.findComponent({ name: 'Tippy' });
    expect(tippy.props('trigger')).toBe('manual');
    expect(tippy.props('placement')).toBe('top');
    expect(tippy.props('interactive')).toBe(true);
    expect(tippy.props('hideOnClick')).toBe(false);
    expect(tippy.props('maxWidth')).toBe('none');
    expect(tippy.props('offset')).toEqual([0, 8]);
    expect(tippy.props('theme')).toBe('ai-input-menu');
    expect(tippy.props('zIndex')).toBe(EDITOR_MENU_Z_INDEX);
    expect(tippy.props('tag')).toBe('div');
    const modifiers = (tippy.props('popperOptions') as { modifiers: { name: string }[] }).modifiers;
    expect(modifiers.some(modifier => modifier.name === 'sameWidth')).toBe(true);
  });

  it('visible 变为 true 时应 show，变为 false 时应 hide', async () => {
    wrapper = mountMenu(false);
    const tippy = wrapper.findComponent({ name: 'Tippy' });
    await wrapper.setProps({ visible: true });
    await nextTick();
    expect(tippy.vm.show).toHaveBeenCalled();
    await wrapper.setProps({ visible: false });
    await nextTick();
    expect(tippy.vm.hide).toHaveBeenCalled();
  });

  it('点击浮层外部应抛出 close', () => {
    wrapper = mountMenu(true);
    const onClickOutside = wrapper.findComponent({ name: 'Tippy' }).props('onClickOutside') as () => void;
    onClickOutside();
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('面板 select / toggleGroup / close 应向外转发', async () => {
    wrapper = mountMenu(true);
    const panel = wrapper.findComponent({ name: 'InputMenuPanel' });
    await panel.vm.$emit('select', flatItems[0]);
    await panel.vm.$emit('toggleGroup', 'skill');
    await panel.vm.$emit('close');
    expect(wrapper.emitted('select')?.[0]).toEqual([flatItems[0]]);
    expect(wrapper.emitted('toggleGroup')?.[0]).toEqual(['skill']);
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('tippyOptions.appendTo 应覆盖默认挂载点', () => {
    const host = document.createElement('div');
    wrapper = mountMenu(true, { tippyOptions: { appendTo: host } });
    expect(wrapper.findComponent({ name: 'Tippy' }).props('appendTo')).toBe(host);
  });
});
