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

import LoadingMessage from './loading-message.vue';

// Mock AiLoading
vi.mock('../../ai-loading/ai-loading.vue', () => ({
  default: defineComponent({
    name: 'AiLoading',
    props: { size: { type: Number, default: 18 } },
    setup() {
      return () => h('span', { class: 'mock-ai-loading' });
    },
  }),
}));

// Mock lang
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

/** 滚动上下文的贴底方法；mockScrollConsumer 置空可模拟无 Provider 的独立使用场景 */
const mockJumpToBottom = vi.hoisted(() => vi.fn());
const mockScrollConsumer = vi.hoisted(() => ({ value: undefined as undefined | { jumpToBottom: () => void } }));

vi.mock('../../../composables', () => ({
  useContainerScrollConsumer: () => mockScrollConsumer,
}));

describe('LoadingMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
    mockScrollConsumer.value = { jumpToBottom: mockJumpToBottom };
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(LoadingMessage);

      expect(wrapper.find('.ai-loading-message').exists()).toBe(true);
    });

    it('应该渲染 AiLoading 图标', () => {
      wrapper = mount(LoadingMessage);

      expect(wrapper.find('.mock-ai-loading').exists()).toBe(true);
    });

    it('未提供 slot 时应显示默认的"请求中..."文本', () => {
      wrapper = mount(LoadingMessage);

      expect(wrapper.text()).toContain('请求中...');
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot 替换默认文本', () => {
      wrapper = mount(LoadingMessage, {
        slots: {
          default: '<span class="custom-loading-text">加载中，请稍候...</span>',
        },
      });

      expect(wrapper.find('.custom-loading-text').exists()).toBe(true);
      expect(wrapper.find('.custom-loading-text').text()).toBe('加载中，请稍候...');
    });

    it('提供 slot 时不应显示默认的"请求中..."文本', () => {
      wrapper = mount(LoadingMessage, {
        slots: {
          default: '<span class="custom-text">自定义内容</span>',
        },
      });

      expect(wrapper.text()).not.toContain('请求中...');
    });

    it('slot 可以接收复杂内容', () => {
      wrapper = mount(LoadingMessage, {
        slots: {
          default: () => h('div', { class: 'complex-slot' }, [h('span', '正在'), h('strong', '思考中...')]),
        },
      });

      expect(wrapper.find('.complex-slot').exists()).toBe(true);
      expect(wrapper.text()).toContain('正在');
      expect(wrapper.text()).toContain('思考中...');
    });
  });

  describe('自动贴底测试', () => {
    it('挂载时应触发滚动容器贴底', () => {
      wrapper = mount(LoadingMessage);

      expect(mockJumpToBottom).toHaveBeenCalledTimes(1);
    });

    it('无滚动 Provider 时挂载不应报错', () => {
      mockScrollConsumer.value = undefined;

      wrapper = mount(LoadingMessage);

      expect(wrapper.find('.ai-loading-message').exists()).toBe(true);
      expect(mockJumpToBottom).not.toHaveBeenCalled();
    });
  });

  describe('边界情况测试', () => {
    it('slot 为空内容时不应报错', () => {
      wrapper = mount(LoadingMessage, {
        slots: {
          default: '',
        },
      });

      expect(wrapper.find('.ai-loading-message').exists()).toBe(true);
    });
  });
});
