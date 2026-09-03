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

import { ALLOWED_UPLOAD_EXTENSIONS, DEFAULT_UPLOAD_ACCEPT } from './upload-accept';

/**
 * 判断文件是否为图片文件
 * @param file 文件
 * @returns 是否为图片文件
 */
export const isImageFile = (mimeType?: string): boolean => {
  if (!mimeType) return false;
  return mimeType.startsWith('image/');
};
/**
 * 获取文件预览 URL
 * @param file 文件
 * @returns 文件预览 URL
 */
export const getFilePreviewUrl = (file?: File): string => {
  if (!file) return '';
  return URL.createObjectURL(file);
};

/**
 * 获取文件扩展名
 * @param file 文件
 * @returns 文件扩展名
 */
export const getFileExtension = (file?: File): string => {
  if (!file) return '';
  return file.name.split('.').pop() || file.type?.split('/').pop() || '';
};

/**
 * 格式化字节数及单位展示
 * @param size 字节数
 * @returns 1024B -> 1KB 1024KB -> 1M 1024M -> 1GB；大小未知时返回空串
 */
export const formatBytes = (size?: number): string => {
  if (!size || size <= 0) return '';
  const units = ['B', 'KB', 'M', 'GB'];
  const index = Math.min(Math.floor(Math.log2(size) / 10), units.length - 1);
  return `${(size / 1024 ** index).toFixed(2)}${units[index]}`;
};

/**
 * 格式化文件大小 及 单位展示
 * @param file 文件
 * @returns 1024B -> 1KB 1024KB -> 1M 1024M -> 1GB
 */
export const formatFileSize = (file?: File): string => formatBytes(file?.size);

/**
 * 未成功添加的文件统一提示（中文在数量为 1 时不带「n个」前缀）
 */
export const formatUploadNotAddedMessage = (count: number, maxMb: string, isEn: boolean): string => {
  if (count < 1) {
    return '';
  }
  if (isEn) {
    // if (count === 1) {
    //   return `The file was not uploaded; it may exceed ${maxMb} MB or the upload count limit.`;
    // }
    return `${count} files were not uploaded; they may exceed ${maxMb} MB or the upload count limit.`;
  }
  // if (count === 1) {
  //   return `文件未上传，可能文件超过 ${maxMb} MB或超出上传个数`;
  // }
  return `有 ${count} 个文件未上传，可能文件超过 ${maxMb} MB或超出上传个数`;
};

/** 将 accept 规范串拆成去重、小写、排序后的 token，便于比较与匹配 */
export const normalizeAcceptTokens = (accept: string): string[] =>
  [
    ...new Set(
      accept
        .split(',')
        .map(item => item.trim().toLowerCase())
        .filter(Boolean),
    ),
  ].sort();

/** 当前 accept 是否就是对话默认允许列表（忽略顺序与大小写） */
export const isDefaultUploadAccept = (accept?: string): boolean => {
  if (!accept) {
    return false;
  }
  const current = normalizeAcceptTokens(accept);
  const defaults = normalizeAcceptTokens(DEFAULT_UPLOAD_ACCEPT);
  return current.length === defaults.length && current.every((token, index) => token === defaults[index]);
};

/** tooltip 每一类最多展示的扩展名数量，超出用「等」收尾 */
const UPLOAD_ACCEPT_TIP_PREVIEW_COUNT = 5;

/** 类别扩展名预览：最多 5 个，超出追加「等」 */
const formatExtensionPreview = (extensions: readonly string[], isEn: boolean): string => {
  const shown = extensions.slice(0, UPLOAD_ACCEPT_TIP_PREVIEW_COUNT).join(' ');
  if (extensions.length <= UPLOAD_ACCEPT_TIP_PREVIEW_COUNT) {
    return shown;
  }
  return isEn ? `${shown} etc.` : `${shown} 等`;
};

/** 默认允许列表的分类说明，与 ALLOWED_UPLOAD_EXTENSIONS 同源；每一类单独一行 */
export const formatDefaultUploadAcceptTip = (isEn: boolean): string => {
  const image = formatExtensionPreview(ALLOWED_UPLOAD_EXTENSIONS.image, isEn);
  const document = formatExtensionPreview(ALLOWED_UPLOAD_EXTENSIONS.document, isEn);
  const text = formatExtensionPreview(ALLOWED_UPLOAD_EXTENSIONS.text, isEn);
  const code = formatExtensionPreview(ALLOWED_UPLOAD_EXTENSIONS.code, isEn);
  if (isEn) {
    return [`Images: ${image}`, `Documents: ${document}`, `Text: ${text}`, `Code: ${code}`].join('\n');
  }
  return [`图片: ${image}`, `文档: ${document}`, `文本: ${text}`, `代码: ${code}`].join('\n');
};

/** 取文件名最后一段扩展名（含点）；无扩展名返回空串 */
const getFileNameExtension = (fileName: string): string => {
  const lastDot = fileName.lastIndexOf('.');
  if (lastDot <= 0 || lastDot === fileName.length - 1) {
    return '';
  }
  return fileName.slice(lastDot).toLowerCase();
};

/**
 * 按 input accept 规则判断文件是否允许上传。
 * accept 为空表示不限制；支持扩展名、精确 mime、以及 mime 通配（含全部类型）。
 */
export const isFileAcceptedByAccept = (file: File, accept?: string): boolean => {
  if (!accept?.trim()) {
    return true;
  }
  const tokens = normalizeAcceptTokens(accept);
  if (tokens.includes('*/*')) {
    return true;
  }
  const extension = getFileNameExtension(file.name);
  const mime = (file.type || '').toLowerCase();
  return tokens.some(token => {
    if (token.startsWith('.')) {
      return extension === token;
    }
    if (token.endsWith('/*')) {
      return mime.startsWith(token.slice(0, -1));
    }
    return mime === token;
  });
};
