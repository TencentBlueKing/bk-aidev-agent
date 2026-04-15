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

import { defineComponent, h, ref } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DeleteTool, { type DeleteToolProps } from './delete-tool.vue';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock vue-tippy
vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    props: {
      arrow: { type: Boolean, default: false },
      interactive: { type: Boolean, default: false },
      offset: { type: Array, default: () => [0, 6] },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'click' },
      appendTo: { type: Function, default: null },
      onShow: { type: Function, default: undefined },
    },
    emits: ['show'],
    setup(props, { slots, emit, expose }) {
      const hide = vi.fn();
      const showPrevented = ref(false);
      expose({ hide, showPrevented });
      return () =>
        h(
          'div',
          {
            class: ['mock-tippy', showPrevented.value && 'show-prevented'],
            'data-show-prevented': showPrevented.value ? 'true' : undefined,
            onMouseenter: () => {
              const allowed = props.onShow?.() !== false;
              showPrevented.value = !allowed;
              emit('show');
            },
          },
          [slots.default?.(), slots.content?.()],
        );
    },
  }),
  useTippy: vi.fn(() => ({
    show: vi.fn(),
    hide: vi.fn(),
  })),
}));

// Mock bkui-vue Button
vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    name: 'BkButton',
    props: {
      size: { type: String, default: '' },
      theme: { type: String, default: '' },
      disabled: { type: Boolean, default: false },
    },
    emits: ['click'],
    setup(props, { slots, emit }) {
      return () =>
        h(
          'button',
          {
            class: ['mock-button', props.theme && `mock-button-${props.theme}`],
            disabled: props.disabled,
            onClick: () => emit('click'),
          },
          slots.default?.(),
        );
    },
  }),
}));

// Mock ToolBtn
vi.mock('../../ai-buttons/tool-btn/tool-btn.vue', () => ({
  default: defineComponent({
    name: 'ToolBtn',
    props: {
      id: { type: String, default: '' },
      name: { type: String, default: '' },
      description: { type: String, default: '' },
      disabled: { type: Boolean, default: false },
      tippyOptions: { type: Object, default: undefined },
    },
    emits: ['click'],
    setup(props) {
      return () =>
        h(
          'button',
          {
            class: 'mock-tool-btn',
            'data-tool-id': props.id,
            'data-disabled': props.disabled,
          },
          props.name,
        );
    },
  }),
}));

// Mock lang
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const defaultProps = {
  id: 'delete' as const,
  name: '删除',
  description: '删除该回答',
};

describe('DeleteTool', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      expect(wrapper.find('.mock-tippy').exists()).toBe(true);
    });

    it('应该渲染 ToolBtn', () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      expect(wrapper.find('.mock-tool-btn').exists()).toBe(true);
      expect(wrapper.find('[data-tool-id="delete"]').exists()).toBe(true);
    });

    it('应该在 Tippy content 中渲染确认对话框', () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      expect(wrapper.find('.ai-delete-confirm').exists()).toBe(true);
      expect(wrapper.find('.ai-delete-confirm__title').text()).toBe('确认删除该回答？');
      expect(wrapper.find('.ai-delete-confirm__desc').text()).toBe('删除操作无法撤回，请谨慎操作！');
    });

    it('应该渲染删除和取消按钮', () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      const buttons = wrapper.findAll('.mock-button');
      expect(buttons.length).toBe(2);

      const dangerBtn = wrapper.find('.mock-button-danger');
      expect(dangerBtn.exists()).toBe(true);
      expect(dangerBtn.text()).toBe('删除');
    });
  });

  describe('Props 测试', () => {
    it('应该将 id/name/description/disabled 传递给 ToolBtn', () => {
      wrapper = mount(DeleteTool, {
        props: { ...defaultProps, disabled: true },
      });

      const toolBtn = wrapper.find('.mock-tool-btn');
      expect(toolBtn.attributes('data-tool-id')).toBe('delete');
      expect(toolBtn.attributes('data-disabled')).toBe('true');
    });

    it('应该正确接收 tippyOptions 属性', () => {
      const tippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(DeleteTool, {
        props: { ...defaultProps, tippyOptions },
      });

      expect((wrapper.props() as DeleteToolProps).tippyOptions).toEqual(tippyOptions);
    });
  });

  describe('事件测试', () => {
    it('点击删除按钮应触发 confirm 事件', async () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      await wrapper.find('.mock-button-danger').trigger('click');

      expect(wrapper.emitted('confirm')).toBeTruthy();
      expect(wrapper.emitted('confirm')?.length).toBe(1);
    });

    it('点击取消按钮应触发 cancel 事件', async () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      const buttons = wrapper.findAll('.mock-button');
      const cancelBtn = buttons.find(btn => btn.text() === '取消');
      await cancelBtn?.trigger('click');

      expect(wrapper.emitted('cancel')).toBeTruthy();
      expect(wrapper.emitted('cancel')?.length).toBe(1);
    });
  });

  describe('disabled 状态测试', () => {
    it('disabled 为 true 时触发 Tippy show 应阻止展示', async () => {
      wrapper = mount(DeleteTool, {
        props: { ...defaultProps, disabled: true },
      });

      const tippy = wrapper.find('.mock-tippy');
      await tippy.trigger('mouseenter');

      expect(tippy.attributes('data-show-prevented')).toBe('true');
      expect(tippy.classes()).toContain('show-prevented');
    });

    it('disabled 为 false 时触发 Tippy show 不应阻止展示', async () => {
      wrapper = mount(DeleteTool, {
        props: { ...defaultProps, disabled: false },
      });

      const tippy = wrapper.find('.mock-tippy');
      await tippy.trigger('mouseenter');

      expect(tippy.attributes('data-show-prevented')).toBeUndefined();
      expect(tippy.classes()).not.toContain('show-prevented');
    });
  });

  describe('边界情况测试', () => {
    it('不传 disabled 时组件应正常渲染', () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      expect(wrapper.find('.mock-tippy').exists()).toBe(true);
    });

    it('不传 tippyOptions 时组件应正常渲染', () => {
      wrapper = mount(DeleteTool, { props: defaultProps });

      expect(wrapper.find('.mock-tippy').exists()).toBe(true);
      expect((wrapper.props() as DeleteToolProps).tippyOptions).toBeUndefined();
    });
  });
});
