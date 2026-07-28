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

import { computed, ref } from 'vue';

import type { IMediatorModule } from '../mediator';
import type {
  GetPvFileDownloadUrlOptions,
  ISession,
  ISessionFeedback,
  ISessionListParams,
  ISessionListResult,
} from './type';

/** 会话列表默认每页条数 */
const DEFAULT_PAGE_SIZE = 20;

/**
 * 使用会话模块，主要做业务的组合
 * @param mediator - 中介者模块，用于获取其他模块的引用
 * @returns 会话模块
 */
export const useSession = (mediator: IMediatorModule) => {
  const list = ref<ISession[]>([]);
  const current = ref<ISession | null>(null);
  const page = ref(0);
  const numPages = ref(0);
  const count = ref(0);
  const isCurrentLoading = ref(false);
  const isListLoading = ref(false);
  const isLoadingMore = ref(false);
  const isCreateLoading = ref(false);
  const isUpdateLoading = ref(false);
  const isDeleteLoading = ref(false);
  const isBatchDeleteLoading = ref(false);
  const isRenameLoading = ref(false);

  const hasMore = computed(() => page.value > 0 && page.value < numPages.value);

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

  /**
   * 拉取会话列表（默认第 1 页并替换本地 list）
   */
  const getSessions = (params?: ISessionListParams) => {
    isListLoading.value = true;
    const requestParams: ISessionListParams = {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? DEFAULT_PAGE_SIZE,
    };
    return mediator.http?.session
      .getSessions(requestParams)
      .then((res: ISessionListResult) => {
        list.value = res.results;
        page.value = res.page;
        numPages.value = res.numPages;
        count.value = res.count;
      })
      .finally(() => {
        isListLoading.value = false;
      });
  };

  /**
   * 加载下一页会话并追加到 list（按 sessionCode 去重）
   */
  const loadMoreSessions = async (pageSize = DEFAULT_PAGE_SIZE) => {
    if (!hasMore.value || isListLoading.value || isLoadingMore.value) return;
    isLoadingMore.value = true;
    try {
      const res = await mediator.http?.session.getSessions({
        page: page.value + 1,
        page_size: pageSize,
      });
      if (!res) return;
      const existing = new Set(list.value.map(s => s.sessionCode));
      const appended = res.results.filter(s => !existing.has(s.sessionCode));
      list.value = [...list.value, ...appended];
      page.value = res.page;
      numPages.value = res.numPages;
      count.value = res.count;
    } finally {
      isLoadingMore.value = false;
    }
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
    const shouldLoadMessages = options?.loadMessages !== false;
    const localSession = list.value.find(item => item.sessionCode === sessionCode);
    // 新会话或明确空会话已在本地列表中，无需额外 GET 会话详情。
    if (!shouldLoadMessages && localSession) {
      current.value = localSession;
    } else {
      // 从接口更新当前会话信息
      await getSession(sessionCode);
    }

    // 默认加载消息，但允许跳过（新会话消息必定为空，无需加载）
    if (shouldLoadMessages) {
      // 获取会话内容
      await mediator.message?.getMessages(sessionCode);
      // 继续聊天
      mediator.agent?.resumeStreamingChat(sessionCode);
      // 轮询接口，判断是否可以继续聊天
      mediator.agent?.pollResumeSession(sessionCode);
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
        count.value += 1;
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
      count.value = Math.max(0, count.value - 1);
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
      const beforeLength = list.value.length;
      list.value = list.value.filter(item => !deletedSet.has(item.sessionCode));
      const removedCount = beforeLength - list.value.length;
      count.value = Math.max(0, count.value - removedCount);

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

  const getPvFileDownloadUrl = (sessionCode: string, path: string, options?: GetPvFileDownloadUrlOptions) => {
    return mediator.http?.session.getPvFileDownloadUrl(sessionCode, path, options);
  };

  /**
   * 重置 session 模块状态
   */
  const reset = () => {
    list.value = [];
    current.value = null;
    page.value = 0;
    numPages.value = 0;
    count.value = 0;
    isCurrentLoading.value = false;
    isListLoading.value = false;
    isLoadingMore.value = false;
    isCreateLoading.value = false;
    isUpdateLoading.value = false;
    isDeleteLoading.value = false;
    isBatchDeleteLoading.value = false;
    isRenameLoading.value = false;
  };

  return {
    list,
    current,
    page,
    numPages,
    count,
    hasMore,
    isCurrentLoading,
    isListLoading,
    isLoadingMore,
    isCreateLoading,
    isUpdateLoading,
    isDeleteLoading,
    isBatchDeleteLoading,
    getSessions,
    loadMoreSessions,
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
    getPvFileDownloadUrl,
    reset,
  };
};

export type ISessionModule = ReturnType<typeof useSession>;
