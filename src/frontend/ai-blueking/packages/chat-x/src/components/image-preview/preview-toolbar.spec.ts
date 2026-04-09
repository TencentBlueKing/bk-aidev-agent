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

import PreviewToolbar from './preview-toolbar.vue';

vi.mock('../../icons/image-preview', () => ({
  DownloadIcon: defineComponent({
    name: 'DownloadIcon',
    setup() {
      return () => h('span', { class: 'mock-download-icon' });
    },
  }),
  FitScreenIcon: defineComponent({
    name: 'FitScreenIcon',
    setup() {
      return () => h('span', { class: 'mock-reset-icon' });
    },
  }),
  ImageSizeIcon: defineComponent({
    name: 'ImageSizeIcon',
    setup() {
      return () => h('span', { class: 'mock-info-icon' });
    },
  }),
  RotateIcon: defineComponent({
    name: 'RotateIcon',
    setup() {
      return () => h('span', { class: 'mock-rotate-icon' });
    },
  }),
  ZoomInIcon: defineComponent({
    name: 'ZoomInIcon',
    setup() {
      return () => h('span', { class: 'mock-zoom-in-icon' });
    },
  }),
  ZoomOutIcon: defineComponent({
    name: 'ZoomOutIcon',
    setup() {
      return () => h('span', { class: 'mock-zoom-out-icon' });
    },
  }),
}));

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

describe('PreviewToolbar', () => {
  let wrapper: VueWrapper;

  const defaultProps = {
    activeIndex: 0,
    isMultiple: false,
    showInfo: false,
    total: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      expect(wrapper.find('.ai-image-preview-toolbar').exists()).toBe(true);
    });

    it('应该渲染工具栏按钮', () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      expect(wrapper.findAll('.ai-image-preview-toolbar-btn').length).toBeGreaterThan(0);
    });
  });

  describe('页码测试', () => {
    it('isMultiple 为 true 时应该显示页码', () => {
      wrapper = mount(PreviewToolbar, {
        props: { ...defaultProps, isMultiple: true, total: 5, activeIndex: 2 },
      });

      expect(wrapper.find('.ai-image-preview-toolbar-pages').exists()).toBe(true);
      expect(wrapper.find('.ai-image-preview-toolbar-pages').text()).toContain('3');
      expect(wrapper.find('.ai-image-preview-toolbar-pages').text()).toContain('5');
    });

    it('isMultiple 为 false 时不应该显示页码', () => {
      wrapper = mount(PreviewToolbar, {
        props: { ...defaultProps, isMultiple: false },
      });

      expect(wrapper.find('.ai-image-preview-toolbar-pages').exists()).toBe(false);
    });

    it('isMultiple 为 true 时应该显示分隔符', () => {
      wrapper = mount(PreviewToolbar, {
        props: { ...defaultProps, isMultiple: true, total: 3 },
      });

      expect(wrapper.find('.ai-image-preview-toolbar-divider').exists()).toBe(true);
    });

    it('isMultiple 为 false 时不应该显示分隔符', () => {
      wrapper = mount(PreviewToolbar, {
        props: { ...defaultProps, isMultiple: false },
      });

      expect(wrapper.find('.ai-image-preview-toolbar-divider').exists()).toBe(false);
    });
  });

  describe('图片信息测试', () => {
    it('showInfo 为 true 且有信息时应该显示图片信息', () => {
      wrapper = mount(PreviewToolbar, {
        props: {
          ...defaultProps,
          showInfo: true,
          currentImageInfo: { width: 1920, resolution: '1920x1080' },
        },
      });

      expect(wrapper.find('.ai-image-preview-toolbar-info').exists()).toBe(true);
    });

    it('showInfo 为 false 时不应该显示图片信息', () => {
      wrapper = mount(PreviewToolbar, {
        props: {
          ...defaultProps,
          showInfo: false,
          currentImageInfo: { width: 1920 },
        },
      });

      expect(wrapper.find('.ai-image-preview-toolbar-info').exists()).toBe(false);
    });
  });

  describe('事件测试', () => {
    it('点击放大按钮应该触发 zoomIn 事件', async () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      const zoomInBtn = wrapper
        .findAll('.ai-image-preview-toolbar-btn')
        .find(btn => btn.attributes('data-tooltip') === '放大');
      await zoomInBtn?.trigger('click');

      expect(wrapper.emitted('zoomIn')).toBeTruthy();
    });

    it('点击缩小按钮应该触发 zoomOut 事件', async () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      const zoomOutBtn = wrapper
        .findAll('.ai-image-preview-toolbar-btn')
        .find(btn => btn.attributes('data-tooltip') === '缩小');
      await zoomOutBtn?.trigger('click');

      expect(wrapper.emitted('zoomOut')).toBeTruthy();
    });

    it('点击旋转按钮应该触发 rotate 事件', async () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      const rotateBtn = wrapper
        .findAll('.ai-image-preview-toolbar-btn')
        .find(btn => btn.attributes('data-tooltip') === '旋转');
      await rotateBtn?.trigger('click');

      expect(wrapper.emitted('rotate')).toBeTruthy();
    });

    it('点击重置按钮应该触发 reset 事件', async () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      const resetBtn = wrapper
        .findAll('.ai-image-preview-toolbar-btn')
        .find(btn => btn.attributes('data-tooltip') === '重置');
      await resetBtn?.trigger('click');

      expect(wrapper.emitted('reset')).toBeTruthy();
    });

    it('点击下载按钮应该触发 download 事件', async () => {
      wrapper = mount(PreviewToolbar, { props: defaultProps });

      const downloadBtn = wrapper
        .findAll('.ai-image-preview-toolbar-btn')
        .find(btn => btn.attributes('data-tooltip') === '下载');
      await downloadBtn?.trigger('click');

      expect(wrapper.emitted('download')).toBeTruthy();
    });
  });

  describe('Slot 测试', () => {
    it('应该支持 extra slot', () => {
      wrapper = mount(PreviewToolbar, {
        props: defaultProps,
        slots: {
          extra: '<div class="custom-extra">Extra</div>',
        },
      });

      expect(wrapper.find('.custom-extra').exists()).toBe(true);
    });
  });
});
