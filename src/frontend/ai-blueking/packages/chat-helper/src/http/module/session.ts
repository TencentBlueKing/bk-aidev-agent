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
import {
  transferSession2SessionApi,
  transferSessionApi2Session,
  transferSessionFeedback2SessionFeedbackApi,
  transferSessionFeedbackApi2SessionFeedback,
} from '../transform/session';
import { resolveRequestValue } from '../fetch';

import type {
  GetPvFileDownloadUrlOptions,
  ILegacyUploadFileResult,
  IPvFileDownloadUrlResult,
  IPvFileUploadResult,
  ISession,
  ISessionApi,
  ISessionFeedback,
  ISessionFeedbackApi,
  ISessionListApi,
  ISessionListParams,
} from '../../session/type';
import type { FetchClient, IRequestConfig } from '../fetch';

/** 上传接口传输用文件名前缀，与原始展示名解耦 */
const UPLOAD_FILE_NAME_PREFIX = 'upload_file';

/** 会话列表默认每页条数 */
const DEFAULT_PAGE_SIZE = 20;

const DEFAULT_PV_FILE_DOWNLOAD_EXPIRES_IN = 600;
const DEFAULT_PV_FILE_DOWNLOAD_TIMEOUT = 20000;

/**
 * 将会话列表接口响应统一为分页结构。
 * 兼容两类后台：
 * 1. 分页：`{ page, num_pages, count, results }`
 * 2. 未分页（旧接口）：直接返回 `ISessionApi[]`
 */
const normalizeSessionListResponse = (res: ISessionListApi | ISessionApi[]) => {
  if (Array.isArray(res)) {
    return {
      page: 1,
      numPages: 1,
      count: res.length,
      results: res.map(transferSessionApi2Session),
    };
  }

  const results = Array.isArray(res?.results) ? res.results : [];
  return {
    page: res?.page ?? 1,
    numPages: res?.num_pages ?? 1,
    count: res?.count ?? results.length,
    results: results.map(transferSessionApi2Session),
  };
};

/** 从原始文件名提取 ASCII 安全扩展名，用于保留文件类型 */
const getSafeFileExtension = (fileName: string): string => {
  const extension = fileName.split('.').pop();
  if (!extension || extension === fileName) {
    return '';
  }

  const safeExtension = extension
    .replace(/[^A-Za-z0-9]/g, '')
    .slice(0, 20)
    .toLowerCase();
  return safeExtension ? `.${safeExtension}` : '';
};

/**
 * 生成上传接口使用的 ASCII 安全文件名。
 * 中文等非 ASCII 原名不能用于 URL path / Content-Disposition（浏览器与后端均可能编码失败），
 * 原始 file.name 仍保留在 File 对象上，由 chat-x 发送消息时作为展示名使用。
 */
const buildSafeUploadFileName = (file: File): string => {
  const suffix = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  return `${UPLOAD_FILE_NAME_PREFIX}_${suffix}${getSafeFileExtension(file.name)}`;
};

/** Content-Disposition 仅允许 ASCII，须与 upload path 中的 file_name 一致 */
const buildUploadContentDisposition = (fileName: string): string => {
  return `attachment; filename="${fileName}"`;
};

/**
 * session 相关 http 接口
 * @param fetchClient - 请求客户端
 * @returns session 相关 http 接口
 */
export const useSession = (fetchClient: FetchClient) => {
  // 清除聊天上下文
  const clearSession = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient.post(`chat_completion/${sessionCode}/clear/`, undefined, config);

  // 获取会话列表（分页；兼容未支持分页的后台返回数组）
  const getSessions = (params?: ISessionListParams, config?: IRequestConfig) =>
    fetchClient
      .get<ISessionListApi | ISessionApi[]>(
        `session/`,
        {
          page: params?.page ?? 1,
          page_size: params?.page_size ?? DEFAULT_PAGE_SIZE,
        },
        config,
      )
      .then(normalizeSessionListResponse);

  // 新增会话
  const plusSession = (data: ISession, config?: IRequestConfig) =>
    fetchClient
      .post<ISessionApi>(`session/`, transferSession2SessionApi(data), config)
      .then(res => transferSessionApi2Session(res));

  // 修改会话
  const modifySession = (data: ISession, config?: IRequestConfig) =>
    fetchClient
      .put<ISessionApi>(`session/${data.sessionCode}/`, transferSession2SessionApi(data), config)
      .then(res => transferSessionApi2Session(res));

  // 删除会话
  const deleteSession = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient.delete(`session/${sessionCode}/`, undefined, config);

  // 批量删除会话
  const batchDeleteSessions = (sessionCodes: string[], config?: IRequestConfig) =>
    fetchClient.post<number>(`session/batch_delete/`, { session_codes: sessionCodes }, config);

  // 获取会话资源
  const getSession = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient
      .get<ISessionApi>(`session/${sessionCode}/`, undefined, config)
      .then(res => transferSessionApi2Session(res));

  // 提交会话反馈
  const postSessionFeedback = (data: ISessionFeedback, config?: IRequestConfig) =>
    fetchClient
      .post<ISessionFeedbackApi>(`session_feedback/`, transferSessionFeedback2SessionFeedbackApi(data), config)
      .then(res => transferSessionFeedbackApi2SessionFeedback(res));

  // 获取反馈标签列表
  const getSessionFeedbackReasons = (rate: number, config?: IRequestConfig) =>
    fetchClient.get<string[]>(`session_feedback/reasons/`, { rate }, config);

  // 会话重命名
  const renameSession = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient
      .post<ISessionApi>(`session/${sessionCode}/ai_rename/`, undefined, config)
      .then(res => transferSessionApi2Session(res));

  // 旧版上传：session/{code}/upload/{asciiFileName}/（agent_sdk_version < 2.2.2rc25）
  const uploadFile = (sessionCode: string, file: File, config?: IRequestConfig) => {
    const safeFileName = buildSafeUploadFileName(file);
    const fileName = encodeURIComponent(safeFileName);
    const headers = resolveRequestValue(config?.headers) ?? {};

    return file.arrayBuffer().then(content =>
      fetchClient.post<ILegacyUploadFileResult>(`session/${sessionCode}/upload/${fileName}/`, content, {
        ...config,
        headers: {
          ...headers,
          'Content-Disposition': buildUploadContentDisposition(safeFileName),
        },
      }),
    );
  };

  /** 新版批量上传：session/{code}/pv_files/upload/（agent_sdk_version ≥ 2.2.2rc25） */
  const uploadPvFiles = (sessionCode: string, files: File[], config?: IRequestConfig) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    return fetchClient.post<IPvFileUploadResult>(`session/${sessionCode}/pv_files/upload/`, formData, config);
  };

  /**
   * 签发会话 PV 文件的临时 download_url / preview_url。
   * path 为文件相对路径（artifacts 的 outputId）；URLSearchParams 会自动编码，勿二次 encode。
   */
  const getPvFileDownloadUrl = (
    sessionCode: string,
    path: string,
    options?: GetPvFileDownloadUrlOptions,
    config?: IRequestConfig,
  ) => {
    const expiresIn = options?.expiresIn ?? DEFAULT_PV_FILE_DOWNLOAD_EXPIRES_IN;
    const timeout = options?.timeout ?? DEFAULT_PV_FILE_DOWNLOAD_TIMEOUT;

    return fetchClient.get<IPvFileDownloadUrlResult>(
      `session/${sessionCode}/pv_files/download_url/`,
      {
        expires_in: expiresIn,
        path,
      },
      {
        ...config,
        timeout: config?.timeout ?? timeout,
      },
    );
  };

  // 轮询接口，判断是否可以继续聊天
  const isResumeSession = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient.get<boolean>(`session/${sessionCode}/is_resume/`, undefined, config);

  return {
    clearSession,
    getSessions,
    plusSession,
    modifySession,
    deleteSession,
    batchDeleteSessions,
    getSession,
    postSessionFeedback,
    getSessionFeedbackReasons,
    renameSession,
    uploadFile,
    uploadPvFiles,
    getPvFileDownloadUrl,
    isResumeSession,
  };
};
