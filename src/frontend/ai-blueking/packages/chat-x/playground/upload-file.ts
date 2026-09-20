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
export interface UploadFileOptions {
  /** access_token */
  accessToken: string;
  /** 文件对象 */
  file: File;
  /** 自定义文件名（可选，默认使用 file.name） */
  fileName?: string;
  /** API host 地址 */
  host?: string;
  /** 会话 code */
  sessionCode: string;
}

export interface UploadFileResponse {
  /** 上传成功后的文件 URL 或其他返回数据 */
  [key: string]: unknown;
}

/** mock 上传延时区间（毫秒）：模拟网络往返，便于观察附件从 pending 到 success */
const MOCK_UPLOAD_DELAY_RANGE = [300, 800] as const;

/** 本地上传文件按永久 path 保存；预览、下载和删除共用同一份数据。 */
const mockUploadedFiles = new Map<string, { file: File; url: string }>();

/** 注册预置样例或用户选中的文件，响应结构与上传 API 一致。 */
export const createMockUploadedFile = (file: File) => {
  const path = `files/${crypto.randomUUID()}-${file.name}`;
  const url = URL.createObjectURL(file);
  mockUploadedFiles.set(path, { file, url });
  return {
    type: 'file' as const,
    id: path,
    path,
    name: file.name,
    mime_type: file.type,
    size: file.size,
    status: 'success' as const,
    download_url: url,
  };
};

/** 文本、代码使用 download_url；图片和 PDF 可直接预览，其他二进制格式需后端转码。 */
export const getMockUploadedFileUrls = (outputId: string) => {
  const item = mockUploadedFiles.get(outputId);
  if (!item) return undefined;
  return {
    download_url: item.url,
    preview_url: item.file.type.startsWith('image/') || item.file.name.toLowerCase().endsWith('.pdf')
      ? item.url
      : undefined,
  };
};

/** 本地 mock 上传保留延时，便于观察 pending → success → 可引用和预览。 */
export async function mockUploadFileToSession(file: File) {
  const [minDelay, maxDelay] = MOCK_UPLOAD_DELAY_RANGE;
  await new Promise(resolve => setTimeout(resolve, minDelay + Math.random() * (maxDelay - minDelay)));
  return createMockUploadedFile(file);
}

export const mockDeleteUploadedFile = async (outputId: string) => {
  await new Promise(resolve => setTimeout(resolve, 300));
  const item = mockUploadedFiles.get(outputId);
  if (!item) return;
  mockUploadedFiles.delete(outputId);
  URL.revokeObjectURL(item.url);
};

/**
 * 批量上传文件
 * @param files 文件数组
 * @param options 通用配置（不包含 file）
 * @returns Promise<UploadFileResponse[]>
 */
export async function uploadFilesToSession(
  files: File[],
  options: Omit<UploadFileOptions, 'file'>,
): Promise<UploadFileResponse[]> {
  return Promise.all(files.map(file => uploadFileToSession({ ...options, file })));
}

/**
 * 上传文件到会话（旧接口，agent_sdk_version < 2.2.2rc25）。
 * 正式环境请用 chat-helper session.uploadFile，会按 agentSdkVersion 自动分流到 pv_files/upload。
 * @param options 上传配置
 * @returns Promise<UploadFileResponse>
 */
export async function uploadFileToSession(options: UploadFileOptions): Promise<UploadFileResponse> {
  const {
    sessionCode,
    file,
    host = import.meta.env.VITE_API_HOST || 'https://your-api-gateway.example.com',
    accessToken,
    fileName,
  } = options;

  const finalFileName = fileName || file.name;
  const uploadUrl = `${host}/bkaidev/resource/chat/v1/session/${sessionCode}/upload/${encodeURIComponent(finalFileName)}/`;

  // 读取文件内容为 ArrayBuffer
  const content = await file.arrayBuffer();

  const response = await fetch(uploadUrl, {
    method: 'POST',
    body: content,
    headers: {
      'Content-Disposition': `attachment; filename="${finalFileName}"`,
      'X-Bkapi-Authorization': JSON.stringify({ access_token: accessToken }),
    },
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
