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

import SelectionFooter from './selection-footer.vue';

vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    name: 'ButtonComponent',
    props: {
      disabled: { type: Boolean, default: false },
      loading: { type: Boolean, default: false },
      size: { type: String, default: 'medium' },
      theme: { type: String, default: 'default' },
    },
    emits: ['click'],
    setup(props, { slots, emit }) {
      return () =>
        h(
          'button',
          {
            class: ['mock-button', props.theme !== 'default' && `mock-button-${props.theme}`],
            disabled: props.disabled,
            onClick: () => !props.disabled && emit('click'),
          },
          slots.default?.(),
        );
    },
  }),
  Checkbox: defineComponent({
    name: 'CheckboxComponent',
    props: {
      modelValue: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () =>
        h('label', { class: 'mock-checkbox' }, [
          h('input', {
            type: 'checkbox',
            checked: props.modelValue,
            onChange: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).checked),
          }),
        ]);
    },
  }),
}));

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

describe('SelectionFooter', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      expect(wrapper.find('.ai-selection-footer').exists()).toBe(true);
    });

    it('应该渲染全选 Checkbox', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      expect(wrapper.find('.mock-checkbox').exists()).toBe(true);
    });

    it('应该渲染取消和确定按钮', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      const buttons = wrapper.findAll('.mock-button');
      expect(buttons.length).toBe(2);
    });

    it('应该显示全选文本', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      expect(wrapper.find('.select-all-text').text()).toBe('全选');
    });
  });

  describe('Props 测试', () => {
    it('isAllSelected 为 true 时 Checkbox 应为选中状态', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: true, selectedCount: 3 },
      });

      const checkbox = wrapper.find('input[type="checkbox"]');
      expect((checkbox.element as HTMLInputElement).checked).toBe(true);
    });

    it('selectedCount 为 0 时确定按钮应该禁用', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      const confirmBtn = wrapper.find('.mock-button-primary');
      expect(confirmBtn.attributes('disabled')).toBeDefined();
    });

    it('selectedCount 大于 0 时确定按钮应该可用', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 2 },
      });

      const confirmBtn = wrapper.find('.mock-button-primary');
      expect(confirmBtn.attributes('disabled')).toBeUndefined();
    });

    it('loading 为 true 时取消按钮应该禁用', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 1, loading: true },
      });

      const buttons = wrapper.findAll('.mock-button');
      const cancelBtn = buttons.find(btn => !btn.classes().includes('mock-button-primary'));
      expect(cancelBtn?.attributes('disabled')).toBeDefined();
    });
  });

  describe('事件测试', () => {
    it('点击取消按钮应该触发 cancel 事件', async () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 1 },
      });

      const cancelBtn = wrapper.findAll('.mock-button').find(btn => !btn.classes().includes('mock-button-primary'));
      await cancelBtn?.trigger('click');

      expect(wrapper.emitted('cancel')).toBeTruthy();
    });

    it('点击确定按钮应该触发 confirm 事件', async () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 1 },
      });

      const confirmBtn = wrapper.find('.mock-button-primary');
      await confirmBtn.trigger('click');

      expect(wrapper.emitted('confirm')).toBeTruthy();
    });

    it('切换 Checkbox 应该触发 toggle-all 事件', async () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      const checkbox = wrapper.find('input[type="checkbox"]');
      await checkbox.setValue(true);

      expect(wrapper.emitted('toggle-all')).toBeTruthy();
      expect(wrapper.emitted('toggle-all')?.[0]).toEqual([true]);
    });
  });

  describe('边界情况测试', () => {
    it('loading 未设置时组件应正常渲染', () => {
      wrapper = mount(SelectionFooter, {
        props: { isAllSelected: false, selectedCount: 0 },
      });

      expect(wrapper.find('.ai-selection-footer').exists()).toBe(true);
    });
  });
});
