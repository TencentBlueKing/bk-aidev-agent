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

import ActivityLayout from './activity-layout.vue';

vi.mock('../../../ag-ui/types/constants', () => ({
  MessageContentType: {
    FlowAgent: 'flow_agent',
    KnowledgeRag: 'knowledge_rag',
    ReferenceDocument: 'reference_document',
  },
}));

vi.mock('../../../icons/messages', () => ({
  CollapsedIcon: defineComponent({
    name: 'CollapsedIcon',
    setup() {
      return () => h('span', { class: 'mock-collapsed-icon' });
    },
  }),
}));

describe('ActivityLayout', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
      });

      expect(wrapper.find('.ai-activity-message').exists()).toBe(true);
    });

    it('应该渲染标题区域', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
      });

      expect(wrapper.find('.ai-activity-message-title').exists()).toBe(true);
    });

    it('应该渲染内容区域', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
        slots: {
          default: () => h('div', { class: 'test-content' }, '内容'),
        },
      });

      expect(wrapper.find('.ai-activity-message-content').exists()).toBe(true);
      expect(wrapper.find('.test-content').exists()).toBe(true);
    });
  });

  describe('折叠功能测试', () => {
    it('默认应该展开显示内容', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
        slots: {
          default: () => h('div', { class: 'test-content' }),
        },
      });

      expect(wrapper.find('.ai-activity-message-content').isVisible()).toBe(true);
    });

    it('点击标题应该切换折叠状态', async () => {
      wrapper = mount(ActivityLayout, {
        props: {
          activityType: 'reference_document',
          collapsed: false,
          'onUpdate:collapsed': (val: boolean) => wrapper.setProps({ collapsed: val }),
        },
        slots: {
          default: () => h('div', { class: 'test-content' }),
        },
      });

      expect(wrapper.find('.ai-activity-message-content').isVisible()).toBe(true);

      await wrapper.find('.ai-activity-message-title').trigger('click');

      expect(wrapper.emitted('update:collapsed')).toBeTruthy();
      expect(wrapper.emitted('update:collapsed')?.[0]).toEqual([true]);
    });

    it('折叠时 collapsed-icon 应该有 is-collapsed 类', async () => {
      wrapper = mount(ActivityLayout, {
        props: {
          activityType: 'reference_document',
          collapsed: false,
          'onUpdate:collapsed': (val: boolean) => wrapper.setProps({ collapsed: val }),
        },
      });

      await wrapper.find('.ai-activity-message-title').trigger('click');

      expect(wrapper.find('.collapsed-icon').classes()).toContain('is-collapsed');
    });

    it('折叠时内容区域应该隐藏', async () => {
      wrapper = mount(ActivityLayout, {
        props: {
          activityType: 'reference_document',
          collapsed: false,
          'onUpdate:collapsed': async (val: boolean) => {
            await wrapper.setProps({ collapsed: val });
          },
        },
        slots: {
          default: () => h('div', { class: 'test-content' }),
        },
      });

      await wrapper.find('.ai-activity-message-title').trigger('click');
      await nextTick();
      await nextTick();

      const contentEl = wrapper.find('.ai-activity-message-content').element as HTMLElement;
      expect(contentEl.style.display).toBe('none');
    });
  });

  describe('FlowAgent 特殊处理测试', () => {
    it('FlowAgent 类型不应该渲染折叠图标', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'flow_agent' },
      });

      expect(wrapper.find('.collapsed-icon').exists()).toBe(false);
    });

    it('非 FlowAgent 类型应该渲染折叠图标', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
      });

      expect(wrapper.find('.collapsed-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-collapsed-icon').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持 title scoped slot', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
        slots: {
          title: ({ collapsed }: { collapsed: boolean }) =>
            h('span', { class: 'custom-title', 'data-collapsed': String(collapsed) }, '自定义标题'),
        },
      });

      expect(wrapper.find('.custom-title').exists()).toBe(true);
      expect(wrapper.find('.custom-title').attributes('data-collapsed')).toBe('false');
    });

    it('应该支持默认 slot', () => {
      wrapper = mount(ActivityLayout, {
        props: { activityType: 'reference_document' },
        slots: {
          default: () => h('div', { class: 'custom-content' }, '自定义内容'),
        },
      });

      expect(wrapper.find('.custom-content').text()).toBe('自定义内容');
    });
  });
});
