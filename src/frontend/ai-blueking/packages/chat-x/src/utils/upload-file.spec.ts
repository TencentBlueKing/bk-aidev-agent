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

import { describe, expect, it } from 'vitest';

import { formatBytes } from './file';
import {
  getFileIdentity,
  getUploadFileKey,
  getUploadFileName,
  getUploadFileSize,
  isUploadImageFile,
  splitUploadFiles,
} from './upload-file';

const createFile = (name: string, type: string, size = 4) =>
  new File([new ArrayBuffer(size)], name, { lastModified: 1000, type });

describe('upload-file', () => {
  describe('getFileIdentity', () => {
    it('应该由文件名 + 大小 + 修改时间组成', () => {
      expect(getFileIdentity(createFile('a.png', 'image/png', 10))).toBe('a.png_10_1000');
    });

    it('同名但大小不同的文件身份应不同', () => {
      expect(getFileIdentity(createFile('a.png', 'image/png', 10))).not.toBe(
        getFileIdentity(createFile('a.png', 'image/png', 20)),
      );
    });
  });

  describe('getUploadFileKey', () => {
    it('待发送态应使用 File 身份', () => {
      expect(getUploadFileKey({ file: createFile('a.png', 'image/png', 10) })).toBe('a.png_10_1000');
    });

    it('上传成功回填 url 后 key 应保持不变', () => {
      const file = createFile('a.png', 'image/png', 10);

      expect(getUploadFileKey({ file, url: 'http://example.com/a.png' })).toBe(getUploadFileKey({ file }));
    });

    it('已发送态应退回 url', () => {
      expect(getUploadFileKey({ filename: 'a.png', url: 'http://example.com/a.png' })).toBe(
        'http://example.com/a.png',
      );
    });

    it('无 File 无 url 时应退回文件名', () => {
      expect(getUploadFileKey({ filename: 'a.png' })).toBe('a.png');
    });
  });

  describe('isUploadImageFile', () => {
    it('mimeType 为图片时应判定为图片', () => {
      expect(isUploadImageFile({ mimeType: 'image/png' })).toBe(true);
    });

    it('缺省 mimeType 时应回退 File.type', () => {
      expect(isUploadImageFile({ file: createFile('a.png', 'image/png') })).toBe(true);
    });

    it('有 url 但类型非图片时不应判定为图片', () => {
      expect(isUploadImageFile({ mimeType: 'application/pdf', url: 'http://example.com/a.pdf' })).toBe(false);
    });

    it('无类型信息时不应判定为图片', () => {
      expect(isUploadImageFile({ filename: 'unknown' })).toBe(false);
    });
  });

  describe('getUploadFileName / getUploadFileSize', () => {
    it('文件名应优先取 filename', () => {
      expect(getUploadFileName({ file: createFile('local.png', 'image/png'), filename: 'remote.png' })).toBe(
        'remote.png',
      );
    });

    it('无 filename 时应取 File.name', () => {
      expect(getUploadFileName({ file: createFile('local.png', 'image/png') })).toBe('local.png');
    });

    it('大小应优先取 File.size', () => {
      expect(getUploadFileSize({ file: createFile('a.png', 'image/png', 10), size: 999 })).toBe(10);
    });

    it('无 File 时应取消息内下发的 size', () => {
      expect(getUploadFileSize({ size: 999 })).toBe(999);
    });

    it('两者都没有时应为 undefined', () => {
      expect(getUploadFileSize({ filename: 'a.png' })).toBeUndefined();
    });
  });

  describe('formatBytes', () => {
    it('应按 1024 进阶换算并保留两位小数', () => {
      expect(formatBytes(512)).toBe('512.00B');
      expect(formatBytes(2048)).toBe('2.00KB');
      expect(formatBytes(1024 * 1024)).toBe('1.00M');
      expect(formatBytes(2 * 1024 * 1024 * 1024)).toBe('2.00GB');
    });

    it('大小缺省或为 0 时应返回空串', () => {
      expect(formatBytes()).toBe('');
      expect(formatBytes(0)).toBe('');
    });
  });

  describe('splitUploadFiles', () => {
    it('应分出图片组与其他文件组，且保持组内原有顺序', () => {
      const pdf = { filename: 'a.pdf', mimeType: 'application/pdf' };
      const png = { filename: 'b.png', mimeType: 'image/png' };
      const csv = { filename: 'c.csv', mimeType: 'text/csv' };
      const jpg = { filename: 'd.jpg', mimeType: 'image/jpeg' };

      const { imageFiles, otherFiles } = splitUploadFiles([pdf, png, csv, jpg]);

      expect(imageFiles).toEqual([png, jpg]);
      expect(otherFiles).toEqual([pdf, csv]);
    });

    it('空列表应返回两个空数组', () => {
      expect(splitUploadFiles([])).toEqual({ imageFiles: [], otherFiles: [] });
    });
  });
});
