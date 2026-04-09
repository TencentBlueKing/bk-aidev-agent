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
import { ref } from 'vue';

import { type IMessage, MessageRole, MessageStatus } from './type';

import type { IMediatorModule } from '../mediator';

/**
 * 生成临时消息 ID
 */
const generateTempId = () => `temp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

/**
 * 使用消息模块，主要做业务的组合
 * @param http - HTTP 模块
 * @returns 消息模块
 */
export const useMessage = (mediator: IMediatorModule) => {
  const list = ref<IMessage[]>([]);
  const isListLoading = ref(false);
  const isDeleteLoading = ref(false);

  const getMessages = (sessionCode: string) => {
    isListLoading.value = true;
    return mediator.http?.message
      .getMessages(sessionCode)
      .then(res => {
        list.value = res;
      })
      ['finally'](() => {
        isListLoading.value = false;
      });
  };

  /**
   * 清空消息列表 & 调用接口删除所有数据
   */
  const clearMessages = () => {
    return deleteMessages(list.value);
  };

  const modifyMessage = (message: IMessage) => {
    list.value = list.value.map(item => (item.messageId === message.messageId ? message : item));
  };

  const plusMessage = (message: IMessage) => {
    list.value.push(message);
  };

  const getCurrentLoadingMessage = () => {
    return list.value.findLast(item => [MessageStatus.Pending, MessageStatus.Streaming].includes(item.status));
  };

  const getMessageByMessageId = (id: string) => {
    return list.value.find(item => item.messageId === id);
  };

  /**
   * 创建并添加消息（乐观更新）
   * 1. 立即在前端显示消息（使用临时 ID）
   * 2. 同时调用后端 API
   * 3. API 返回后更新为真实 ID
   * 4. 失败时标记为错误状态
   */
  const createAndPlusMessage = async (message: IMessage) => {
    // 1. 生成临时 ID 并立即添加到列表（乐观更新）
    const tempId = generateTempId();
    const optimisticMessage: IMessage = {
      ...message,
      id: tempId,
      messageId: tempId,
    };
    list.value.push(optimisticMessage);

    try {
      // 2. 调用后端 API
      const res = await mediator.http?.message.plusMessage(message);

      if (res) {
        // 3. 更新为真实的消息数据
        const index = list.value.findIndex(m => m.messageId === tempId);
        if (index !== -1) {
          const mergedMessage: IMessage = {
            ...res,
            ...('property' in message && message.property ? { property: message.property } : {}),
          };
          list.value[index] = mergedMessage;
        }
      }
    } catch (error) {
      // 4. 失败处理：标记消息为失败状态
      const index = list.value.findIndex(m => m.messageId === tempId);
      if (index !== -1) {
        list.value[index] = {
          ...list.value[index],
          status: MessageStatus.Error,
        };
      }
      throw error;
    }
  };

  /**
   * 批量删除消息（乐观更新）
   * 1. 立即从列表中移除消息
   * 2. 调用后端 API
   * 3. 失败时恢复消息
   * 接口只需要传 user message id 列表
   */
  const deleteMessages = async (messages: IMessage[]) => {
    // 获取 user message id 列表
    const ids = messages.reduce((acc, item) => {
      if (item.role === MessageRole.User) {
        acc.push(item.id);
      }
      return acc;
    }, [] as string[]);

    // 如果 user message id 列表为空，则直接返回
    if (ids.length <= 0) {
      return;
    }

    // 1. 保存原始列表（用于失败时恢复）
    const originalList = [...list.value];

    // 2. 乐观更新：立即从列表中移除消息
    list.value = list.value.filter(item => !messages.includes(item));

    // 3. 调用后端 API
    isDeleteLoading.value = true;
    try {
      await mediator.http?.message.batchDeleteMessages(ids);
    } catch (error) {
      // 4. 失败时恢复原始列表
      list.value = originalList;
      throw error;
    } finally {
      isDeleteLoading.value = false;
    }
  };

  /**
   * 分享消息
   * 提取 user message id 列表，调用后端分享接口
   * @param sessionCode 会话编码
   * @param messages 要分享的消息列表
   * @param expiredAt 过期时间（可选）
   * @returns 分享结果（包含 share_url）
   */
  const shareMessages = async (sessionCode: string, messages: IMessage[], expiredAt?: number) => {
    // 获取 user message id 列表
    const contentIds = messages.reduce((acc, item) => {
      if (item.role === MessageRole.User) {
        acc.push(item.id);
      }
      return acc;
    }, [] as string[]);

    // 如果 user message id 列表为空，则直接返回
    if (contentIds.length <= 0) {
      return;
    }

    return mediator.http?.message.shareMessages(sessionCode, contentIds, expiredAt);
  };

  const getFlowAgentTaskInfo = (taskId: number) => mediator.http?.message.getFlowAgentTaskInfo(taskId);

  const getFlowAgentTaskNodeInfo = (taskId: number, nodeId: string) =>
    mediator.http?.message.getFlowAgentTaskNodeInfo(taskId, nodeId);

  const reset = () => {
    list.value = [];
    isListLoading.value = false;
    isDeleteLoading.value = false;
  };

  return {
    list,
    isListLoading,
    isDeleteLoading,
    getMessages,
    clearMessages,
    getCurrentLoadingMessage,
    getMessageByMessageId,
    modifyMessage,
    plusMessage,
    createAndPlusMessage,
    deleteMessages,
    shareMessages,
    getFlowAgentTaskInfo,
    getFlowAgentTaskNodeInfo,
    reset,
  };
};

export type IMessageModule = ReturnType<typeof useMessage>;
