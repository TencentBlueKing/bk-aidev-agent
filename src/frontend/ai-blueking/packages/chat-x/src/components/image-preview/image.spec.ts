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

import AiImage from './image.vue';

vi.mock('../../icons/content', () => ({
  ImageErrorIcon: defineComponent({
    name: 'ImageErrorIcon',
    setup() {
      return () => h('span', { class: 'mock-image-error-icon' });
    },
  }),
}));

vi.mock('../../icons/image-preview', () => ({
  ReloadIcon: defineComponent({
    name: 'ReloadIcon',
    setup() {
      return () => h('span', { class: 'mock-reload-icon' });
    },
  }),
}));

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('./image-preview.vue', () => ({
  default: defineComponent({
    name: 'ImagePreview',
    props: {
      images: { type: Array, default: () => [] },
      visible: { type: Boolean, default: false },
      onDownload: { type: Function, default: undefined },
      showInfo: { type: Boolean, default: false },
    },
    emits: ['update:visible'],
    setup(_, { slots }) {
      return () => h('div', { class: 'mock-image-preview' }, slots.default?.());
    },
  }),
}));

describe('AiImage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png' },
      });

      expect(wrapper.find('.ai-image').exists()).toBe(true);
    });

    it('应该渲染 img 元素', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png' },
      });

      expect(wrapper.find('.ai-image-inner').exists()).toBe(true);
      expect(wrapper.find('.ai-image-inner').attributes('src')).toBe('https://example.com/test.png');
    });
  });

  describe('Props 测试', () => {
    it('应该正确设置 alt 属性', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', alt: '测试图片' },
      });

      expect(wrapper.find('.ai-image-inner').attributes('alt')).toBe('测试图片');
    });

    it('应该正确设置 width', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', width: 200 },
      });

      expect(wrapper.find('.ai-image').attributes('style')).toContain('width: 200px');
    });

    it('应该正确设置 height', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', height: '150px' },
      });

      expect(wrapper.find('.ai-image').attributes('style')).toContain('height: 150px');
    });

    it('preview 默认应该为 true', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png' },
      });

      expect(wrapper.props().preview).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('图片加载成功应该触发 load 事件', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png' },
      });

      await wrapper.find('.ai-image-inner').trigger('load');

      expect(wrapper.emitted('load')).toBeTruthy();
    });

    it('图片加载失败应该触发 error 事件', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/broken.png' },
      });

      await wrapper.find('.ai-image-inner').trigger('error');

      expect(wrapper.emitted('error')).toBeTruthy();
    });

    it('图片加载失败应该显示错误状态', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/broken.png' },
      });

      await wrapper.find('.ai-image-inner').trigger('error');

      expect(wrapper.find('.ai-image--error').exists()).toBe(true);
      expect(wrapper.find('.ai-image-error').exists()).toBe(true);
    });

    it('点击重新加载应该重置加载状态', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/broken.png' },
      });

      await wrapper.find('.ai-image-inner').trigger('error');
      expect(wrapper.find('.ai-image-error-overlay').exists()).toBe(true);

      await wrapper.find('.ai-image-error-overlay').trigger('click');

      expect(wrapper.find('.ai-image--error').exists()).toBe(false);
    });
  });

  describe('预览测试', () => {
    it('加载成功后点击应该触发 preview 事件', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png' },
      });

      await wrapper.find('.ai-image-inner').trigger('load');
      await wrapper.find('.ai-image').trigger('click');

      expect(wrapper.emitted('preview')).toBeTruthy();
    });

    it('preview 为 false 时点击不应该触发预览', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', preview: false },
      });

      await wrapper.find('.ai-image-inner').trigger('load');
      await wrapper.find('.ai-image').trigger('click');

      expect(wrapper.emitted('preview')).toBeFalsy();
    });

    it('加载成功且 preview 为 true 时应该有 preview 样式类', async () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', preview: true },
      });

      await wrapper.find('.ai-image-inner').trigger('load');

      expect(wrapper.find('.ai-image--preview').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png' },
        slots: {
          default: '<div class="custom-overlay">Overlay</div>',
        },
      });

      expect(wrapper.find('.custom-overlay').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 src', () => {
      wrapper = mount(AiImage, {
        props: { src: '' },
      });

      expect(wrapper.find('.ai-image').exists()).toBe(true);
    });

    it('数字类型的 width 和 height 应该转换为 px', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', width: 300, height: 200 },
      });

      const style = wrapper.find('.ai-image').attributes('style');
      expect(style).toContain('width: 300px');
      expect(style).toContain('height: 200px');
    });

    it('字符串类型的 width 和 height 应该直接使用', () => {
      wrapper = mount(AiImage, {
        props: { src: 'https://example.com/test.png', width: '50%', height: 'auto' },
      });

      const style = wrapper.find('.ai-image').attributes('style');
      expect(style).toContain('width: 50%');
      expect(style).toContain('height: auto');
    });
  });
});
