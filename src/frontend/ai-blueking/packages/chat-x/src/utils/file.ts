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
 * 格式化文件大小 及 单位展示
 * @param file 文件
 * @returns 1024B -> 1KB 1024KB -> 1MB 1024MB -> 1GB
 */
export const formatFileSize = (file?: File): string => {
  if (!file) return '';
  const size = file.size;
  const units = ['B', 'KB', 'M', 'GB'];
  const index = Math.floor(Math.log2(size) / 10);
  return `${(size / Math.pow(1024, index)).toFixed(2)} ${units[index]}`;
};
