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
import { UploadStatus } from '../../../types';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('../../../icons', () => ({
  CloseIcon: defineComponent({
    name: 'CloseIcon',
    setup() {
      return () => h('span', { class: 'mock-close-icon' });
    },
  }),
  ImageErrorIcon: defineComponent({
    name: 'ImageErrorIcon',
    setup() {
      return () => h('span', { class: 'mock-image-error-icon' });
    },
  }),
}));

vi.mock('../../file-icon/file-icon.vue', () => ({
  default: defineComponent({
    name: 'FileIcon',
    props: { fileName: { type: String, default: '' } },
    setup(props) {
      return () => h('span', { class: 'mock-file-icon', 'data-file-name': props.fileName });
    },
  }),
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

const IMAGE_SELECTOR = '.ai-upload-image-item-thumb';
const FILE_SELECTOR = '.ai-upload-file-item';
const DELETE_SELECTOR = '.ai-upload-image-item-delete, .ai-upload-file-item-delete';

describe('FileContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom 未实现 createObjectURL / revokeObjectURL
    URL.createObjectURL = vi.fn((file: Blob) => `blob:${(file as File).name}`);
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(FileContent, {
        props: { files: [] },
      });

      expect(wrapper.find('.ai-files-content').exists()).toBe(true);
    });

    it('应该按图片渲染缩略图', () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['img'], 'photo.png', { type: 'image/png' }), mimeType: 'image/png' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find(IMAGE_SELECTOR).exists()).toBe(true);
      expect(wrapper.find(FILE_SELECTOR).exists()).toBe(false);
    });

    it('应该按文件卡片渲染非图片文件，并显示文件名与大小', () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }), mimeType: 'application/pdf' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find(FILE_SELECTOR).exists()).toBe(true);
      expect(wrapper.find('.ai-upload-file-item-name').text()).toBe('doc.pdf');
      expect(wrapper.find('.ai-upload-file-item-size').text()).toBe('4.00B');
    });

    it('文件图标应按文件名解析（与文件产物侧栏同一套映射）', () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }), mimeType: 'application/pdf' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find('.mock-file-icon').attributes('data-file-name')).toBe('doc.pdf');
    });

    it('图片应始终排在文件前方', () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }), mimeType: 'application/pdf' },
        { file: new File(['img'], 'photo.png', { type: 'image/png' }), mimeType: 'image/png' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      const rows = wrapper.findAll('.ai-files-content-row');
      expect(rows).toHaveLength(2);
      expect(rows[0].classes()).toContain('is-images');
      expect(rows[1].classes()).toContain('is-files');
    });

    it('应该渲染 ImagePreview 组件', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['img'], 'photo.png', { type: 'image/png' }), mimeType: 'image/png' }],
        },
      });

      expect(wrapper.find('.mock-image-preview').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('readonly 为 false 时应该显示删除按钮', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['data'], 'test.txt', { type: 'text/plain' }), mimeType: 'text/plain' }],
          readonly: false,
        },
      });

      expect(wrapper.find(DELETE_SELECTOR).exists()).toBe(true);
    });

    it('readonly 为 true 时不应该显示删除按钮', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['data'], 'test.txt', { type: 'text/plain' }), mimeType: 'text/plain' }],
          readonly: true,
        },
      });

      expect(wrapper.find(DELETE_SELECTOR).exists()).toBe(false);
    });

    it('variant 默认为 input，图片使用输入态样式', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ url: 'http://example.com/a.png', mimeType: 'image/png', filename: 'a.png' }],
        },
      });

      expect(wrapper.find(IMAGE_SELECTOR).classes()).toContain('is-input');
    });

    it('variant 为 message 时图片使用消息态样式', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ url: 'http://example.com/a.png', mimeType: 'image/png', filename: 'a.png' }],
          variant: 'message' as const,
        },
      });

      expect(wrapper.find('.ai-files-content').classes()).toContain('is-message');
      expect(wrapper.find(IMAGE_SELECTOR).classes()).toContain('is-message');
    });

    it('有 url 但非图片类型的文件应渲染为文件卡片而非缩略图', () => {
      const files: Partial<UploadFile>[] = [
        { url: 'http://example.com/report.pdf', mimeType: 'application/pdf', filename: 'report.pdf' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find(IMAGE_SELECTOR).exists()).toBe(false);
      expect(wrapper.find(FILE_SELECTOR).exists()).toBe(true);
    });

    it('消息态附件带 size 时应显示文件大小', () => {
      const files: Partial<UploadFile>[] = [
        {
          url: 'http://example.com/report.pdf',
          mimeType: 'application/pdf',
          filename: 'report.pdf',
          size: 1024 * 1024,
        },
      ];

      wrapper = mount(FileContent, { props: { files, readonly: true, variant: 'message' as const } });

      expect(wrapper.find('.ai-upload-file-item-size').text()).toBe('1.00M');
    });

    it('消息态附件无 size 时不渲染大小节点', () => {
      const files: Partial<UploadFile>[] = [
        { url: 'http://example.com/report.pdf', mimeType: 'application/pdf', filename: 'report.pdf' },
      ];

      wrapper = mount(FileContent, { props: { files, readonly: true, variant: 'message' as const } });

      expect(wrapper.find('.ai-upload-file-item-size').exists()).toBe(false);
    });
  });

  describe('事件测试', () => {
    it('点击文件删除按钮应该触发 deleteFile 事件', async () => {
      const file: Partial<UploadFile> = {
        file: new File(['data'], 'test.txt', { type: 'text/plain' }),
        mimeType: 'text/plain',
      };

      wrapper = mount(FileContent, {
        props: { files: [file], readonly: false },
      });

      await wrapper.find('.ai-upload-file-item-delete').trigger('click');

      expect(wrapper.emitted('deleteFile')?.[0]).toEqual([file]);
    });

    it('点击图片删除按钮应该触发 deleteFile 事件', async () => {
      const file: Partial<UploadFile> = {
        file: new File(['img'], 'photo.png', { type: 'image/png' }),
        mimeType: 'image/png',
      };

      wrapper = mount(FileContent, {
        props: { files: [file], readonly: false },
      });

      await wrapper.find('.ai-upload-image-item-delete').trigger('click');

      expect(wrapper.emitted('deleteFile')?.[0]).toEqual([file]);
    });

    it('点击图片应该打开预览', async () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['img'], 'photo.png', { type: 'image/png' }), mimeType: 'image/png' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      await wrapper.find(IMAGE_SELECTOR).trigger('click');

      const preview = wrapper.findComponent({ name: 'ImagePreview' });
      expect(preview.props('visible')).toBe(true);
      expect(preview.props('current')).toBe(0);
    });

    it('点击第二张图片应该预览对应索引', async () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['img1'], 'a.png', { type: 'image/png' }), mimeType: 'image/png' },
        { file: new File(['img2'], 'b.jpg', { type: 'image/jpeg' }), mimeType: 'image/jpeg' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      await wrapper.findAll(IMAGE_SELECTOR)[1].trigger('click');

      const preview = wrapper.findComponent({ name: 'ImagePreview' });
      expect(preview.props('current')).toBe(1);
    });

    it('加载失败的图片应降级为错误占位且不进入预览列表', async () => {
      const files: Partial<UploadFile>[] = [
        { file: new File(['img1'], 'broken.png', { type: 'image/png' }), mimeType: 'image/png' },
        { file: new File(['img2'], 'ok.png', { type: 'image/png' }), mimeType: 'image/png' },
      ];

      wrapper = mount(FileContent, { props: { files } });

      await wrapper.findAll(IMAGE_SELECTOR)[0].trigger('error');

      expect(wrapper.find('.mock-image-error-icon').exists()).toBe(true);
      expect(wrapper.findComponent({ name: 'ImagePreview' }).props('images')).toHaveLength(1);
    });
  });

  describe('上传状态展示', () => {
    it('文件上传中应显示遮罩和圈圈 loading，并保留删除', () => {
      const files: Partial<UploadFile>[] = [
        {
          file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }),
          mimeType: 'application/pdf',
          status: UploadStatus.Pending,
        },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find('.ai-upload-file-item').classes()).toContain('is-pending');
      expect(wrapper.find('.ai-upload-file-item-overlay').exists()).toBe(true);
      expect(wrapper.find('.ai-upload-spinner').exists()).toBe(true);
      expect(wrapper.find('.ai-upload-file-item-size').text()).toBe('4.00B');
      expect(wrapper.find('.ai-upload-file-item-delete').exists()).toBe(true);
    });

    it('文件上传失败应显示红色失败态和「上传失败」', () => {
      const files: Partial<UploadFile>[] = [
        {
          file: new File(['data'], 'doc.pdf', { type: 'application/pdf' }),
          mimeType: 'application/pdf',
          status: UploadStatus.Error,
        },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find('.ai-upload-file-item').classes()).toContain('is-error');
      expect(wrapper.find('.ai-upload-file-item-size').text()).toBe('上传失败');
      expect(wrapper.find('.ai-upload-file-item-overlay').exists()).toBe(false);
      expect(wrapper.find('.ai-upload-file-item-delete').exists()).toBe(true);
    });

    it('图片上传中应覆盖 loading，且不可打开预览', async () => {
      const files: Partial<UploadFile>[] = [
        {
          file: new File(['img'], 'photo.png', { type: 'image/png' }),
          mimeType: 'image/png',
          status: UploadStatus.Pending,
        },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find('.ai-upload-image-item').classes()).toContain('is-pending');
      expect(wrapper.find('.ai-upload-image-item-overlay').exists()).toBe(true);
      expect(wrapper.find('.ai-upload-spinner').exists()).toBe(true);
      expect(wrapper.find(IMAGE_SELECTOR).exists()).toBe(true);
      expect(wrapper.find('.ai-upload-image-item-delete').exists()).toBe(true);

      await wrapper.find(IMAGE_SELECTOR).trigger('click');

      expect(wrapper.findComponent({ name: 'ImagePreview' }).props('visible')).toBe(false);
    });

    it('图片上传失败应显示裂图占位而非原图', () => {
      const files: Partial<UploadFile>[] = [
        {
          file: new File(['img'], 'photo.png', { type: 'image/png' }),
          mimeType: 'image/png',
          status: UploadStatus.Error,
        },
      ];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find('.ai-upload-image-item-thumb.is-error').exists()).toBe(true);
      expect(wrapper.find('.mock-image-error-icon').exists()).toBe(true);
      expect(wrapper.find('img.ai-upload-image-item-thumb').exists()).toBe(false);
    });
  });

  describe('资源回收测试', () => {
    it('同一文件多次渲染只创建一个 blob URL', async () => {
      const file: Partial<UploadFile> = {
        file: new File(['img'], 'photo.png', { type: 'image/png' }),
        mimeType: 'image/png',
      };

      wrapper = mount(FileContent, { props: { files: [file] } });
      await wrapper.setProps({ readonly: true });

      expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    });

    it('卸载时应回收已创建的 blob URL', () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['img'], 'photo.png', { type: 'image/png' }), mimeType: 'image/png' }],
        },
      });

      wrapper.unmount();

      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:photo.png');
    });

    it('文件被移除后应回收对应 blob URL', async () => {
      wrapper = mount(FileContent, {
        props: {
          files: [{ file: new File(['img'], 'photo.png', { type: 'image/png' }), mimeType: 'image/png' }],
        },
      });

      await wrapper.setProps({ files: [] });

      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:photo.png');
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空文件列表', () => {
      wrapper = mount(FileContent, { props: { files: [] } });

      expect(wrapper.find('.ai-files-content').exists()).toBe(true);
      expect(wrapper.find('.ai-files-content-row').exists()).toBe(false);
    });

    it('无 mimeType 的文件退回文件卡片，不渲染破图', () => {
      const files: Partial<UploadFile>[] = [{ filename: 'unknown-file' }];

      wrapper = mount(FileContent, { props: { files } });

      expect(wrapper.find(IMAGE_SELECTOR).exists()).toBe(false);
      expect(wrapper.find('.ai-upload-file-item-name').text()).toBe('unknown-file');
    });
  });
});
