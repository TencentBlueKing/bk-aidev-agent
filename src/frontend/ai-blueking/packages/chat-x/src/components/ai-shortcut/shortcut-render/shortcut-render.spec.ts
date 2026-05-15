/* eslint-disable vue/no-reserved-component-names */
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

import ShortcutRender from './shortcut-render.vue';

import type { Shortcut, ShortcutComponent } from '../../../types';

// Mock bkui-vue components
vi.mock('bkui-vue', () => {
  const Form = defineComponent({
    name: 'Form',
    props: {
      formType: { type: String, default: 'horizontal' },
      model: { type: Object, default: () => ({}) },
      rules: { type: Object, default: () => ({}) },
    },
    setup(_, { slots, expose }) {
      const validate = vi.fn().mockResolvedValue(true);
      expose({ validate });
      return () => h('form', { class: 'mock-form' }, slots.default?.());
    },
  });

  const FormItem = defineComponent({
    name: 'FormItem',
    props: {
      property: { type: String, default: '' },
      label: { type: String, default: '' },
      required: { type: Boolean, default: false },
    },
    setup(props, { slots }) {
      return () =>
        h('div', { class: 'mock-form-item', 'data-property': props.property }, [
          slots.label ? slots.label() : h('label', { class: 'mock-label' }, props.label),
          slots.default?.(),
        ]);
    },
  });

  (Form as unknown as { FormItem: typeof FormItem }).FormItem = FormItem;

  return {
    Form,
    Input: defineComponent({
      name: 'Input',
      props: {
        modelValue: { type: [String, Number], default: '' },
        type: { type: String, default: 'text' },
      },
      emits: ['update:modelValue', 'change'],
      setup(props, { emit }) {
        return () =>
          h('input', {
            class: 'mock-input',
            type: props.type,
            value: props.modelValue,
            onInput: (e: Event) => {
              const value = (e.target as HTMLInputElement).value;
              emit('update:modelValue', value);
              emit('change', value);
            },
          });
      },
    }),
    Select: Object.assign(
      defineComponent({
        name: 'Select',
        props: {
          modelValue: { type: [String, Number, Array], default: '' },
        },
        emits: ['update:modelValue', 'change'],
        setup(props, { slots }) {
          return () => h('select', { class: 'mock-select', value: props.modelValue }, slots.default?.());
        },
      }),
      {
        Option: defineComponent({
          name: 'Option',
          props: {
            value: { type: [String, Number], default: '' },
            label: { type: String, default: '' },
          },
          setup(props) {
            return () => h('option', { value: props.value }, props.label);
          },
        }),
      },
    ),
    Checkbox: Object.assign(
      defineComponent({
        name: 'Checkbox',
        props: {
          modelValue: { type: Boolean, default: false },
          label: { type: String, default: '' },
          value: { type: [String, Number], default: '' },
        },
        setup(props) {
          return () => h('input', { class: 'mock-checkbox', type: 'checkbox', checked: props.modelValue }, props.label);
        },
      }),
      {
        Group: defineComponent({
          name: 'CheckboxGroup',
          props: {
            modelValue: { type: Array, default: () => [] },
          },
          setup(_, { slots }) {
            return () => h('div', { class: 'mock-checkbox-group' }, slots.default?.());
          },
        }),
      },
    ),
    Radio: Object.assign(
      defineComponent({
        name: 'Radio',
        props: {
          modelValue: { type: [String, Number, Boolean], default: '' },
          label: { type: String, default: '' },
          value: { type: [String, Number], default: '' },
        },
        setup(props) {
          return () =>
            h('input', { class: 'mock-radio', type: 'radio', checked: props.modelValue === props.value }, props.label);
        },
      }),
      {
        Group: defineComponent({
          name: 'RadioGroup',
          props: {
            modelValue: { type: [String, Number], default: '' },
          },
          setup(_, { slots }) {
            return () => h('div', { class: 'mock-radio-group' }, slots.default?.());
          },
        }),
      },
    ),
    Switcher: defineComponent({
      name: 'Switcher',
      props: {
        modelValue: { type: Boolean, default: false },
      },
      emits: ['update:modelValue', 'change'],
      setup(props) {
        return () => h('input', { class: 'mock-switcher', type: 'checkbox', checked: props.modelValue });
      },
    }),
    Button: defineComponent({
      name: 'Button',
      props: {
        theme: { type: String, default: 'default' },
      },
      emits: ['click'],
      setup(props, { slots, emit }) {
        return () =>
          h(
            'button',
            {
              class: ['mock-button', `mock-button-${props.theme}`],
              onClick: () => emit('click'),
            },
            slots.default?.(),
          );
      },
    }),
  };
});

// Mock icons
vi.mock('../../../icons', () => ({
  CloseIcon: defineComponent({
    name: 'CloseIcon',
    setup() {
      return () => h('span', { class: 'mock-close-icon' });
    },
  }),
  ThinkingIcon: defineComponent({
    name: 'ThinkingIcon',
    setup() {
      return () => h('span', { class: 'mock-thinking-icon' });
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

describe('ShortcutRender', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试表单',
        },
      });

      expect(wrapper.find('.shortcut-render').exists()).toBe(true);
    });

    it('应该正确渲染标题', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '自定义表单标题',
        },
      });

      expect(wrapper.find('.header-name').text()).toBe('自定义表单标题');
    });

    it('应该渲染头部图标', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      expect(wrapper.find('.header-icon').exists()).toBe(true);
    });

    it('应该渲染关闭按钮', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      expect(wrapper.find('.header-close').exists()).toBe(true);
    });

    it('应该渲染提交和取消按钮', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      const buttons = wrapper.findAll('.mock-button');
      expect(buttons.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('表单组件渲染测试', () => {
    it('应该渲染 input 类型组件', () => {
      const components: ShortcutComponent[] = [
        {
          key: 'name',
          name: '姓名',
          type: 'input',
        },
      ];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect(wrapper.find('.mock-input').exists()).toBe(true);
    });

    it('应通过 label 插槽渲染 component.name', () => {
      const components: ShortcutComponent[] = [
        {
          key: 'name',
          name: '姓名',
          type: 'input',
        },
      ];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect(wrapper.find('.shortcut-render-form-label').text()).toBe('姓名');
    });

    it('应该渲染 textarea 类型组件', () => {
      const components: ShortcutComponent[] = [
        {
          key: 'description',
          name: '描述',
          type: 'textarea',
        },
      ];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect(wrapper.find('.mock-input[type="textarea"]').exists()).toBe(true);
    });

    it('应该渲染 select 类型组件', () => {
      const components: ShortcutComponent[] = [
        {
          key: 'option',
          name: '选择',
          type: 'select',
          options: [
            { label: '选项1', value: '1' },
            { label: '选项2', value: '2' },
          ],
        },
      ];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect(wrapper.find('.mock-select').exists()).toBe(true);
    });

    it('应该渲染 switcher 类型组件', () => {
      const components: ShortcutComponent[] = [
        {
          key: 'enabled',
          name: '开关',
          type: 'switcher',
        },
      ];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect(wrapper.find('.mock-switcher').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击关闭按钮应该触发 close 事件', async () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      await wrapper.find('.header-close').trigger('click');

      expect(wrapper.emitted('close')).toBeTruthy();
    });

    it('点击取消按钮应该触发 close 事件', async () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      const buttons = wrapper.findAll('.mock-button');
      const cancelBtn = buttons.find(btn => btn.text() === '取消');
      await cancelBtn?.trigger('click');

      expect(wrapper.emitted('close')).toBeTruthy();
    });

    it('点击提交按钮应该触发 submit 事件', async () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      const buttons = wrapper.findAll('.mock-button');
      const submitBtn = buttons.find(btn => btn.text() === '提交');
      await submitBtn?.trigger('click');
      await nextTick();

      expect(wrapper.emitted('submit')).toBeTruthy();
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 name 属性', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '表单名称',
        },
      });

      expect((wrapper.props() as Partial<Shortcut>).name).toBe('表单名称');
    });

    it('应该正确接收 components 属性', () => {
      const components: ShortcutComponent[] = [{ key: 'field1', name: '字段1', type: 'input' }];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect((wrapper.props() as Partial<Shortcut>).components).toEqual(components);
    });

    it('应该正确接收 formModel 属性', () => {
      const formModel = { name: '初始值' };

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          formModel,
        },
      });

      expect((wrapper.props() as Partial<Shortcut>).formModel).toEqual(formModel);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
        },
      });

      expect(wrapper.find('.shortcut-render').exists()).toBe(true);
      expect(wrapper.find('.shortcut-render-header').exists()).toBe(true);
      expect(wrapper.find('.shortcut-render-content').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 components 数组', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components: [],
        },
      });

      expect(wrapper.find('.shortcut-render').exists()).toBe(true);
    });

    it('应该处理空 name', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '',
        },
      });

      expect(wrapper.find('.shortcut-render').exists()).toBe(true);
    });

    it('应该处理特殊字符的 name', () => {
      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '<script>alert("xss")</script>',
        },
      });

      expect(wrapper.find('.header-name').text()).toContain('<script>');
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理多个表单组件', () => {
      const components: ShortcutComponent[] = [
        { key: 'field1', name: '字段1', type: 'input' },
        { key: 'field2', name: '字段2', type: 'input' },
        { key: 'field3', name: '字段3', type: 'textarea' },
      ];

      wrapper = mount(ShortcutRender, {
        props: {
          id: 'test',
          name: '测试',
          components,
        },
      });

      expect(wrapper.findAll('.mock-form-item').length).toBeGreaterThanOrEqual(3);
    });
  });
});
