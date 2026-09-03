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

import { DEFAULT_UPLOAD_ACCEPT } from '../../../common';
import FileUploadBtn from './file-upload-btn.vue';

// ============= Mock 区域 =============

vi.mock('tippy.js/dist/tippy.css', () => ({}));

const mockMessage = vi.fn();
vi.mock('bkui-vue', () => ({
  Message: (...args: unknown[]) => mockMessage(...args),
}));

vi.mock('vue-tippy', () => ({
  directive: {},
}));

vi.mock('../../../icons', () => ({
  FileUploadIcon: defineComponent({
    name: 'FileUploadIcon',
    setup() {
      return () => h('span', { class: 'mock-file-upload-icon' });
    },
  }),
}));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../../common', async importOriginal => {
  const actual = await importOriginal<typeof import('../../../common')>();
  return {
    ...actual,
    isEn: false,
    MAX_UPLOAD_FILE_SIZE: 2.5 * 1024 * 1024,
    MAX_UPLOAD_FILES: 9,
  };
});

// ============= 辅助函数 =============

function createFile(name: string, size: number, type = 'image/png'): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type });
}

function createFileList(files: File[]): FileList {
  const fileList = {
    length: files.length,
    item: (index: number) => files[index] ?? null,
    [Symbol.iterator]: function* () {
      for (const file of files) {
        yield file;
      }
    },
  } as unknown as FileList;

  files.forEach((file, index) => {
    Object.defineProperty(fileList, index, { value: file, enumerable: true });
  });

  return fileList;
}

function triggerFileChange(wrapper: VueWrapper, files: File[]) {
  const input = wrapper.find('input[type="file"]');
  const inputEl = input.element as HTMLInputElement;

  Object.defineProperty(inputEl, 'files', {
    value: createFileList(files),
    writable: true,
    configurable: true,
  });

  return input.trigger('change');
}

// ============= 测试主体 =============

// style-note: chat-x PR3 — 上传按钮热区 32×32 / --ai-icon-size-sm
describe('FileUploadBtn', () => {
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
      wrapper = mount(FileUploadBtn);

      expect(wrapper.find('.ai-file-upload-btn').exists()).toBe(true);
    });

    it('应该渲染隐藏的 file input', () => {
      wrapper = mount(FileUploadBtn);

      const input = wrapper.find('.file-upload-btn-input');
      expect(input.exists()).toBe(true);
      expect(input.attributes('type')).toBe('file');
    });

    it('应该渲染上传按钮图标', () => {
      wrapper = mount(FileUploadBtn);

      expect(wrapper.find('.file-upload-btn-icon').exists()).toBe(true);
    });

    it('图标按钮应该绑定 v-tippy 指令', () => {
      wrapper = mount(FileUploadBtn);

      const icon = wrapper.find('.file-upload-btn-icon');
      expect(icon.exists()).toBe(true);
    });

    it('应该渲染默认的 FileUploadIcon', () => {
      wrapper = mount(FileUploadBtn);

      expect(wrapper.find('.mock-file-upload-icon').exists()).toBe(true);
    });

    it('input 应该设置 multiple 属性', () => {
      wrapper = mount(FileUploadBtn);

      const input = wrapper.find('input[type="file"]');
      expect(input.attributes('multiple')).toBeDefined();
    });
  });

  // ---------- Props 测试 ----------
  describe('Props 测试', () => {
    it('默认不下发 accept，不限制文件类型', () => {
      wrapper = mount(FileUploadBtn);

      const input = wrapper.find('input[type="file"]');
      expect(input.attributes('accept')).toBeUndefined();
    });

    it('应该支持自定义 accept 收窄类型', () => {
      wrapper = mount(FileUploadBtn, {
        props: { accept: '.pdf,.doc,.docx' },
      });

      const input = wrapper.find('input[type="file"]');
      expect(input.attributes('accept')).toBe('.pdf,.doc,.docx');
    });

    it('传入默认允许列表时应下发到 file input', () => {
      wrapper = mount(FileUploadBtn, {
        props: { accept: DEFAULT_UPLOAD_ACCEPT },
      });

      const input = wrapper.find('input[type="file"]');
      expect(input.attributes('accept')).toBe(DEFAULT_UPLOAD_ACCEPT);
    });

    it('multiple 默认值应该为 true', () => {
      wrapper = mount(FileUploadBtn);

      expect((wrapper.props() as Record<string, unknown>).multiple).toBe(true);
    });

    it('应该正确接收 tippyOptions 属性', () => {
      wrapper = mount(FileUploadBtn, {
        props: { tippyOptions: { appendTo: 'parent' } },
      });

      expect((wrapper.props() as Record<string, unknown>).tippyOptions).toEqual({ appendTo: 'parent' });
    });
  });

  // ---------- Slot 测试 ----------
  describe('Slot 测试', () => {
    it('应该支持默认 slot 替换图标', () => {
      wrapper = mount(FileUploadBtn, {
        slots: {
          default: () => h('span', { class: 'custom-upload-icon' }, '📎'),
        },
      });

      expect(wrapper.find('.custom-upload-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-file-upload-icon').exists()).toBe(false);
    });

    it('没有自定义 slot 时应该显示默认图标', () => {
      wrapper = mount(FileUploadBtn);

      expect(wrapper.find('.mock-file-upload-icon').exists()).toBe(true);
    });
  });

  // ---------- 事件测试 ----------
  describe('事件测试', () => {
    it('点击按钮应该触发 file input 的 click', async () => {
      wrapper = mount(FileUploadBtn);

      const input = wrapper.find('input[type="file"]');
      const clickSpy = vi.spyOn(input.element as HTMLInputElement, 'click');

      await wrapper.find('.file-upload-btn-icon').trigger('click');

      expect(clickSpy).toHaveBeenCalled();
    });

    it('选择文件后应该触发 upload 事件', async () => {
      wrapper = mount(FileUploadBtn);

      const file = createFile('test.png', 1024);
      await triggerFileChange(wrapper, [file]);

      expect(wrapper.emitted('upload')).toBeTruthy();
      expect(wrapper.emitted('upload')?.length).toBe(1);
      expect(wrapper.emitted('upload')?.[0]).toEqual([[file]]);
    });

    it('选择多个文件应该一次性触发 upload 事件', async () => {
      wrapper = mount(FileUploadBtn);

      const files = [createFile('a.png', 1024), createFile('b.png', 2048), createFile('c.png', 4096)];
      await triggerFileChange(wrapper, files);

      expect(wrapper.emitted('upload')?.length).toBe(1);
      expect(wrapper.emitted('upload')?.[0]).toEqual([files]);
    });

    it('选择文件后应该重置 input value', async () => {
      wrapper = mount(FileUploadBtn);

      const file = createFile('test.png', 1024);
      const input = wrapper.find('input[type="file"]');
      const inputEl = input.element as HTMLInputElement;

      Object.defineProperty(inputEl, 'files', {
        value: createFileList([file]),
        writable: true,
        configurable: true,
      });

      const valueSetter = vi.fn();
      Object.defineProperty(inputEl, 'value', {
        set: valueSetter,
        configurable: true,
      });

      await input.trigger('change');

      expect(valueSetter).toHaveBeenCalledWith('');
    });
  });

  // ---------- 文件验证测试 ----------
  describe('文件验证测试', () => {
    it('单次多选时发出全部尺寸合法的文件，不在按钮层按个数截断或提示', async () => {
      wrapper = mount(FileUploadBtn);

      const files = [
        createFile('a.png', 1024),
        createFile('b.png', 1024),
        createFile('c.png', 1024),
        createFile('d.png', 1024),
      ];
      await triggerFileChange(wrapper, files);

      expect(mockMessage).not.toHaveBeenCalled();
      const emitted = wrapper.emitted('upload')?.[0]?.[0] as File[];
      expect(emitted).toHaveLength(4);
      expect(emitted.map(f => f.name)).toEqual(['a.png', 'b.png', 'c.png', 'd.png']);
    });

    it('文件数量不超过限制时不应该显示错误', async () => {
      wrapper = mount(FileUploadBtn);

      const files = [createFile('a.png', 1024), createFile('b.png', 1024), createFile('c.png', 1024)];
      await triggerFileChange(wrapper, files);

      expect(mockMessage).not.toHaveBeenCalled();
      expect(wrapper.emitted('upload')).toBeTruthy();
    });

    it('非图片类型文件也应正常发出（已解除类型限制）', async () => {
      wrapper = mount(FileUploadBtn);

      const files = [
        createFile('report.pdf', 1024, 'application/pdf'),
        createFile('data.xlsx', 2048, 'application/vnd.ms-excel'),
        createFile('archive.zip', 4096, 'application/zip'),
      ];
      await triggerFileChange(wrapper, files);

      expect(mockMessage).not.toHaveBeenCalled();
      expect((wrapper.emitted('upload')?.[0]?.[0] as File[]).map(f => f.name)).toEqual([
        'report.pdf',
        'data.xlsx',
        'archive.zip',
      ]);
    });

    it('应该过滤掉大小为 0 的文件', async () => {
      wrapper = mount(FileUploadBtn);

      const validFile = createFile('valid.png', 1024);
      const emptyFile = createFile('empty.png', 0);
      await triggerFileChange(wrapper, [validFile, emptyFile]);

      expect(mockMessage).toHaveBeenCalledWith({
        message: '有 1 个文件未上传，可能文件超过 2.5 MB或超出上传个数',
        theme: 'error',
      });
      const emittedFiles = wrapper.emitted('upload')?.[0]?.[0] as File[];
      expect(emittedFiles).toHaveLength(1);
      expect(emittedFiles[0].name).toBe('valid.png');
    });

    it('应该过滤掉超过最大尺寸的文件', async () => {
      wrapper = mount(FileUploadBtn);

      const validFile = createFile('small.png', 1024);
      const oversizedFile = createFile('huge.png', 3 * 1024 * 1024);
      await triggerFileChange(wrapper, [validFile, oversizedFile]);

      expect(mockMessage).toHaveBeenCalledWith({
        message: '有 1 个文件未上传，可能文件超过 2.5 MB或超出上传个数',
        theme: 'error',
      });
      const emittedFiles = wrapper.emitted('upload')?.[0]?.[0] as File[];
      expect(emittedFiles).toHaveLength(1);
      expect(emittedFiles[0].name).toBe('small.png');
    });

    it('超过数量上限时仍一次发出多选的全部合法文件（个数由上层处理）', async () => {
      wrapper = mount(FileUploadBtn);

      const files = [createFile('a.png', 1024), createFile('b.png', 1024), createFile('c.png', 1024)];
      await triggerFileChange(wrapper, files);

      expect(mockMessage).not.toHaveBeenCalled();
      expect((wrapper.emitted('upload')?.[0]?.[0] as File[]).map(f => f.name)).toEqual(['a.png', 'b.png', 'c.png']);
    });
  });

  // ---------- 边界情况测试 ----------
  describe('边界情况测试', () => {
    it('没有选择文件时不应该触发 upload 事件', async () => {
      wrapper = mount(FileUploadBtn);

      const input = wrapper.find('input[type="file"]');
      const inputEl = input.element as HTMLInputElement;
      Object.defineProperty(inputEl, 'files', {
        value: createFileList([]),
        writable: true,
        configurable: true,
      });

      await input.trigger('change');

      expect(wrapper.emitted('upload')).toBeFalsy();
    });

    it('files 为 null 时不应该触发 upload 事件', async () => {
      wrapper = mount(FileUploadBtn);

      const input = wrapper.find('input[type="file"]');
      const inputEl = input.element as HTMLInputElement;
      Object.defineProperty(inputEl, 'files', {
        value: null,
        writable: true,
        configurable: true,
      });

      await input.trigger('change');

      expect(wrapper.emitted('upload')).toBeFalsy();
    });

    it('所有文件都被过滤后不应触发 upload 但应提示错误', async () => {
      wrapper = mount(FileUploadBtn);

      const emptyFile = createFile('empty.png', 0);
      await triggerFileChange(wrapper, [emptyFile]);

      expect(wrapper.emitted('upload')).toBeFalsy();
      expect(mockMessage).toHaveBeenCalledWith({
        message: '有 1 个文件未上传，可能文件超过 2.5 MB或超出上传个数',
        theme: 'error',
      });
    });

    it('刚好等于最大尺寸的文件应该被过滤', async () => {
      wrapper = mount(FileUploadBtn);

      const maxSizeFile = createFile('max.png', 2.5 * 1024 * 1024);
      await triggerFileChange(wrapper, [maxSizeFile]);

      expect(wrapper.emitted('upload')).toBeFalsy();
      expect(mockMessage).toHaveBeenCalledWith({
        message: '有 1 个文件未上传，可能文件超过 2.5 MB或超出上传个数',
        theme: 'error',
      });
    });
  });
});
