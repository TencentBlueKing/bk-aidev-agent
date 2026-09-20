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

import AddMenuBtn from './add-menu-btn.vue';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('vue-tippy', () => ({ directive: {} }));

vi.mock('../../../lang/lang', () => ({ t: (key: string) => key }));

vi.mock('../../../icons', () => ({
  AddIcon: defineComponent({
    name: 'AddIcon',
    setup() {
      return () => h('span', { class: 'mock-add-icon' });
    },
  }),
}));

describe('AddMenuBtn', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('默认渲染 + 号图标', () => {
    wrapper = mount(AddMenuBtn);
    expect(wrapper.find('.ai-add-menu-btn').exists()).toBe(true);
    expect(wrapper.find('.mock-add-icon').exists()).toBe(true);
  });

  it('菜单展开时带 is-active', () => {
    wrapper = mount(AddMenuBtn, { props: { active: true } });
    expect(wrapper.find('.ai-add-menu-btn').classes()).toContain('is-active');
  });

  it('点击抛出 toggle', async () => {
    wrapper = mount(AddMenuBtn);
    await wrapper.find('.ai-add-menu-btn').trigger('click');
    expect(wrapper.emitted('toggle')).toHaveLength(1);
  });

  it('默认插槽可替换图标', () => {
    wrapper = mount(AddMenuBtn, { slots: { default: '<i class="custom-icon" />' } });
    expect(wrapper.find('.custom-icon').exists()).toBe(true);
    expect(wrapper.find('.mock-add-icon').exists()).toBe(false);
  });
});
