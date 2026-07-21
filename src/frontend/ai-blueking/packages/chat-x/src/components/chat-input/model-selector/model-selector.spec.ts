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

import ModelSelector from './model-selector.vue';

import type { IModelOption } from './types';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../../icons', () => ({
  ArrowDownIcon: defineComponent({
    name: 'ArrowDownIcon',
    setup() {
      return () => h('span', { class: 'mock-arrow-icon' });
    },
  }),
  SearchIcon: defineComponent({
    name: 'SearchIcon',
    setup() {
      return () => h('span', { class: 'mock-search-icon' });
    },
  }),
}));

vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    props: {
      arrow: { type: Boolean, default: false },
      interactive: { type: Boolean, default: false },
      offset: { type: Array, default: () => [0, 0] },
      placement: { type: String, default: 'top-end' },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'click' },
    },
    emits: ['hidden', 'show'],
    setup(_, { slots, expose }) {
      expose({
        hide: vi.fn(),
      });
      return () =>
        h('div', { class: 'mock-tippy' }, [
          slots.default?.(),
          h('div', { class: 'mock-tippy-content' }, slots.content?.()),
        ]);
    },
  }),
}));

const mockModels: IModelOption[] = [
  { id: 'gpt-4', name: 'GPT-4', capabilities: [{ text: '深度思考', theme: 'primary' }] },
  { id: 'claude', name: 'Claude 3', disabled: true },
  { id: 'deepseek', name: 'DeepSeek' },
];

describe('ModelSelector', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('无选中项时应展示占位文案', () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
        },
      });

      expect(wrapper.find('.ai-model-selector-trigger-name').text()).toBe('选择模型');
    });

    it('有选中项时应展示模型名称', () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
          modelValue: 'gpt-4',
        },
      });

      expect(wrapper.find('.ai-model-selector-trigger-name').text()).toBe('GPT-4');
    });

    it('应渲染能力标签', () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
        },
      });

      expect(wrapper.find('.ai-model-capability-tag').text()).toBe('深度思考');
    });
  });

  describe('交互测试', () => {
    it('选中模型后应更新 v-model 并触发 change 事件', async () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
        },
      });

      const options = wrapper.findAll('.ai-model-selector-panel-option');
      await options[2].trigger('click');

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['deepseek']);
      expect(wrapper.emitted('change')?.[0]).toEqual([{ id: 'deepseek', name: 'DeepSeek' }]);
    });

    it('禁用项点击时不应触发 change', async () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
        },
      });

      const disabledOption = wrapper.findAll('.ai-model-selector-panel-option')[1];
      await disabledOption.trigger('click');

      expect(wrapper.emitted('change')).toBeFalsy();
    });

    it('搜索关键字应过滤列表', async () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
        },
      });

      const input = wrapper.find('.ai-model-selector-panel-search-input');
      await input.setValue('deep');

      const visibleNames = wrapper.findAll('.ai-model-selector-panel-option-name').map(node => node.text());
      expect(visibleNames).toEqual(['DeepSeek']);
    });
  });

  describe('Props 测试', () => {
    it('disabled 为 true 时 trigger 应有禁用样式', () => {
      wrapper = mount(ModelSelector, {
        props: {
          models: mockModels,
          disabled: true,
        },
      });

      expect(wrapper.find('.ai-model-selector-trigger.is-disabled').exists()).toBe(true);
    });
  });
});
