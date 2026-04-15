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

import ImagePreview from './image-preview.vue';

vi.mock('../../icons/image-preview', () => ({
  ArrowLeftIcon: defineComponent({
    name: 'ArrowLeftIcon',
    setup() {
      return () => h('span', { class: 'mock-arrow-left-icon' });
    },
  }),
  ArrowRightPreviewIcon: defineComponent({
    name: 'ArrowRightPreviewIcon',
    setup() {
      return () => h('span', { class: 'mock-arrow-right-icon' });
    },
  }),
  ImageBrokenIcon: defineComponent({
    name: 'ImageBrokenIcon',
    setup() {
      return () => h('span', { class: 'mock-image-broken-icon' });
    },
  }),
  PreviewCloseIcon: defineComponent({
    name: 'PreviewCloseIcon',
    setup() {
      return () => h('span', { class: 'mock-close-icon' });
    },
  }),
}));

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('./preview-toolbar.vue', () => ({
  default: defineComponent({
    name: 'PreviewToolbar',
    props: {
      activeIndex: { type: Number, default: 0 },
      currentImageInfo: { type: Object, default: null },
      isMultiple: { type: Boolean, default: false },
      showInfo: { type: Boolean, default: false },
      total: { type: Number, default: 0 },
    },
    emits: ['download', 'reset', 'rotate', 'zoomIn', 'zoomOut'],
    setup(_props, { emit, slots }) {
      return () =>
        h('div', { class: 'mock-preview-toolbar' }, [
          h('button', { class: 'toolbar-download', onClick: () => emit('download') }),
          h('button', { class: 'toolbar-zoom-in', onClick: () => emit('zoomIn') }),
          h('button', { class: 'toolbar-zoom-out', onClick: () => emit('zoomOut') }),
          h('button', { class: 'toolbar-rotate', onClick: () => emit('rotate') }),
          h('button', { class: 'toolbar-reset', onClick: () => emit('reset') }),
          slots.extra?.(),
        ]);
    },
  }),
}));

vi.mock('./use-image-transform', () => ({
  useImageTransform: () => ({
    imageStyle: { value: {} },
    resetTransform: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    rotateCW: vi.fn(),
    handleWheel: vi.fn(),
    handleDragStart: vi.fn(),
  }),
}));

vi.mock('./use-preview-keyboard', () => ({
  usePreviewKeyboard: vi.fn(),
}));

describe('ImagePreview', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('visible 为 true 时应该渲染预览', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/test.png'],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview').exists()).toBe(true);
    });

    it('visible 为 false 时不应该渲染预览', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: false,
          images: ['https://example.com/test.png'],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview').exists()).toBe(false);
    });
  });

  describe('导航测试', () => {
    it('多张图片时应该显示导航箭头', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png', 'https://example.com/2.png'],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-arrow-left').exists()).toBe(true);
      expect(wrapper.find('.ai-image-preview-arrow-right').exists()).toBe(true);
    });

    it('单张图片时不应该显示导航箭头', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png'],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-arrow-left').exists()).toBe(false);
      expect(wrapper.find('.ai-image-preview-arrow-right').exists()).toBe(false);
    });
  });

  describe('关闭测试', () => {
    it('点击关闭按钮应该关闭预览', async () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png'],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      await wrapper.find('.ai-image-preview-close').trigger('click');

      expect(wrapper.emitted('update:visible')?.[0]).toEqual([false]);
    });

    it('maskClosable 为 true 时点击遮罩应关闭', async () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png'],
          maskClosable: true,
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      await wrapper.find('.ai-image-preview-body').trigger('click');

      expect(wrapper.emitted('update:visible')?.[0]).toEqual([false]);
    });
  });

  describe('Props 测试', () => {
    it('应该支持字符串数组作为 images', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png'],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-img').exists()).toBe(true);
    });

    it('应该支持 ImageItem 对象数组作为 images', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: [{ url: 'https://example.com/1.png', name: 'test' }],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-img').exists()).toBe(true);
    });
  });

  describe('File 类型图片支持', () => {
    it('应该支持 File 对象作为 images', () => {
      const file = new File(['dummy'], 'photo.png', { type: 'image/png' });

      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: [file],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-img').exists()).toBe(true);
    });

    it('应该支持混合类型 images（string + File + ImageItem）', () => {
      const file = new File(['dummy'], 'photo.png', { type: 'image/png' });

      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png', file, { url: 'https://example.com/2.png' }],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-img').exists()).toBe(true);
      expect(wrapper.find('.ai-image-preview-arrow-left').exists()).toBe(true);
    });

    it('应该支持 ImageItem 中仅有 file 字段的情况', () => {
      const file = new File(['dummy'], 'photo.png', { type: 'image/png' });

      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: [{ file, name: 'photo.png' }],
          'onUpdate:visible': () => {},
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.ai-image-preview-img').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持 extra slot', () => {
      wrapper = mount(ImagePreview, {
        props: {
          visible: true,
          images: ['https://example.com/1.png'],
          'onUpdate:visible': () => {},
        },
        slots: {
          extra: '<div class="custom-extra">Extra</div>',
        },
        global: {
          stubs: { Teleport: true },
        },
      });

      expect(wrapper.find('.custom-extra').exists()).toBe(true);
    });
  });
});
