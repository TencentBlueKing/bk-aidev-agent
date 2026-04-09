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

import FileContent from './file-content.vue';

import type { UploadFile } from '../../../types';

vi.mock('../../../icons', () => ({
  DeleteCircleIcon: defineComponent({
    name: 'DeleteCircleIcon',
    emits: ['click'],
    setup(_, { emit }) {
      return () =>
        h('span', {
          class: 'mock-delete-icon',
          onClick: () => emit('click'),
        });
    },
  }),
  DocumentIcon: defineComponent({
    name: 'DocumentIcon',
    setup() {
      return () => h('span', { class: 'mock-document-icon' });
    },
  }),
  ImageErrorIcon: defineComponent({
    name: 'ImageErrorIcon',
    setup() {
      return () => h('span', { class: 'mock-image-error-icon' });
    },
  }),
}));

vi.mock('../../../utils', () => ({
  formatFileSize: (file?: File) => (file ? `${file.size}B` : ''),
  getFileExtension: (file?: File) => (file ? file.name.split('.').pop() || '' : ''),
  getFilePreviewUrl: (file?: File) => (file ? `blob:preview-${file.name}` : ''),
  isImageFile: (mimeType?: string) => !!mimeType?.startsWith('image/'),
}));

vi.mock('../../image-preview/image-preview.vue', () => ({
  default: defineComponent({
    name: 'ImagePreview',
    props: {
      visible: { type: Boolean, default: false },
      current: { type: Number, default: 0 },
      images: { type: Array, default: () => [] },
    },
    emits: ['update:visible', 'update:current'],
    setup(props) {
      return () => h('div', { class: 'mock-image-preview', 'data-visible': String(props.visible) });
    },
  }),
}));

describe('FileContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [],
        },
      });

      expect(wrapper.find('.ai-files-content').exists()).toBe(true);
    });

    it('应该渲染图片文件', () => {
      const files: Partial<UploadFile>[] = [{ file: new File(['img'], 'photo.png', { type: 'image/png' }) }];

      wrapper = mount(FileContent, {
        props: { files },
      });

      expect(wrapper.find('.file-content-image').exists()).toBe(true);
    });

    it('应该渲染非图片文件', () => {
      const files: Partial<UploadFile>[] = [{ file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }) }];

      wrapper = mount(FileContent, {
        props: { files },
      });

      expect(wrapper.find('.file-content-object').exists()).toBe(true);
      expect(wrapper.find('.file-name').text()).toBe('doc.pdf');
    });

    it('应该渲染 ImagePreview 组件', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['img'], 'photo.png', { type: 'image/png' }) }],
        },
      });

      expect(wrapper.find('.mock-image-preview').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('readonly 为 false 时应该显示删除按钮', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['data'], 'test.txt', { type: 'text/plain' }) }],
          readonly: false,
        },
      });

      expect(wrapper.find('.mock-delete-icon').exists()).toBe(true);
    });

    it('readonly 为 true 时不应该显示删除按钮', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['data'], 'test.txt', { type: 'text/plain' }) }],
          readonly: true,
        },
      });

      expect(wrapper.find('.mock-delete-icon').exists()).toBe(false);
    });

    it('有 url 的文件应被识别为图片', () => {
      const files: Partial<UploadFile>[] = [{ url: 'http://example.com/image.png', filename: 'image.png' }];

      wrapper = mount(FileContent, {
        props: { files },
      });

      expect(wrapper.find('.file-content-image').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击删除按钮应该触发 deleteFile 事件', async () => {
      const file: Partial<UploadFile> = { file: new File(['data'], 'test.txt', { type: 'text/plain' }) };

      wrapper = mount(FileContent, {
        props: {
          files: [file],
          readonly: false,
        },
      });

      await wrapper.find('.mock-delete-icon').trigger('click');

      expect(wrapper.emitted('deleteFile')).toBeTruthy();
      expect(wrapper.emitted('deleteFile')?.[0]).toEqual([file]);
    });

    it('点击图片应该打开预览', async () => {
      const files: Partial<UploadFile>[] = [{ file: new File(['img'], 'photo.png', { type: 'image/png' }) }];

      wrapper = mount(FileContent, {
        props: { files },
      });

      await wrapper.find('.file-content-image').trigger('click');

      const preview = wrapper.findComponent({ name: 'ImagePreview' });
      expect(preview.props('visible')).toBe(true);
      expect(preview.props('current')).toBe(0);
    });

    it('点击第二张图片应该预览对应索引', async () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['img1'], 'a.png', { type: 'image/png' }) },
        { file: new File(['img2'], 'b.jpg', { type: 'image/jpeg' }) },
      ];

      wrapper = mount(FileContent, {
        props: { files },
      });

      const images = wrapper.findAll('.file-content-image');
      await images[1].trigger('click');

      const preview = wrapper.findComponent({ name: 'ImagePreview' });
      expect(preview.props('visible')).toBe(true);
      expect(preview.props('current')).toBe(1);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空文件列表', () => {
      wrapper = mount(FileContent, {
        props: { files: [] },
      });

      expect(wrapper.find('.ai-files-content').exists()).toBe(true);
      expect(wrapper.find('.file-content').exists()).toBe(false);
    });

    it('应该正确渲染混合类型文件', () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['img'], 'photo.png', { type: 'image/png' }) },
        { file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }) },
      ];

      wrapper = mount(FileContent, {
        props: { files },
      });

      expect(wrapper.find('.file-content-image').exists()).toBe(true);
      expect(wrapper.find('.file-content-object').exists()).toBe(true);
    });
  });
});
