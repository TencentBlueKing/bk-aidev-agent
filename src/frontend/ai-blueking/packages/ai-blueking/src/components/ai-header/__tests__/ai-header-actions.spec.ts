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

describe('AIHeader headerActions slot', () => {
  it('should not render header-actions when the slot is empty', () => {
    const wrapper = mount(AIHeader, {
      props: {
        showHistoryIcon: true,
        showCompressionIcon: true,
      },
    });

    expect(wrapper.find('.header-actions').exists()).toBe(false);
  });

  it('should render headerActions after history and before compression', () => {
    const wrapper = mount(AIHeader, {
      props: {
        showHistoryIcon: true,
        showNewChatIcon: true,
        showCompressionIcon: true,
        hasSessionContents: true,
      },
      slots: {
        headerActions: '<i class="bkai-icon custom-action-icon"></i>',
      },
    });

    expect(wrapper.find('.header-actions').exists()).toBe(true);
    expect(wrapper.find('.custom-action-icon').exists()).toBe(true);

    const children = wrapper.findAll('.right-section > *');
    const classLists = children.map(node => node.classes());

    const historyIndex = classLists.findIndex(classes => classes.includes('bkai-history'));
    const actionsIndex = classLists.findIndex(classes => classes.includes('header-actions'));
    const compressionIndex = classLists.findIndex(
      classes => classes.includes('bkai-yasuo') || classes.includes('bkai-morenchicun'),
    );
    const closeIndex = classLists.findIndex(classes => classes.includes('bkai-close-line-2'));

    expect(historyIndex).toBeGreaterThanOrEqual(0);
    expect(actionsIndex).toBe(historyIndex + 1);
    expect(compressionIndex).toBe(actionsIndex + 1);
    expect(closeIndex).toBe(compressionIndex + 1);
  });
});
