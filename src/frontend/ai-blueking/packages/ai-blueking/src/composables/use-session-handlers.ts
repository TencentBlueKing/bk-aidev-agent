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

import type ChatBot from '../components/chat-bot.vue';
import type { SessionBusinessManager } from '../manager/business/session-business-manager';
import type { IChatHelper, ISession } from '../types';
import type { EventForwarders } from './use-ai-blueking-init';
import type { IMessageProperty } from '@blueking/chat-helper';

export interface UseSessionHandlersParams {
  chatBotRef: Ref<InstanceType<typeof ChatBot> | undefined>;
  chatHelper: IChatHelper;
  currentSession: ComputedRef<ISession | null>;
  forwarders: EventForwarders;
  sessionBusinessManager: SessionBusinessManager;
  handleError: (error: Error) => void;
}

export function useSessionHandlers(params: UseSessionHandlersParams) {
  const { chatHelper, sessionBusinessManager, chatBotRef, forwarders, handleError, currentSession } = params;

  // ==================== 会话状态 ====================
  const sessionName = ref('');
  const hasPermission = ref(true);
  const hasSessionContents = ref(false);

  // ==================== 辅助方法 ====================

  /**
   * 判断消息列表中是否存在真实会话内容（排除 promptSetting pause 预设消息）
   * pause 消息通过 property.extra.pause 标识，仅用于初始化展示，不算用户发起的会话
   */
  const checkHasRealContents = () => {
    return chatHelper.message.list.value.some(msg => {
      if (!('property' in msg)) return true;
      const { property } = msg as { property?: IMessageProperty };
      return !property?.extra?.pause;
    });
  };

  // ==================== Watchers ====================

  watch(
    () => currentSession.value,
    session => {
      if (session) {
        sessionName.value = session.sessionName || '';
        hasSessionContents.value = (session.sessionContentCount ?? 0) > 0;
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

  const handleHistoryClick = (event: Event) => {
    forwarders.historyClick(event);
  };

  const handleHistorySessionSwitch = async (sessionCode: string) => {
    chatBotRef.value?.exitShareMode();
    await sessionBusinessManager.switchSession(sessionCode);
  };

  const handleHistorySessionDelete = async (sessionCode: string) => {
    await sessionBusinessManager.deleteSession(sessionCode);
  };

  const handleHistorySessionRename = async (sessionCode: string, newName: string) => {
    await sessionBusinessManager.updateSessionName(sessionCode, newName);
  };

  const handleAutoGenerateName = async () => {
    const sessionCode = chatHelper.session.current?.value?.sessionCode;
    if (!sessionCode) {
      console.error('[AIBlueking] Cannot auto-generate name: no active session');
      return;
    }

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
      handleError(error as Error);
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
      handleError(error as Error);
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

  const addNewSession = async (sessionCode?: string) => {
    if (sessionCode) {
      await sessionBusinessManager.createSession({ sessionCode });
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
      handleError(error as Error);
    }
  };

  return {
    sessionName,
    hasPermission,
    hasSessionContents,
    handleNewChat,
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
