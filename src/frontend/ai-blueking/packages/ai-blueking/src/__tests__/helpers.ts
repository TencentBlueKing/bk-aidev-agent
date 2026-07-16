/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { ref, shallowRef } from 'vue';

import { vi } from 'vitest';

import type { ChatBusinessManager } from '../manager/business/chat-business-manager';
import type { SessionBusinessManager } from '../manager/business/session-business-manager';
import type { IChatHelper } from '../types';

/**
 * 创建模拟的 AI 消息
 */
export function createMockAIMessage(overrides: Record<string, any> = {}) {
  return {
    id: 2,
    role: 'assistant',
    content: 'Hi there!',
    ...overrides,
  };
}

/**
 * 创建 Mock ChatBusinessManager
 */
export function createMockChatBusinessManager(): ChatBusinessManager {
  return {
    isGenerating: ref(false),
    isStopLoading: ref(false),
    isMessagesLoading: ref(false),
    messages: shallowRef([]),
    openingRemark: '',
    predefinedQuestions: [],
    sendMessage: vi.fn().mockResolvedValue(undefined),
    stopGeneration: vi.fn().mockResolvedValue(undefined),
    regenerateMessage: vi.fn().mockResolvedValue(undefined),
    regenerateFromAIMessages: vi.fn().mockResolvedValue(undefined),
    resendMessageWithProperty: vi.fn().mockResolvedValue(undefined),
    retryMessage: vi.fn().mockResolvedValue(undefined),
    deleteMessage: vi.fn().mockResolvedValue(undefined),
    batchDeleteMessages: vi.fn().mockResolvedValue(undefined),
    handleStreamStart: vi.fn(),
    handleStreamEnd: vi.fn(),
    handleStreamError: vi.fn(),
  } as unknown as ChatBusinessManager;
}

/**
 * 创建 Mock IChatHelper 实例
 */
export function createMockChatHelper(): IChatHelper {
  return {
    agent: {
      chat: vi.fn().mockResolvedValue(undefined),
      getAgentInfo: vi.fn().mockResolvedValue({}),
      handleRole: vi.fn(),
      info: ref(null) as any,
      isChatting: ref(false),
      resendMessage: vi.fn().mockResolvedValue(undefined),
      stopChat: vi.fn().mockResolvedValue(undefined),
      abortChat: vi.fn(),
      streamRequest: vi.fn().mockResolvedValue(undefined),
      userOperationStreamRequest: vi.fn().mockResolvedValue(undefined),
      pollResumeSession: vi.fn(),
    } as any,
    http: {},
    message: {
      deleteMessages: vi.fn().mockResolvedValue(undefined),
      isListLoading: ref(false),
      list: shallowRef([]),
      shareMessages: vi.fn().mockResolvedValue({ share_page: 'https://example.com/', share_token: 'abc123' }),
    } as any,
    session: {
      chooseSession: vi.fn().mockResolvedValue(undefined),
      createSession: vi.fn().mockResolvedValue(undefined),
      current: ref(null) as any,
      deleteSession: vi.fn().mockResolvedValue(undefined),
      getSession: vi.fn().mockResolvedValue(undefined),
      getSessionFeedbackReasons: vi.fn().mockResolvedValue([]),
      getSessions: vi.fn().mockResolvedValue(undefined),
      loadMoreSessions: vi.fn().mockResolvedValue(undefined),
      hasMore: ref(false),
      isCreateLoading: ref(false),
      isCurrentLoading: ref(false),
      isDeleteLoading: ref(false),
      isListLoading: ref(false),
      isLoadingMore: ref(false),
      isUpdateLoading: ref(false),
      list: ref([]),
      page: ref(0),
      numPages: ref(0),
      count: ref(0),
      postSessionFeedback: vi.fn().mockResolvedValue(undefined),
      renameSession: vi.fn().mockResolvedValue(undefined),
      updateSession: vi.fn().mockResolvedValue(undefined),
      uploadFile: vi.fn().mockResolvedValue({ download_url: 'https://example.com/file.png' }),
    } as any,
  };
}

/**
 * 创建 Mock emit 函数
 */
export function createMockEmit() {
  return vi.fn() as any;
}

/**
 * 创建 Mock SessionBusinessManager
 */
export function createMockSessionBusinessManager(): SessionBusinessManager {
  return {
    currentSession: ref(null),
    sessionList: ref([]),
    sessionCount: ref(0),
    hasMoreSessions: ref(false),
    isCreateLoading: ref(false),
    isCurrentLoading: ref(false),
    isDeleteLoading: ref(false),
    isListLoading: ref(false),
    isLoadingMore: ref(false),
    isUpdateLoading: ref(false),
    loadRecentSession: vi.fn().mockResolvedValue(undefined),
    createNewSession: vi.fn().mockResolvedValue(undefined),
    createSession: vi.fn().mockResolvedValue(undefined),
    deleteSession: vi.fn().mockResolvedValue(undefined),
    getSession: vi.fn().mockResolvedValue(undefined),
    loadSessions: vi.fn().mockResolvedValue(undefined),
    loadMoreSessions: vi.fn().mockResolvedValue(undefined),
    switchSession: vi.fn().mockResolvedValue(undefined),
    updateSessionName: vi.fn().mockResolvedValue(undefined),
  } as unknown as SessionBusinessManager;
}

/**
 * 创建模拟的快捷指令
 */
export function createMockShortcut(overrides: Record<string, any> = {}) {
  return {
    id: 'shortcut-1',
    name: 'Test Shortcut',
    alias: 'Test',
    components: [
      {
        key: 'input',
        name: 'Input',
        type: 'textarea',
        fillBack: false,
      },
    ],
    formModel: {},
    ...overrides,
  };
}

/**
 * 创建模拟的用户消息
 */
export function createMockUserMessage(overrides: Record<string, any> = {}) {
  return {
    id: 1,
    role: 'user',
    content: 'Hello',
    ...overrides,
  };
}
