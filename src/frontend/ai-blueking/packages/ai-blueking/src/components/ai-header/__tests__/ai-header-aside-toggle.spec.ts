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

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

vi.mock('bkui-vue', () => ({
  Input: defineComponent({ name: 'BkInput', template: '<input />' }),
  Loading: defineComponent({ name: 'Loading', template: '<span />' }),
  bkTooltips: {},
  Message: vi.fn(),
}));

vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    setup(_, { slots }) {
      return () => h('div', [slots.default?.(), slots.content?.()]);
    },
  }),
  directive: {},
}));

vi.mock('../../../lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../../assets/images/avatar.png', () => ({
  default: 'avatar.png',
}));

vi.mock('../history-dropdown/use-history-dropdown', () => ({
  useHistoryDropdown: vi.fn(),
}));

vi.mock('@blueking/chat-x', async importOriginal => {
  const actual = await importOriginal<typeof import('@blueking/chat-x')>();
  return {
    ...actual,
    RenderMode: { Chat: 'chat', Share: 'share', Test: 'test' },
    CollapsedAsideIcon: defineComponent({
      name: 'CollapsedAsideIcon',
      setup() {
        return () => h('svg', { class: 'collapsed-aside-icon' });
      },
    }),
  };
});

import AIHeader from '../index.vue';

describe('AIHeader aside toggle', () => {
  it('should render the aside toggle immediately left of the compression icon', () => {
    const wrapper = mount(AIHeader, {
      props: {
        asideCollapsed: true,
        showAsideToggle: true,
        showCompressionIcon: true,
      },
    });

    const icons = wrapper.findAll('.right-section > *');
    const toggleIndex = icons.findIndex(node => node.classes().includes('aside-toggle'));
    const compressionIndex = icons.findIndex(
      node => node.classes().includes('bkai-yasuo') || node.classes().includes('bkai-morenchicun'),
    );

    expect(toggleIndex).toBeGreaterThanOrEqual(0);
    expect(compressionIndex).toBe(toggleIndex + 1);
  });

  it('should emit toggle-aside on click', async () => {
    const wrapper = mount(AIHeader, {
      props: {
        asideCollapsed: true,
        showAsideToggle: true,
      },
    });

    await wrapper.find('.aside-toggle').trigger('click');
    expect(wrapper.emitted('toggle-aside')).toHaveLength(1);
  });

  it('should hide the toggle when showAsideToggle is false', () => {
    const wrapper = mount(AIHeader, {
      props: {
        showAsideToggle: false,
        showCompressionIcon: true,
      },
    });

    expect(wrapper.find('.aside-toggle').exists()).toBe(false);
  });
});
