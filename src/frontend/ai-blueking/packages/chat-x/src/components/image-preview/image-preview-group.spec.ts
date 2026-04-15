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

import ImagePreviewGroup from './image-preview-group.vue';

vi.mock('./image-preview.vue', () => ({
  default: defineComponent({
    name: 'ImagePreview',
    props: {
      images: { type: Array, default: () => [] },
      visible: { type: Boolean, default: false },
      current: { type: Number, default: 0 },
      maskClosable: { type: Boolean, default: true },
      onDownload: { type: Function, default: undefined },
      showInfo: { type: Boolean, default: false },
    },
    emits: ['update:visible', 'update:current'],
    setup(props, { slots }) {
      return () => (props.visible ? h('div', { class: 'mock-image-preview' }, slots.default?.()) : null);
    },
  }),
}));

describe('ImagePreviewGroup', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ImagePreviewGroup);

      expect(wrapper.find('.ai-image-preview-group').exists()).toBe(true);
    });

    it('初始时不应该显示预览', () => {
      wrapper = mount(ImagePreviewGroup);

      expect(wrapper.find('.mock-image-preview').exists()).toBe(false);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot', () => {
      wrapper = mount(ImagePreviewGroup, {
        slots: {
          default: '<div class="custom-children">Children</div>',
        },
      });

      expect(wrapper.find('.custom-children').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('maskClosable 默认应该为 true', () => {
      wrapper = mount(ImagePreviewGroup);

      expect(wrapper.props().maskClosable).toBe(true);
    });

    it('showInfo 默认应该为 false', () => {
      wrapper = mount(ImagePreviewGroup);

      expect(wrapper.props().showInfo).toBe(false);
    });
  });
});
