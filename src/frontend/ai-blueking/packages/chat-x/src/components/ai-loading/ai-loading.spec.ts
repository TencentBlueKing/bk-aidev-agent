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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AiLoading from './ai-loading.vue';

describe('AiLoading', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  // ---------- 渲染测试 ----------
  describe('渲染测试', () => {
    it('应该正确渲染组件根元素', () => {
      wrapper = mount(AiLoading);

      expect(wrapper.find('.ai-loading').exists()).toBe(true);
    });

    it('应该渲染 ring 元素', () => {
      wrapper = mount(AiLoading);

      expect(wrapper.find('.ai-loading-ring').exists()).toBe(true);
      expect(wrapper.find('.ai-loading-ring svg').exists()).toBe(true);
    });

    it('应该渲染 star 元素', () => {
      wrapper = mount(AiLoading);

      expect(wrapper.find('.ai-loading-star').exists()).toBe(true);
      expect(wrapper.find('.ai-loading-star svg').exists()).toBe(true);
    });

    it('SVG 应该包含 linearGradient 定义', () => {
      wrapper = mount(AiLoading);

      const gradients = wrapper.findAll('linearGradient');
      expect(gradients.length).toBe(2);
    });
  });

  // ---------- Props 测试 ----------
  describe('Props 测试', () => {
    it('size 默认值应该为 16', () => {
      wrapper = mount(AiLoading);

      const root = wrapper.find('.ai-loading');
      expect(root.attributes('style')).toContain('width: 16px');
      expect(root.attributes('style')).toContain('height: 16px');
    });

    it('应该根据 size 属性设置宽高', () => {
      wrapper = mount(AiLoading, {
        props: { size: 32 },
      });

      const root = wrapper.find('.ai-loading');
      expect(root.attributes('style')).toContain('width: 32px');
      expect(root.attributes('style')).toContain('height: 32px');
    });

    it('stopLoading 默认值应该为 false', () => {
      wrapper = mount(AiLoading);

      expect(wrapper.find('.ai-loading').classes()).not.toContain('ai-loading-stopped');
    });

    it('stopLoading 为 true 时应该添加 ai-loading-stopped 类', () => {
      wrapper = mount(AiLoading, {
        props: { stopLoading: true },
      });

      expect(wrapper.find('.ai-loading').classes()).toContain('ai-loading-stopped');
    });

    it('stopLoading 为 false 时不应该有 ai-loading-stopped 类', () => {
      wrapper = mount(AiLoading, {
        props: { stopLoading: false },
      });

      expect(wrapper.find('.ai-loading').classes()).not.toContain('ai-loading-stopped');
    });

    it('更新 size 属性时应该响应式更新样式', async () => {
      wrapper = mount(AiLoading, {
        props: { size: 16 },
      });

      await wrapper.setProps({ size: 48 });

      const root = wrapper.find('.ai-loading');
      expect(root.attributes('style')).toContain('width: 48px');
      expect(root.attributes('style')).toContain('height: 48px');
    });

    it('更新 stopLoading 属性时应该响应式切换类名', async () => {
      wrapper = mount(AiLoading, {
        props: { stopLoading: false },
      });

      expect(wrapper.find('.ai-loading').classes()).not.toContain('ai-loading-stopped');

      await wrapper.setProps({ stopLoading: true });
      expect(wrapper.find('.ai-loading').classes()).toContain('ai-loading-stopped');

      await wrapper.setProps({ stopLoading: false });
      expect(wrapper.find('.ai-loading').classes()).not.toContain('ai-loading-stopped');
    });
  });

  // ---------- SVG Gradient ID 测试 ----------
  describe('SVG Gradient ID 测试', () => {
    it('ring 和 star 应该使用不同的 gradient ID', () => {
      wrapper = mount(AiLoading);

      const gradients = wrapper.findAll('linearGradient');
      const ids = gradients.map(g => g.attributes('id'));

      expect(ids[0]).toMatch(/^ai-loading-ring-\d+$/);
      expect(ids[1]).toMatch(/^ai-loading-star-\d+$/);
    });

    it('gradient ID 中 ring 和 star 的实例号应一致', () => {
      wrapper = mount(AiLoading);

      const gradients = wrapper.findAll('linearGradient');
      const ringId = gradients[0].attributes('id');
      const starId = gradients[1].attributes('id');

      const ringNum = ringId?.replace('ai-loading-ring-', '');
      const starNum = starId?.replace('ai-loading-star-', '');
      expect(ringNum).toBe(starNum);
    });

    it('path 的 fill 应该引用对应的 gradient ID', () => {
      wrapper = mount(AiLoading);

      const gradients = wrapper.findAll('linearGradient');
      const ringGradientId = gradients[0].attributes('id');
      const starGradientId = gradients[1].attributes('id');

      const paths = wrapper.findAll('path');
      expect(paths[0].attributes('fill')).toBe(`url(#${ringGradientId})`);
      expect(paths[1].attributes('fill')).toBe(`url(#${starGradientId})`);
    });
  });

  // ---------- 样式测试 ----------
  describe('样式测试', () => {
    it('应该具有正确的基础类名', () => {
      wrapper = mount(AiLoading);

      expect(wrapper.find('.ai-loading').exists()).toBe(true);
    });

    it('同时设置 size 和 stopLoading 时应该正确渲染', () => {
      wrapper = mount(AiLoading, {
        props: { size: 24, stopLoading: true },
      });

      const root = wrapper.find('.ai-loading');
      expect(root.attributes('style')).toContain('width: 24px');
      expect(root.attributes('style')).toContain('height: 24px');
      expect(root.classes()).toContain('ai-loading-stopped');
    });
  });

  // ---------- 边界情况测试 ----------
  describe('边界情况测试', () => {
    it('size 为 0 时应该正确渲染', () => {
      wrapper = mount(AiLoading, {
        props: { size: 0 },
      });

      const root = wrapper.find('.ai-loading');
      expect(root.attributes('style')).toContain('width: 0px');
      expect(root.attributes('style')).toContain('height: 0px');
    });

    it('size 为较大值时应该正确渲染', () => {
      wrapper = mount(AiLoading, {
        props: { size: 200 },
      });

      const root = wrapper.find('.ai-loading');
      expect(root.attributes('style')).toContain('width: 200px');
      expect(root.attributes('style')).toContain('height: 200px');
    });

    it('不传任何 props 时应该使用默认值正常渲染', () => {
      wrapper = mount(AiLoading);

      const root = wrapper.find('.ai-loading');
      expect(root.exists()).toBe(true);
      expect(root.attributes('style')).toContain('width: 16px');
      expect(root.attributes('style')).toContain('height: 16px');
      expect(root.classes()).not.toContain('ai-loading-stopped');
    });

    it('多个实例应该各自独立渲染', () => {
      const wrapper1 = mount(AiLoading, { props: { size: 16 } });
      const wrapper2 = mount(AiLoading, { props: { size: 32, stopLoading: true } });

      expect(wrapper1.find('.ai-loading').attributes('style')).toContain('width: 16px');
      expect(wrapper2.find('.ai-loading').attributes('style')).toContain('width: 32px');
      expect(wrapper1.find('.ai-loading').classes()).not.toContain('ai-loading-stopped');
      expect(wrapper2.find('.ai-loading').classes()).toContain('ai-loading-stopped');

      wrapper1.unmount();
      wrapper2.unmount();
    });
  });
});
