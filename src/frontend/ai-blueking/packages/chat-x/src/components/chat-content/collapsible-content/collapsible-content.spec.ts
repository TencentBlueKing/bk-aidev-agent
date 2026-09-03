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

import CollapsibleContent from './collapsible-content.vue';

vi.mock('../../../lang/lang', () => ({ t: (key: string) => key }));

vi.mock('../../../icons', () => ({
  ArrowLeftIcon: defineComponent({
    name: 'ArrowLeftIcon',
    setup(_, { attrs }) {
      return () => h('span', { class: ['mock-arrow-left-icon', attrs.class] });
    },
  }),
}));

/** happy-dom 不做真实布局，用可控的 ResizeObserver 桩驱动高度变化 */
const observerCallbacks = new Set<ResizeObserverCallback>();
const emitHeight = async (height: number) => {
  await nextTick();
  for (const callback of observerCallbacks) {
    callback([{ contentRect: { height } } as ResizeObserverEntry], {} as ResizeObserver);
  }
  await nextTick();
};

beforeEach(() => {
  observerCallbacks.clear();
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: ResizeObserverCallback) {
        observerCallbacks.add(callback);
      }
      disconnect() {}
      observe() {}
      unobserve() {}
    },
  );
});

describe('CollapsibleContent', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
    vi.unstubAllGlobals();
  });

  const mountWith = (props: Record<string, unknown> = {}) =>
    mount(CollapsibleContent, {
      props,
      slots: { default: '<p class="inner">内容</p>' },
    });

  it('渲染插槽内容', () => {
    wrapper = mountWith();
    expect(wrapper.find('.inner').exists()).toBe(true);
  });

  it('内容未超出最大高度时不展示切换按钮，也不裁剪', async () => {
    wrapper = mountWith({ maxHeight: 200 });
    await emitHeight(150);

    expect(wrapper.find('.ai-collapsible-content-toggle').exists()).toBe(false);
    expect(wrapper.find('.ai-collapsible-content-body').classes()).not.toContain('is-collapsed');
  });

  it('内容超出最大高度时裁剪并展示「显示更多」', async () => {
    wrapper = mountWith({ maxHeight: 200 });
    await emitHeight(320);

    const body = wrapper.find('.ai-collapsible-content-body');
    expect(body.classes()).toContain('is-collapsed');
    expect(body.attributes('style')).toContain('max-height: 200px');
    expect(wrapper.find('.ai-collapsible-content-toggle').text()).toBe('显示更多');
  });

  it('点击后展开：文案变「收起」、箭头翻转、不再裁剪', async () => {
    wrapper = mountWith({ maxHeight: 200 });
    await emitHeight(320);

    await wrapper.find('.ai-collapsible-content-toggle').trigger('click');

    expect(wrapper.find('.ai-collapsible-content-toggle').text()).toBe('收起');
    expect(wrapper.find('.ai-collapsible-content-toggle-icon').classes()).toContain('is-expanded');
    expect(wrapper.find('.ai-collapsible-content-body').classes()).not.toContain('is-collapsed');
    expect(wrapper.find('.ai-collapsible-content-body').attributes('style')).toBeUndefined();
  });

  it('再次点击可收起', async () => {
    wrapper = mountWith({ maxHeight: 200 });
    await emitHeight(320);

    await wrapper.find('.ai-collapsible-content-toggle').trigger('click');
    await wrapper.find('.ai-collapsible-content-toggle').trigger('click');

    expect(wrapper.find('.ai-collapsible-content-toggle').text()).toBe('显示更多');
    expect(wrapper.find('.ai-collapsible-content-body').classes()).toContain('is-collapsed');
  });

  it('内容变矮到阈值以内时按钮自动消失', async () => {
    wrapper = mountWith({ maxHeight: 200 });
    await emitHeight(320);
    expect(wrapper.find('.ai-collapsible-content-toggle').exists()).toBe(true);

    await emitHeight(120);
    expect(wrapper.find('.ai-collapsible-content-toggle').exists()).toBe(false);
  });

  it('maxHeight 默认为设计稿的 200', async () => {
    wrapper = mountWith();
    await emitHeight(220);

    expect(wrapper.find('.ai-collapsible-content-body').attributes('style')).toContain('max-height: 200px');
  });

  it('展开态可由 v-model:expanded 外部控制', async () => {
    wrapper = mountWith({ maxHeight: 200, expanded: true });
    await emitHeight(320);

    expect(wrapper.find('.ai-collapsible-content-body').classes()).not.toContain('is-collapsed');

    await wrapper.find('.ai-collapsible-content-toggle').trigger('click');
    expect(wrapper.emitted('update:expanded')?.[0]).toEqual([false]);
  });
});
