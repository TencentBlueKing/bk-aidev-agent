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

import type { IMediatorModule } from '../mediator';
import type { ISession, ISessionFeedback } from './type';

/**
 * 使用会话模块，主要做业务的组合
 * @param mediator - 中介者模块，用于获取其他模块的引用
 * @returns 会话模块
 */
export const useSession = (mediator: IMediatorModule) => {
  const list = ref<ISession[]>([]);
  const current = ref<ISession | null>(null);
  const isCurrentLoading = ref(false);
  const isListLoading = ref(false);
  const isCreateLoading = ref(false);
  const isUpdateLoading = ref(false);
  const isDeleteLoading = ref(false);
  const isBatchDeleteLoading = ref(false);
  const isRenameLoading = ref(false);

  /**
   * 更新 list 中的 session，并同步更新 current
   * @param session - Partial session
   */
  const updateSessionInList = (session: Partial<ISession> & { sessionCode: string }) => {
    // 先更新 list 中对应的 session
    list.value = list.value.map(item => (item.sessionCode === session.sessionCode ? { ...item, ...session } : item));
    // 如果 current 是被更新的 session，则让 current 重新指向 list 中更新后的对象
    if (current.value?.sessionCode === session.sessionCode) {
      current.value = list.value.find(item => item.sessionCode === session.sessionCode) ?? current.value;
    }
  };

  const getSessions = () => {
    isListLoading.value = true;
    return mediator.http?.session
      .getSessions()
      .then((res: ISession[]) => {
        list.value = res;
      })
      .finally(() => {
        isListLoading.value = false;
      });
  };

  /**
   * 切换会话
   * @param sessionCode - 会话编码
   * @param options - 选项
   * @param options.loadMessages - 是否加载消息列表，默认 true。新创建的会话可设为 false 跳过加载
   */
  const chooseSession = async (sessionCode: string, options?: { loadMessages?: boolean }) => {
    // 中止当前聊天
    mediator.agent?.abortChat();
    // 选择会话
    current.value = list.value.find(item => item.sessionCode === sessionCode) ?? null;

    // 默认加载消息，但允许跳过（新会话消息必定为空，无需加载）
    if (options?.loadMessages !== false) {
      // 获取会话内容
      await mediator.message?.getMessages(sessionCode);
      // 继续聊天
      mediator.agent?.resumeStreamingChat(sessionCode);
    } else {
      // 新会话，清空消息列表
      if (mediator.message) {
        mediator.message.list.value = [];
      }
    }
  };

  const getSession = (sessionCode: string) => {
    isCurrentLoading.value = true;
    return mediator.http?.session
      .getSession(sessionCode)
      .then((res: ISession) => {
        current.value = res;
      })
      .finally(() => {
        isCurrentLoading.value = false;
      });
  };

  /**
   * 创建新会话
   * @param session - 会话数据
   * @param options - 选项
   * @param options.loadMessages - 创建后是否加载消息列表，默认 false（新会话消息必定为空）
   */
  const createSession = async (session: ISession, options?: { loadMessages?: boolean }) => {
    isCreateLoading.value = true;
    try {
      const res = await mediator.http?.session.plusSession(session);
      if (res) {
        list.value.unshift(res); // 新会话插入到列表头部
        // 新会话默认不加载消息（消息必定为空），优化 UX
        await chooseSession(res.sessionCode, { loadMessages: options?.loadMessages ?? false });
      }
    } finally {
      isCreateLoading.value = false;
    }
  };

  const updateSession = (session: ISession) => {
    isUpdateLoading.value = true;
    return mediator.http?.session
      .modifySession(session)
      .then((res: ISession) => {
        updateSessionInList(res);
      })
      .finally(() => {
        isUpdateLoading.value = false;
      });
  };

  const deleteSession = async (sessionCode: string) => {
    isDeleteLoading.value = true;
    try {
      await mediator.http?.session.deleteSession(sessionCode);
      list.value = list.value.filter(item => item.sessionCode !== sessionCode);
      // 如果当前会话被删除，选择第一个会话
      if (current.value?.sessionCode === sessionCode && list.value[0]?.sessionCode) {
        await chooseSession(list.value[0].sessionCode);
      }
    } finally {
      isDeleteLoading.value = false;
    }
  };

  /**
   * 批量删除会话
   * @param sessionCodes - 要删除的会话编码列表
   */
  const batchDeleteSessions = async (sessionCodes: string[]) => {
    if (sessionCodes.length === 0) return;

    isBatchDeleteLoading.value = true;
    try {
      await mediator.http?.session.batchDeleteSessions(sessionCodes);

      const deletedSet = new Set(sessionCodes);
      list.value = list.value.filter(item => !deletedSet.has(item.sessionCode));

      if (current.value && deletedSet.has(current.value.sessionCode)) {
        if (list.value.length > 0) {
          await chooseSession(list.value[0].sessionCode);
        } else {
          current.value = null;
          if (mediator.message) {
            mediator.message.list.value = [];
          }
        }
      }
    } finally {
      isBatchDeleteLoading.value = false;
    }
  };

  /**
   * 提交会话反馈，sessionContentIds 只需要传 user 对应的 sessionContentId
   * @param data - ISessionFeedback
   */
  const postSessionFeedback = (data: ISessionFeedback) => {
    return mediator.http?.session.postSessionFeedback(data);
  };

  // 获取会话反馈原因
  const getSessionFeedbackReasons = (rate: number) => {
    return mediator.http?.session.getSessionFeedbackReasons(rate);
  };

  // 会话重命名
  const renameSession = (sessionCode: string) => {
    isRenameLoading.value = true;
    return mediator.http?.session
      .renameSession(sessionCode)
      .then((res: ISession) => {
        updateSessionInList({
          sessionCode: res.sessionCode,
          sessionName: res.sessionName,
        });
      })
      .finally(() => {
        isRenameLoading.value = false;
      });
  };

  // 上传文件到会话
  const uploadFile = (sessionCode: string, file: File) => {
    return mediator.http?.session.uploadFile(sessionCode, file);
  };

  /**
   * 重置 session 模块状态
   */
  const reset = () => {
    list.value = [];
    current.value = null;
    isCurrentLoading.value = false;
    isListLoading.value = false;
    isCreateLoading.value = false;
    isUpdateLoading.value = false;
    isDeleteLoading.value = false;
    isBatchDeleteLoading.value = false;
    isRenameLoading.value = false;
  };

  return {
    list,
    current,
    isCurrentLoading,
    isListLoading,
    isCreateLoading,
    isUpdateLoading,
    isDeleteLoading,
    isBatchDeleteLoading,
    getSessions,
    chooseSession,
    getSession,
    createSession,
    updateSession,
    deleteSession,
    batchDeleteSessions,
    postSessionFeedback,
    getSessionFeedbackReasons,
    renameSession,
    uploadFile,
    reset,
  };
};

export type ISessionModule = ReturnType<typeof useSession>;
