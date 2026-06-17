/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { ref, watch } from 'vue';
import type { ComputedRef, Ref } from 'vue';

import { hasRealMessageContent } from '../utils/message-utils';

import type ChatBot from '../components/chat-bot.vue';
import type { SessionBusinessManager } from '../manager/business/session-business-manager';
import type { CreateSessionOptions } from '../manager/business/types';
import type { IChatHelper, ISession, ReportSdkErrorOptions } from '../types';
import type { EventForwarders } from './use-ai-blueking-init';

export interface UseSessionHandlersParams {
  chatBotRef: Ref<InstanceType<typeof ChatBot> | undefined>;
  chatHelper: IChatHelper;
  currentSession: ComputedRef<ISession | null>;
  forwarders: EventForwarders;
  sessionBusinessManager: SessionBusinessManager;
  reportSdkError: (options: ReportSdkErrorOptions) => void;
}

export function useSessionHandlers(params: UseSessionHandlersParams) {
  const { chatHelper, sessionBusinessManager, chatBotRef, forwarders, reportSdkError, currentSession } = params;

  // ==================== 会话状态 ====================
  const sessionName = ref('');
  const hasPermission = ref(true);
  const hasSessionContents = ref(false);
  const autoGenerateLoading = ref(false);

  // ==================== 辅助方法 ====================

  /**
   * 判断当前会话消息列表中是否存在真实会话内容（排除 promptSetting pause 预设消息）
   * 与业务管理器 createNewSession 共用 hasRealMessageContent，保证判断口径一致
   */
  const checkHasRealContents = () => hasRealMessageContent(chatHelper.message.list.value);

  // ==================== Watchers ====================

  watch(
    () => currentSession.value,
    session => {
      if (session) {
        sessionName.value = session.sessionName || '';
        const hasContent = (session.sessionContentCount ?? 0) > 0 || checkHasRealContents();
        hasSessionContents.value = hasContent;
      }
    },
    { immediate: true },
  );

  watch(
    () => chatHelper.message.list.value.length,
    () => {
      hasSessionContents.value = checkHasRealContents();
    },
  );

  // ==================== Header 事件处理 ====================

  const handleNewChat = async () => {
    chatBotRef.value?.exitShareMode();
    forwarders.newChat();
  };

  const handleNewChatCreated = (session: { sessionCode: string; sessionName?: string; createdAt?: string }) => {
    forwarders.newChatCreated(session);
  };

  const handleHistoryClick = (event: Event) => {
    forwarders.historyClick(event);
  };

  const handleHistorySessionSwitch = async (sessionCode: string) => {
    try {
      chatBotRef.value?.exitShareMode();
      await sessionBusinessManager.switchSession(sessionCode);
    } catch (error) {
      console.error('[AIBlueking] Failed to switch history session:', error);
      reportSdkError({ apiName: 'session', action: 'historySwitch', error, source: 'business' });
    }
  };

  const handleHistorySessionDelete = async (sessionCode: string) => {
    try {
      await sessionBusinessManager.deleteSession(sessionCode);
    } catch (error) {
      console.error('[AIBlueking] Failed to delete history session:', error);
      reportSdkError({ apiName: 'session', action: 'historyDelete', error, source: 'business' });
    }
  };

  const handleHistorySessionRename = async (sessionCode: string, newName: string) => {
    try {
      await sessionBusinessManager.updateSessionName(sessionCode, newName);
    } catch (error) {
      console.error('[AIBlueking] Failed to rename history session:', error);
      reportSdkError({ apiName: 'session', action: 'historyRename', error, source: 'business' });
    }
  };

  const handleAutoGenerateName = async () => {
    const sessionCode = chatHelper.session.current?.value?.sessionCode;
    if (!sessionCode) {
      console.error('[AIBlueking] Cannot auto-generate name: no active session');
      return;
    }

    autoGenerateLoading.value = true;
    try {
      await chatHelper.session.renameSession(sessionCode);

      const updatedSession = chatHelper.session.list.value.find(
        (s: { sessionCode: string }) => s.sessionCode === sessionCode,
      );
      if (updatedSession) {
        sessionName.value = updatedSession.sessionName || '';
      }
    } catch (error) {
      console.error('[AIBlueking] Failed to auto-generate session name:', error);
      reportSdkError({ apiName: 'session', action: 'autoGenerateName', error, source: 'business' });
    } finally {
      autoGenerateLoading.value = false;
    }

    forwarders.autoGenerateName();
  };

  const handleHelpClick = () => {
    forwarders.helpClick();
  };

  const handleRename = async (newName: string) => {
    const current = chatHelper.session.current?.value;
    if (!current) {
      console.error('[AIBlueking] Cannot rename: no active session');
      return;
    }

    try {
      await chatHelper.session.updateSession({
        ...current,
        sessionName: newName,
      });

      sessionName.value = newName;
    } catch (error) {
      console.error('[AIBlueking] Failed to rename session:', error);
      reportSdkError({ apiName: 'session', action: 'rename', error, source: 'business' });
    }

    forwarders.rename(newName);
  };

  const handleSessionSwitched = (session: ISession | null) => {
    if (session) {
      sessionName.value = session.sessionName || '';
      const hasContent = (session.sessionContentCount ?? 0) > 0 || checkHasRealContents();
      hasSessionContents.value = hasContent;
    }
  };

  // ==================== Expose 方法 ====================

  const addNewSession = async (options?: CreateSessionOptions) => {
    if (options) {
      await sessionBusinessManager.createSession(options);
    } else {
      await sessionBusinessManager.createNewSession();
    }
  };

  const switchToSession = async (sessionCode: string) => {
    if (chatBotRef.value) {
      await chatBotRef.value.switchSession(sessionCode);
    }
  };

  const updateSessionName = async (sessionCode: string, newName: string) => {
    try {
      await sessionBusinessManager.updateSessionName(sessionCode, newName);
      sessionName.value = newName;
    } catch (error) {
      console.error('[AIBlueking] Failed to update session name:', error);
      reportSdkError({ apiName: 'session', action: 'updateSessionName', error, source: 'business' });
    }
  };

  return {
    sessionName,
    hasPermission,
    hasSessionContents,
    autoGenerateLoading,
    handleNewChat,
    handleNewChatCreated,
    handleHistoryClick,
    handleHistorySessionSwitch,
    handleHistorySessionDelete,
    handleHistorySessionRename,
    handleAutoGenerateName,
    handleHelpClick,
    handleRename,
    handleSessionSwitched,
    addNewSession,
    switchToSession,
    updateSessionName,
  };
}
