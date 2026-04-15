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

import ExecutionSummary from './execution-summary.vue';

import type { MessageGroup } from '../../composables';

vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    name: 'ButtonComponent',
    props: {
      text: { type: Boolean, default: false },
      theme: { type: String, default: 'default' },
    },
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { class: 'mock-button', onClick: () => emit('click') }, slots.default?.());
    },
  }),
  Exception: defineComponent({
    name: 'ExceptionComponent',
    props: { type: { type: String, default: 'empty' } },
    setup(props) {
      return () => h('div', { class: 'mock-exception', 'data-type': props.type });
    },
  }),
  Input: defineComponent({
    name: 'InputComponent',
    props: {
      modelValue: { type: String, default: '' },
      placeholder: { type: String, default: '' },
      clearable: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () =>
        h('input', {
          class: 'mock-input',
          value: props.modelValue,
          onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value),
        });
    },
  }),
}));

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../composables/use-common', () => ({
  useKeywordProvider: () => ({
    keyword: ref(''),
  }),
  useCommonTippyInject: vi.fn(() => undefined),
}));

vi.mock('../../directives', () => ({
  OverflowTips: { mounted: vi.fn(), updated: vi.fn(), unmounted: vi.fn() },
}));

vi.mock('../chat-message/message-render/message-render.vue', () => ({
  default: defineComponent({
    name: 'MessageRender',
    props: { message: { type: Object, default: null } },
    setup(props) {
      return () => h('div', { class: 'mock-message-render' }, props.message?.content);
    },
  }),
}));

const createMessageGroup = (overrides: Partial<MessageGroup> = {}): MessageGroup => ({
  uid: `group-${Math.random().toString(36).slice(2, 8)}`,
  messages: [],
  type: 'assistant' as MessageGroup['type'],
  isHover: false,
  checked: false,
  userMessageTitle: '测试用户消息',
  ...overrides,
});

describe('ExecutionSummary', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [] },
      });

      expect(wrapper.find('.execution-summary').exists()).toBe(true);
    });

    it('应该渲染搜索输入框', () => {
      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [] },
      });

      expect(wrapper.find('.mock-input').exists()).toBe(true);
    });

    it('有数据时应该渲染消息组列表', () => {
      const groups = [
        createMessageGroup({ userMessageTitle: '第一条消息' }),
        createMessageGroup({ userMessageTitle: '第二条消息' }),
      ];

      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: groups },
      });

      const items = wrapper.findAll('.execution-summary-content-item');
      expect(items.length).toBe(2);
    });

    it('无数据时应该显示空状态', () => {
      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [] },
      });

      expect(wrapper.find('.execution-summary-content-empty').exists()).toBe(true);
      expect(wrapper.find('.mock-exception').exists()).toBe(true);
    });
  });

  describe('标题显示测试', () => {
    it('userMessageTitle 为字符串时应直接显示', () => {
      const group = createMessageGroup({ userMessageTitle: '帮我分析 Trace 数据' });

      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [group] },
      });

      expect(wrapper.find('.content-item-title').text()).toBe('帮我分析 Trace 数据');
    });

    it('userMessageTitle 为数字（时间戳）时应格式化为时间', () => {
      const timestamp = new Date(2025, 0, 15, 10, 30, 45).getTime();
      const group = createMessageGroup({ userMessageTitle: timestamp });

      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [group] },
      });

      expect(wrapper.find('.content-item-title').text()).toBe('2025-01-15 10:30:45');
    });

    it('userMessageTitle 为 undefined 时应显示空文本', () => {
      const group = createMessageGroup({ userMessageTitle: undefined });

      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [group] },
      });

      expect(wrapper.find('.content-item-title').text()).toBe('');
    });
  });

  describe('事件测试', () => {
    it('点击定位按钮应该触发 locateMessageGroup 事件', async () => {
      const group = createMessageGroup({ uid: 'test-uid', userMessageTitle: '测试消息' });

      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [group] },
      });

      const item = wrapper.find('.execution-summary-content-item');
      await item.trigger('mouseenter');

      const locateBtn = wrapper.find('.content-item-locate');
      await locateBtn.trigger('click');

      expect(wrapper.emitted('locateMessageGroup')).toBeTruthy();
      expect(wrapper.emitted('locateMessageGroup')?.[0]?.[0]).toBe('test-uid');
    });
  });

  describe('空状态测试', () => {
    it('无数据时应该显示暂无数据', () => {
      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: [] },
      });

      expect(wrapper.find('.execution-summary-content-empty-text').text()).toContain('暂无数据');
    });
  });

  describe('时间线测试', () => {
    it('非最后一项应该显示时间线', () => {
      const groups = [
        createMessageGroup({ userMessageTitle: '消息1' }),
        createMessageGroup({ userMessageTitle: '消息2' }),
      ];

      wrapper = mount(ExecutionSummary, {
        props: { messageGroups: groups },
      });

      const items = wrapper.findAll('.execution-summary-content-item');
      expect(items[0]?.find('.timeline-line').exists()).toBe(true);
      expect(items[1]?.find('.timeline-line').exists()).toBe(false);
    });
  });
});
