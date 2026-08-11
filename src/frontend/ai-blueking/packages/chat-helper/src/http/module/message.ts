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
import { transferMessage2MessageApi, transferMessageApi2Message } from '../transform/message';

import type {
  IFlowAgentTaskNodeInfo,
  IMessage,
  IMessageApi,
  IUserOperationPayload,
  UserOperation,
} from '../../message/type';
import type { FetchClient, IRequestConfig } from '../fetch';

/**
 * 分享消息接口返回数据
 */
export interface IShareMessagesResponse {
  agent_code: string;
  agent_version: string;
  content_count: number;
  created_at: string;
  created_by: string;
  session_code: string;
  share_page: string;
  share_token: string;
}

/**
 * message 相关 http 接口
 * @param fetchClient - 请求客户端
 * @returns message 相关 http 接口
 */
export const useMessage = (fetchClient: FetchClient) => {
  // 获取会话内容列表（fuzzy 置于末尾，避免影响既有 limit/config 调用）
  const getMessages = (sessionCode: string, limit?: number, config?: IRequestConfig, fuzzy?: string) =>
    fetchClient
      .get<IMessageApi[]>(`session_content/content/`, { session_code: sessionCode, limit, fuzzy }, config)
      .then(res => res.map(transferMessageApi2Message));

  // 新增会话内容
  const plusMessage = (data: IMessage, config?: IRequestConfig) =>
    fetchClient
      .post<IMessageApi>(`session_content/`, transferMessage2MessageApi(data), config)
      .then(transferMessageApi2Message);

  // 修改会话内容
  const modifyMessage = (data: IMessage, config?: IRequestConfig) =>
    fetchClient
      .put<IMessageApi>(`session_content/${data.id}/`, transferMessage2MessageApi(data), config)
      .then(transferMessageApi2Message);

  // 删除会话内容
  const deleteMessage = (id: string, config?: IRequestConfig) =>
    fetchClient.delete<IMessage>(`session_content/${id}/`, undefined, config);

  // 批量删除聊天内容
  const batchDeleteMessages = (ids: string[], config?: IRequestConfig) =>
    fetchClient.post<number>(`session_content/batch_delete/`, { ids }, config);

  // 分享消息
  const shareMessages = (sessionCode: string, contentIds: string[], expiredAt?: number, config?: IRequestConfig) =>
    fetchClient.post<IShareMessagesResponse>(
      `share/`,
      {
        session_code: sessionCode,
        content_ids: contentIds,
        ...(expiredAt ? { expired_at: expiredAt } : {}),
      },
      config,
    );

  // 停止会话
  const stopChat = (sessionCode: string, config?: IRequestConfig) =>
    fetchClient.post<void>(`session_content/stop/`, { session_code: sessionCode }, config);

  // 获取流程引擎任务信息
  const getFlowAgentTaskInfo = (taskId: number, config?: IRequestConfig) =>
    fetchClient.get<unknown>(`flow_agent/${taskId}/task_info/`, undefined, config);

  // 获取流程引擎任务节点详情
  const getFlowAgentTaskNodeInfo = (taskId: number, nodeId: string, config?: IRequestConfig) =>
    fetchClient.get<IFlowAgentTaskNodeInfo>(`flow_agent/${taskId}/task_node_info/${nodeId}/`, undefined, config);

  // 重试流程引擎任务节点
  const retryFlowAgentTaskNode = (sessionCode: string, nodeId: string, taskId: number, config?: IRequestConfig) =>
    fetchClient.post<void>(`flow_agent/${sessionCode}/node/${nodeId}/retry/`, { task_id: taskId }, config);

  // 跳过流程引擎任务节点
  const skipFlowAgentTaskNode = (sessionCode: string, nodeId: string, taskId: number, config?: IRequestConfig) =>
    fetchClient.post<void>(`flow_agent/${sessionCode}/node/${nodeId}/skip/`, { task_id: taskId }, config);

  // 用户操作
  const userOperation = (
    sessionCode: string,
    operation: UserOperation,
    payload: IUserOperationPayload,
    config?: IRequestConfig,
  ) => fetchClient.post<void>(`user_operation/`, { session_code: sessionCode, operation, payload }, config);

  return {
    getMessages,
    plusMessage,
    modifyMessage,
    deleteMessage,
    batchDeleteMessages,
    shareMessages,
    stopChat,
    getFlowAgentTaskInfo,
    getFlowAgentTaskNodeInfo,
    retryFlowAgentTaskNode,
    skipFlowAgentTaskNode,
    userOperation,
  };
};
