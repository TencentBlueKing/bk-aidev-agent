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

import type { ISession, ISessionApi, ISessionFeedback, ISessionFeedbackApi } from '../../session/type';
import type { FetchClient, IRequestConfig } from '../fetch';

/**
 * session 相关 http 接口
 * @param fetchClient - 请求客户端
 * @returns session 相关 http 接口
 */
export const useSession = (fetchClient: FetchClient) => {
  // 清除聊天上下文
  const clearSession = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient.post(`chat_completion/${sessionCode}/clear/`, undefined, config);

  // 获取会话列表
  const getSessions = (config?: IRequestConfig) =>
    fetchClient.get<ISessionApi[]>(`session/`, undefined, config).then(res => res.map(transferSessionApi2Session));

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

  // 上传文件到会话
  const uploadFile = (sessionCode: string, file: File, config?: IRequestConfig) => {
    const fileName = encodeURIComponent(file.name);
    return file.arrayBuffer().then(content =>
      fetchClient.post<{ download_url?: string }>(`session/${sessionCode}/upload/${fileName}/`, content, {
        ...config,
        headers: { 'Content-Disposition': `attachment; filename="${file.name}"` },
      }),
    );
  };

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
  };
};
