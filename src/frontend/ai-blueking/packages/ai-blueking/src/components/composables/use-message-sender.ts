/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { shallowRef } from 'vue';
import type { Ref, ShallowRef } from 'vue';

import type { ChatBusinessManager } from '../../manager/business/chat-business-manager';
import type { IChatHelper } from '../../types';
import type { ChatBotEmitFn } from './use-chatbot-init';
import type { IUserMessage } from '@blueking/chat-helper';
import type { IAiSlashMenuItem, TagSchema, UserMessage } from '@blueking/chat-x';

export interface UseMessageSenderParams {
  chatBusinessManager: Ref<ChatBusinessManager | null>;
  chatHelper: Ref<IChatHelper | null>;
  emit: ChatBotEmitFn;
  selectedResources: ShallowRef<IAiSlashMenuItem[]>;
  selectedShortcut: Ref<null | { id?: string }>;
}

export interface UseMessageSenderReturn {
  cite: Ref<string>;
  userInput: ShallowRef<string | TagSchema>;
  doSendMessage: (message: IUserMessage['content'], options?: { property?: Record<string, unknown> }) => Promise<void>;
  handleSendMessage: (content: UserMessage['content'], docSchema: TagSchema) => Promise<void>;
  handleStopSending: () => Promise<void>;
  handleUpdateModelValue: (value: string | TagSchema, resourceList: IAiSlashMenuItem[]) => void;
  handleUpload: (file: File) => Promise<{ download_url?: string }>;
  stopGeneration: () => Promise<void>;
}

export function useMessageSender(params: UseMessageSenderParams): UseMessageSenderReturn {
  const { emit, chatHelper, chatBusinessManager, selectedShortcut, selectedResources } = params;

  const userInput = shallowRef<string | TagSchema>([[]]);
  const cite = shallowRef('');

  const handleUpdateModelValue = (value: string | TagSchema, resourceList: IAiSlashMenuItem[]) => {
    userInput.value = value;
    selectedResources.value = resourceList;
  };

  /**
   * 内部发送消息的核心方法
   */
  const doSendMessage = async (
    message: IUserMessage['content'],
    options: { property?: Record<string, unknown> } = {},
  ) => {
    if (!chatBusinessManager.value || !chatHelper.value) {
      throw new Error('[ChatBot] Cannot send message: chatBusinessManager not initialized');
    }

    const sessionCode = chatHelper.value.session.current?.value?.sessionCode;
    if (!sessionCode) {
      throw new Error('[ChatBot] Cannot send message: no active session');
    }

    // 清空输入框、引用和已选资源
    userInput.value = [[]];
    cite.value = '';
    selectedResources.value = [];

    // 通知外部
    const messageText = typeof message === 'string' ? message : '';
    emit('send-message', messageText);

    // 发送消息
    await chatBusinessManager.value.sendMessage(message, sessionCode, options);
  };

  /**
   * 处理文件上传
   */
  const handleUpload = async (file: File): Promise<{ download_url?: string }> => {
    const sessionCode = chatHelper.value?.session.current?.value?.sessionCode;
    if (!sessionCode) {
      throw new Error('[ChatBot] Cannot upload: no active session');
    }

    const result = await chatHelper.value!.session.uploadFile(sessionCode, file);
    if (!result?.download_url) {
      throw new Error('[ChatBot] Upload failed: no download URL returned');
    }

    return result;
  };

  /**
   * 处理发送消息
   */
  const handleSendMessage = async (content: UserMessage['content'], _docSchema: TagSchema) => {
    try {
      const extra: Record<string, unknown> = {};
      if (cite.value) {
        extra.cite = cite.value;
      }
      if (selectedShortcut.value) {
        extra.command = selectedShortcut.value.id;
      }
      if (selectedResources.value.length) {
        extra.resources = selectedResources.value;
      }
      const options = Object.keys(extra).length ? { property: { extra } } : {};
      await doSendMessage(content as IUserMessage['content'], options);
    } catch (error) {
      console.error('Failed to send message:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 处理停止发送
   */
  const handleStopSending = async () => {
    await stopGeneration();
  };

  const stopGeneration = async () => {
    if (!chatBusinessManager.value) {
      console.error('[ChatBot] Cannot stop generation: chatBusinessManager not initialized');
      return;
    }
    await chatBusinessManager.value.stopGeneration();
    emit('stop');
  };

  return {
    userInput,
    cite,
    handleUpdateModelValue,
    doSendMessage,
    handleSendMessage,
    handleUpload,
    handleStopSending,
    stopGeneration,
  };
}
