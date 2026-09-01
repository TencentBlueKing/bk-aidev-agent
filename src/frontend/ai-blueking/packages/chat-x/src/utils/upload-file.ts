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
 * 上传附件的取值与分组纯函数。
 *
 * 待发送（含 `File`）与已发送（仅 `BinaryInputContent`）两种形态字段不齐，
 * 此处收敛取值优先级，避免各组件各写一份 `a || b || c`。
 * 结构化入参而非直接依赖 `UploadFile`，让 utils 层不反向依赖 components / types。
 */
import { formatBytes, isImageFile } from './file';

/** 附件的结构化最小契约，`Partial<UploadFile>` 可直接传入 */
export type UploadFileLike = {
  file?: File;
  filename?: string;
  mimeType?: string;
  size?: number;
  url?: string;
};

/** `File` 的身份标识：同名文件靠体积与修改时间区分，用于去重与列表 key */
export const getFileIdentity = (file: File): string => `${file.name}_${file.size}_${file.lastModified}`;

/**
 * 附件的稳定 key：待发送态用 `File` 身份（上传成功回填 url 后不变），
 * 已发送态退回 url / 文件名。
 */
export const getUploadFileKey = (item: UploadFileLike): string =>
  item.file ? getFileIdentity(item.file) : item.url || item.filename || '';

/**
 * 是否按图片渲染缩略图。
 * 仅依据 MIME，不再因「有 url」就当图片——解除类型限制后，
 * 任意文件上传成功都会拿到 url，靠 url 判断必然把 doc / pdf 渲染成破图。
 */
export const isUploadImageFile = (item: UploadFileLike): boolean => isImageFile(item.mimeType || item.file?.type);

/** 文件名：已发送态的 filename 优先，回退原始 `File` */
export const getUploadFileName = (item: UploadFileLike): string => item.filename || item.file?.name || '';

/** 字节数：待发送态取 `File.size`，已发送态取消息内下发的 size */
export const getUploadFileSize = (item: UploadFileLike): number | undefined => item.file?.size ?? item.size;

/** 附件大小文案，无法得知大小时返回空串（消息态老数据无 size） */
export const formatUploadFileSize = (item: UploadFileLike): string => formatBytes(getUploadFileSize(item));

/**
 * 单次遍历分出图片组与其他文件组。
 * 设计稿要求图片始终排在文件前方，分组本身即承担了排序职责。
 */
export const splitUploadFiles = <T extends UploadFileLike>(items: T[]): { imageFiles: T[]; otherFiles: T[] } => {
  const imageFiles: T[] = [];
  const otherFiles: T[] = [];
  for (const item of items) {
    (isUploadImageFile(item) ? imageFiles : otherFiles).push(item);
  }
  return { imageFiles, otherFiles };
};
