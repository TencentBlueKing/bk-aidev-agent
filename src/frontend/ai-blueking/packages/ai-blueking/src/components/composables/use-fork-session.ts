/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref } from 'vue';

import type { SessionBusinessManager } from '../../manager/business/session-business-manager';
import type { IChatHelper } from '../../types';
import type { ChatBotEmitFn } from './use-chatbot-init';
import type { ReportChatBotError } from './use-error-reporter';
import type { IMessage } from '@blueking/chat-helper';
import type { Message, MessageForkInfo } from '@blueking/chat-x';

export interface UseForkSessionParams {
  chatHelper: Ref<IChatHelper | null>;
  clearCite: () => void;
  emit: ChatBotEmitFn;
  exitShareMode: () => void;
  reportError: ReportChatBotError;
  sessionBusinessManager: Ref<null | SessionBusinessManager>;
}

export interface UseForkSessionReturn {
  forkFromMessages: (messages: Message[]) => Promise<void>;
  handleForkSourceClick: (forkInfo: MessageForkInfo) => Promise<void>;
}

export function useForkSession(params: UseForkSessionParams): UseForkSessionReturn {
  const { emit, chatHelper, sessionBusinessManager, reportError, exitShareMode, clearCite } = params;

  const forkFromMessages = async (messages: Message[]) => {
    if (!sessionBusinessManager.value || !chatHelper.value) {
      console.error('[ChatBot] Cannot fork session: not initialized');
      return;
    }

    try {
      const contentId = await sessionBusinessManager.value.getForkContentId(messages as unknown as IMessage[]);
      if (contentId === undefined) {
        console.error('[ChatBot] Cannot fork session: no persisted content id');
        return;
      }
      exitShareMode();
      clearCite();
      await sessionBusinessManager.value.forkSession(contentId);
      emit('session-switched', sessionBusinessManager.value.currentSession.value);
    } catch (error) {
      reportError(error, 'Failed to fork session');
    }
  };

  const handleForkSourceClick = async (forkInfo: MessageForkInfo) => {
    if (!sessionBusinessManager.value) {
      console.error('[ChatBot] Cannot open fork source: sessionBusinessManager not initialized');
      return;
    }

    if (!forkInfo?.source_session_code) {
      console.error('[ChatBot] Cannot open fork source: missing source_session_code');
      return;
    }

    try {
      exitShareMode();
      clearCite();
      await sessionBusinessManager.value.openForkSource(forkInfo.source_session_code);
      emit('session-switched', sessionBusinessManager.value.currentSession.value);
    } catch (error) {
      reportError(error, 'Failed to open fork source session');
    }
  };

  return {
    forkFromMessages,
    handleForkSourceClick,
  };
}
