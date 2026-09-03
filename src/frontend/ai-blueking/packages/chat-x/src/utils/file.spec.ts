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

import {
  formatDefaultUploadAcceptTip,
  isDefaultUploadAccept,
  isFileAcceptedByAccept,
  normalizeAcceptTokens,
} from './file';
import { ALLOWED_UPLOAD_EXTENSIONS, DEFAULT_UPLOAD_ACCEPT } from './upload-accept';

const createFile = (name: string, type = ''): File => new File(['x'], name, { type });

describe('normalizeAcceptTokens', () => {
  it('应按逗号拆分、去空、转小写并去重排序', () => {
    expect(normalizeAcceptTokens('.PNG, .jpg, .png')).toEqual(['.jpg', '.png']);
  });
});

describe('isDefaultUploadAccept', () => {
  it('缺省或空串不是默认列表', () => {
    expect(isDefaultUploadAccept()).toBe(false);
    expect(isDefaultUploadAccept('')).toBe(false);
  });

  it('与默认列表顺序无关时应判定为同一份', () => {
    const reversed = [...normalizeAcceptTokens(DEFAULT_UPLOAD_ACCEPT)].reverse().join(',');
    expect(isDefaultUploadAccept(DEFAULT_UPLOAD_ACCEPT)).toBe(true);
    expect(isDefaultUploadAccept(reversed)).toBe(true);
  });

  it('收窄后的 accept 不应判定为默认列表', () => {
    expect(isDefaultUploadAccept('.pdf,.doc')).toBe(false);
  });
});

describe('isFileAcceptedByAccept', () => {
  it('未传 accept 时应放行任意文件', () => {
    expect(isFileAcceptedByAccept(createFile('a.exe'))).toBe(true);
    expect(isFileAcceptedByAccept(createFile('a.exe'), '  ')).toBe(true);
  });

  it('应按扩展名匹配默认允许列表，忽略大小写', () => {
    expect(isFileAcceptedByAccept(createFile('shot.PNG', 'image/png'), DEFAULT_UPLOAD_ACCEPT)).toBe(true);
    expect(isFileAcceptedByAccept(createFile('main.ts'), DEFAULT_UPLOAD_ACCEPT)).toBe(true);
    expect(isFileAcceptedByAccept(createFile('virus.exe'), DEFAULT_UPLOAD_ACCEPT)).toBe(false);
    expect(isFileAcceptedByAccept(createFile('archive.zip'), DEFAULT_UPLOAD_ACCEPT)).toBe(false);
  });

  it('无扩展名且未命中 mime 时应拒绝', () => {
    expect(isFileAcceptedByAccept(createFile('Makefile'), DEFAULT_UPLOAD_ACCEPT)).toBe(false);
  });

  it('应支持 mime 与通配符', () => {
    expect(isFileAcceptedByAccept(createFile('a.bin', 'image/png'), 'image/*')).toBe(true);
    expect(isFileAcceptedByAccept(createFile('a.bin', 'application/pdf'), 'image/*')).toBe(false);
    expect(isFileAcceptedByAccept(createFile('a.bin'), '*/*')).toBe(true);
  });
});

describe('formatDefaultUploadAcceptTip', () => {
  it('类别名缩短，冒号后接扩展名，超出 5 个时用「 等」收尾', () => {
    const preview = (extensions: readonly string[], ellipsis: string) =>
      extensions.length > 5 ? `${extensions.slice(0, 5).join(' ')}${ellipsis}` : extensions.join(' ');

    expect(formatDefaultUploadAcceptTip(false).split('\n')).toEqual([
      `图片:${preview(ALLOWED_UPLOAD_EXTENSIONS.image, ' 等')}`,
      `文档:${preview(ALLOWED_UPLOAD_EXTENSIONS.document, ' 等')}`,
      `文本:${preview(ALLOWED_UPLOAD_EXTENSIONS.text, ' 等')}`,
      `代码:${preview(ALLOWED_UPLOAD_EXTENSIONS.code, ' 等')}`,
    ]);
    expect(formatDefaultUploadAcceptTip(true).split('\n')).toEqual([
      `Images:${preview(ALLOWED_UPLOAD_EXTENSIONS.image, ' etc.')}`,
      `Documents:${preview(ALLOWED_UPLOAD_EXTENSIONS.document, ' etc.')}`,
      `Text:${preview(ALLOWED_UPLOAD_EXTENSIONS.text, ' etc.')}`,
      `Code:${preview(ALLOWED_UPLOAD_EXTENSIONS.code, ' etc.')}`,
    ]);
  });
});
