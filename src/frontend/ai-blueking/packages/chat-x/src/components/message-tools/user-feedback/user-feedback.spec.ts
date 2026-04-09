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

import UserFeedback from './user-feedback.vue';

// Mock bkui-vue
vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    name: 'ButtonComponent',
    props: {
      disabled: { type: Boolean, default: false },
      size: { type: String, default: 'medium' },
      theme: { type: String, default: 'default' },
      width: { type: String, default: '' },
    },
    emits: ['click'],
    setup(props, { slots, emit }) {
      return () =>
        h(
          'button',
          {
            class: ['mock-button', `mock-button-${props.theme}`],
            disabled: props.disabled,
            onClick: () => emit('click'),
          },
          slots.default?.(),
        );
    },
  }),
  Input: defineComponent({
    name: 'InputComponent',
    props: {
      modelValue: { type: String, default: '' },
      placeholder: { type: String, default: '' },
      rows: { type: Number, default: 1 },
      type: { type: String, default: 'text' },
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () =>
        h('textarea', {
          class: 'mock-input',
          value: props.modelValue,
          onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLTextAreaElement).value),
        });
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

describe('UserFeedback', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1', '原因2'],
          title: '请选择原因',
        },
      });

      expect(wrapper.find('.ai-user-feedback').exists()).toBe(true);
    });

    it('应该渲染标题', () => {
      const title = '请选择反馈原因';

      wrapper = mount(UserFeedback, {
        props: {
          reasonList: [],
          title,
        },
      });

      expect(wrapper.find('.ai-feedback-title').text()).toBe(title);
    });

    it('应该渲染原因列表', () => {
      const reasonList = ['原因1', '原因2', '原因3'];

      wrapper = mount(UserFeedback, {
        props: {
          reasonList,
          title: '标题',
        },
      });

      const items = wrapper.findAll('.reason-item');
      expect(items.length).toBe(3);
      expect(items[0]?.text()).toBe('原因1');
      expect(items[1]?.text()).toBe('原因2');
      expect(items[2]?.text()).toBe('原因3');
    });

    it('应该渲染输入框', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: [],
          title: '标题',
        },
      });

      expect(wrapper.find('.mock-input').exists()).toBe(true);
    });

    it('应该渲染提交和取消按钮', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: [],
          title: '标题',
        },
      });

      const buttons = wrapper.findAll('.mock-button');
      expect(buttons.length).toBe(2);
    });
  });

  describe('交互测试', () => {
    it('点击原因项应该切换选中状态', async () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1', '原因2'],
          title: '标题',
        },
      });

      const item = wrapper.find('.reason-item');
      expect(item.classes()).not.toContain('is-active');

      await item.trigger('click');
      expect(item.classes()).toContain('is-active');

      await item.trigger('click');
      expect(item.classes()).not.toContain('is-active');
    });

    it('可以选择多个原因', async () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1', '原因2', '原因3'],
          title: '标题',
        },
      });

      const items = wrapper.findAll('.reason-item');

      await items[0]?.trigger('click');
      await items[1]?.trigger('click');

      expect(items[0]?.classes()).toContain('is-active');
      expect(items[1]?.classes()).toContain('is-active');
      expect(items[2]?.classes()).not.toContain('is-active');
    });
  });

  describe('事件测试', () => {
    it('点击提交按钮应该发出 submit 事件', async () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1'],
          title: '标题',
        },
      });

      // 先选择一个原因
      await wrapper.find('.reason-item').trigger('click');

      // 点击提交
      await wrapper.find('.mock-button-primary').trigger('click');

      expect(wrapper.emitted('submit')).toBeTruthy();
      const emittedArgs = wrapper.emitted('submit')?.[0];
      expect(emittedArgs?.[0]).toContain('原因1');
    });

    it('点击取消按钮应该发出 cancel 事件', async () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: [],
          title: '标题',
        },
      });

      // 找到非 primary 的按钮（取消按钮）
      const cancelBtn = wrapper.findAll('.mock-button').find(btn => !btn.classes().includes('mock-button-primary'));
      await cancelBtn?.trigger('click');

      expect(wrapper.emitted('cancel')).toBeTruthy();
    });

    it('取消时应该重置选择状态', async () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1'],
          title: '标题',
        },
      });

      // 选择原因
      await wrapper.find('.reason-item').trigger('click');
      expect(wrapper.find('.reason-item').classes()).toContain('is-active');

      // 点击取消
      const cancelBtn = wrapper.findAll('.mock-button').find(btn => !btn.classes().includes('mock-button-primary'));
      await cancelBtn?.trigger('click');

      expect(wrapper.find('.reason-item').classes()).not.toContain('is-active');
    });
  });

  describe('提交按钮状态测试', () => {
    it('未选择原因且无其他输入时提交按钮应该禁用', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1'],
          title: '标题',
        },
      });

      const submitBtn = wrapper.find('.mock-button-primary');
      expect(submitBtn.attributes('disabled')).toBeDefined();
    });

    it('选择原因后提交按钮应该启用', async () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1'],
          title: '标题',
        },
      });

      await wrapper.find('.reason-item').trigger('click');

      const submitBtn = wrapper.find('.mock-button-primary');
      expect(submitBtn.attributes('disabled')).toBeUndefined();
    });
  });

  describe('Loading 状态测试', () => {
    it('loading 为 true 时应该渲染 8 个骨架屏元素', () => {
      wrapper = mount(UserFeedback, {
        props: {
          loading: true,
          reasonList: ['原因1', '原因2'],
          title: '标题',
        },
      });

      const skeletonItems = wrapper.findAll('.ai-skeleton-element');
      expect(skeletonItems.length).toBe(8);
    });

    it('loading 为 true 时骨架屏元素应该同时具有 reason-item 类名', () => {
      wrapper = mount(UserFeedback, {
        props: {
          loading: true,
          reasonList: [],
          title: '标题',
        },
      });

      const skeletonItems = wrapper.findAll('.ai-skeleton-element');
      skeletonItems.forEach(item => {
        expect(item.classes()).toContain('reason-item');
      });
    });

    it('loading 为 true 时不应该渲染原因列表内容', () => {
      wrapper = mount(UserFeedback, {
        props: {
          loading: true,
          reasonList: ['原因1', '原因2'],
          title: '标题',
        },
      });

      // 骨架屏元素有 reason-item 类但没有文本内容
      const allReasonItems = wrapper.findAll('.reason-item');
      allReasonItems.forEach(item => {
        expect(item.text()).toBe('');
      });
      // 不应该显示原因文本
      expect(wrapper.text()).not.toContain('原因1');
      expect(wrapper.text()).not.toContain('原因2');
    });

    it('loading 为 false 时应该正常渲染原因列表', () => {
      wrapper = mount(UserFeedback, {
        props: {
          loading: false,
          reasonList: ['原因1', '原因2'],
          title: '标题',
        },
      });

      expect(wrapper.findAll('.ai-skeleton-element').length).toBe(0);
      const items = wrapper.findAll('.reason-item');
      expect(items.length).toBe(2);
      expect(items[0]?.text()).toBe('原因1');
    });

    it('loading 未设置时应该正常渲染原因列表', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1'],
          title: '标题',
        },
      });

      expect(wrapper.findAll('.ai-skeleton-element').length).toBe(0);
      expect(wrapper.findAll('.reason-item').length).toBe(1);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 reasonList', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: [],
          title: '标题',
        },
      });

      expect(wrapper.find('.ai-user-feedback').exists()).toBe(true);
      expect(wrapper.findAll('.reason-item').length).toBe(0);
    });

    it('应该处理单个原因', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['唯一原因'],
          title: '标题',
        },
      });

      expect(wrapper.findAll('.reason-item').length).toBe(1);
    });
  });

  describe('mouseenter 事件测试', () => {
    it('根元素 mouseenter 应该阻止事件冒泡', async () => {
      const parentMouseEnter = vi.fn();
      const Parent = defineComponent({
        setup() {
          return () =>
            h('div', { onMouseenter: parentMouseEnter }, h(UserFeedback, { reasonList: ['原因1'], title: '标题' }));
        },
      });

      const parentWrapper = mount(Parent);
      const feedback = parentWrapper.find('.ai-user-feedback');
      await feedback.trigger('mouseenter');

      expect(parentMouseEnter).not.toHaveBeenCalled();
      parentWrapper.unmount();
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(UserFeedback, {
        props: {
          reasonList: ['原因1'],
          title: '标题',
        },
      });

      expect(wrapper.find('.ai-user-feedback').exists()).toBe(true);
      expect(wrapper.find('.ai-feedback-title').exists()).toBe(true);
      expect(wrapper.find('.ai-feedback-reason-list').exists()).toBe(true);
      expect(wrapper.find('.ai-feedback-other').exists()).toBe(true);
      expect(wrapper.find('.ai-feedback-footer').exists()).toBe(true);
    });
  });
});
