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
import { afterEach, describe, expect, it, vi } from 'vitest';

import InputMenuPanel from './input-menu-panel.vue';

import type { IInputMenuGroup } from '../../../types/input-menu';

vi.mock('../../../lang/lang', () => ({ t: (key: string) => key }));

vi.mock('vue-tippy', () => ({ directive: {} }));

vi.mock('../../../icons', () => ({
  ArrowLeftIcon: defineComponent({
    name: 'ArrowLeftIcon',
    setup(_, { attrs }) {
      return () => h('span', { class: ['mock-arrow-left-icon', attrs.class] });
    },
  }),
}));

vi.mock('../../../directives', () => ({ OverflowTips: {} }));

vi.mock('../../resource-icon', () => ({
  ResourceIcon: defineComponent({
    name: 'ResourceIcon',
    setup() {
      return () => h('span', { class: 'mock-resource-icon' });
    },
  }),
}));

const buildGroup = (overrides: Partial<IInputMenuGroup> = {}): IInputMenuGroup => ({
  key: 'skill',
  name: 'Skill',
  divided: false,
  expanded: false,
  restCount: 0,
  items: [
    { id: 's1', type: 'skill', name: 'Hangzhou' },
    { id: 's2', type: 'skill', name: 'Guangzhou' },
  ],
  ...overrides,
});

describe('InputMenuPanel', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('按分组渲染标题与选项', () => {
    const group = buildGroup();
    wrapper = mount(InputMenuPanel, { props: { groups: [group], flatItems: group.items } });
    expect(wrapper.find('.ai-input-menu-title').text()).toBe('Skill');
    expect(wrapper.findAll('.ai-input-menu-option')).toHaveLength(2);
  });

  it('分组无数据时展示暂无数据', () => {
    const group = buildGroup({ key: 'artifact', name: '会话产物', items: [] });
    wrapper = mount(InputMenuPanel, { props: { groups: [group], flatItems: [] } });
    expect(wrapper.find('.ai-input-menu-empty').text()).toBe('暂无数据');
  });

  it('有折叠条数时展示「更多 +N」，展开后展示「收起 +N」', async () => {
    wrapper = mount(InputMenuPanel, {
      props: { groups: [buildGroup({ restCount: 4 })], flatItems: [] },
    });
    expect(wrapper.find('.ai-input-menu-toggle').text()).toBe('更多 +4');

    await wrapper.setProps({ groups: [buildGroup({ restCount: 4, expanded: true })] });
    expect(wrapper.find('.ai-input-menu-toggle').text()).toBe('收起 +4');
    expect(wrapper.find('.ai-input-menu-toggle-icon').classes()).toContain('is-expanded');
  });

  it('点击折叠行抛出 toggleGroup', async () => {
    wrapper = mount(InputMenuPanel, {
      props: { groups: [buildGroup({ restCount: 2 })], flatItems: [] },
    });
    await wrapper.find('.ai-input-menu-toggle').trigger('click');
    expect(wrapper.emitted('toggleGroup')?.[0]).toEqual(['skill']);
  });

  it('点击选项抛出 select', async () => {
    const group = buildGroup();
    wrapper = mount(InputMenuPanel, { props: { groups: [group], flatItems: group.items } });
    await wrapper.findAll('.ai-input-menu-option')[1].trigger('click');
    expect(wrapper.emitted('select')?.[0]).toEqual([group.items[1]]);
  });

  it('禁用项点击不抛出 select', async () => {
    const group = buildGroup({ items: [{ id: 's1', type: 'skill', name: 'Hangzhou', disabled: true }] });
    wrapper = mount(InputMenuPanel, { props: { groups: [group], flatItems: [] } });
    await wrapper.find('.ai-input-menu-option').trigger('click');
    expect(wrapper.emitted('select')).toBeUndefined();
  });

  it('需要分隔线的分组带 is-divided', () => {
    wrapper = mount(InputMenuPanel, {
      props: { groups: [buildGroup({ key: 'add', name: '添加', divided: true })], flatItems: [] },
    });
    expect(wrapper.find('.ai-input-menu-group').classes()).toContain('is-divided');
  });

  it('按下 Esc 抛出 close', () => {
    wrapper = mount(InputMenuPanel, { props: { groups: [buildGroup()], flatItems: [] } });
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(wrapper.emitted('close')).toHaveLength(1);
  });
});
