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
import type { ISession, ISessionApi, ISessionFeedback, ISessionFeedbackApi } from '../../session/type';

/**
 * 将 API 返回的 session 数据转换为前端使用的 session 数据
 * @param data API 返回的 session 数据
 * @returns 前端使用的 session 数据
 */
export const transferSessionApi2Session = (data: ISessionApi): ISession => {
  return {
    sessionCode: data.session_code,
    sessionContentCount: data.session_content_count,
    sessionName: data.session_name,
    isTemporary: data.is_temporary,
    model: data.model,
    comment: data.comment,
    rate: data.rate,
    updatedAt: data.updated_at,
    createdAt: data.created_at,
    status: data.status,
    roleInfo: data.role_info
      ? {
          collectionId: data.role_info.collection_id,
          collectionName: data.role_info.collection_name,
          content: data.role_info.content,
          variables: data.role_info.variables,
        }
      : undefined,
    sessionProperty: {
      isAutoClear: data.session_property?.is_auto_clear,
      isAutoCalcPrompt: data.session_property?.is_auto_clac_prompt,
      labels: data.session_property?.labels,
    },
  };
};

/**
 * 将前端使用的 session 数据转换为 API 使用的 session 数据
 * @param data 前端使用的 session 数据
 * @returns API 使用的 session 数据
 */
export const transferSession2SessionApi = (data: ISession): ISessionApi => {
  return {
    session_code: data.sessionCode,
    session_content_count: data.sessionContentCount,
    session_name: data.sessionName,
    is_temporary: data.isTemporary,
    model: data.model,
    comment: data.comment,
    rate: data.rate,
    updated_at: data.updatedAt,
    created_at: data.createdAt,
    status: data.status,
    role_info: data.roleInfo
      ? {
          collection_id: data.roleInfo.collectionId,
          collection_name: data.roleInfo.collectionName,
          content: data.roleInfo.content,
          variables: data.roleInfo.variables,
        }
      : undefined,
    session_property: {
      is_auto_clear: data.sessionProperty?.isAutoClear,
      is_auto_clac_prompt: data.sessionProperty?.isAutoCalcPrompt,
      labels: data.sessionProperty?.labels,
    },
  };
};

/**
 * 将前端使用的 session 反馈数据转换为 API 使用的 session 反馈数据
 * @param data 前端使用的 session 反馈数据
 * @returns API 使用的 session 反馈数据
 */
export const transferSessionFeedback2SessionFeedbackApi = (data: ISessionFeedback) => {
  return {
    session_code: data.sessionCode,
    session_content_ids: data.sessionContentIds,
    rate: data.rate,
    comment: data.comment,
    labels: data.labels,
  };
};

/**
 * 将 API 返回的 session 反馈数据转换为前端使用的 session 反馈数据
 * @param data API 返回的 session 反馈数据
 * @returns 前端使用的 session 反馈数据
 */
export const transferSessionFeedbackApi2SessionFeedback = (data: ISessionFeedbackApi) => {
  return {
    sessionCode: data.session_code,
    sessionContentIds: data.session_content_ids,
    rate: data.rate,
    comment: data.comment,
    labels: data.lables,
  };
};
