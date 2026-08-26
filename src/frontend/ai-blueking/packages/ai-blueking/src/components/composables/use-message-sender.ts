/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { shallowRef, watch } from 'vue';
import type { Ref, ShallowRef } from 'vue';

import { applyRequestOptionsContext } from '../../utils';
import type { ChatBusinessManager } from '../../manager/business/chat-business-manager';
import type { IChatHelper, IRequestOptions } from '../../types';
import type { ChatBotEmitFn } from './use-chatbot-init';
import type { ReportChatBotError } from './use-error-reporter';
import type { IUserMessage } from '@blueking/chat-helper';
import type {
  IAiSlashMenuItem,
  Interrupt,
  InterruptResume,
  OnArtifactClick,
  TagSchema,
  UserMessage,
} from '@blueking/chat-x';

import type { UseInterruptResumeReturn } from './use-interrupt-resume';

export interface UseMessageSenderParams {
  chatBusinessManager: Ref<ChatBusinessManager | null>;
  chatHelper: Ref<IChatHelper | null>;
  emit: ChatBotEmitFn;
  /** 返回最新 requestOptions 的 getter（每次调用时读取，确保响应式） */
  getRequestOptions?: () => IRequestOptions | undefined;
  reportError: ReportChatBotError;
  resumeUserQuestionWithInput?: UseInterruptResumeReturn['resumeUserQuestionWithInput'];
  selectedResources: ShallowRef<IAiSlashMenuItem[]>;
  selectedShortcut: Ref<null | { id?: string }>;
}

export interface UseMessageSenderReturn {
  cite: Ref<string>;
  userInput: ShallowRef<string | TagSchema>;
  doSendMessage: (message: IUserMessage['content'], options?: { property?: Record<string, unknown> }) => Promise<void>;
  handleSendMessage: (
    content: UserMessage['content'],
    docSchema: TagSchema,
    options?: { interrupt?: Interrupt; payload?: InterruptResume },
  ) => Promise<void>;
  handleArtifactClick: OnArtifactClick;
  handleStopSending: () => Promise<void>;
  handleUpdateModelValue: (value: string | TagSchema, resourceList: IAiSlashMenuItem[]) => void;
  handleUpload: (file: File) => Promise<{ download_url?: string }>;
  stopGeneration: () => Promise<void>;
}

export function useMessageSender(params: UseMessageSenderParams): UseMessageSenderReturn {
  const {
    emit,
    chatHelper,
    chatBusinessManager,
    getRequestOptions,
    reportError,
    resumeUserQuestionWithInput,
    selectedShortcut,
    selectedResources,
  } = params;

  const userInput = shallowRef<string | TagSchema>([[]]);
  const cite = shallowRef('');

  // 引用绑定当前会话：切换/新建会话后不应把旧会话的引用带到新对话
  watch(
    () => chatHelper.value?.session.current?.value?.sessionCode,
    (newCode, oldCode) => {
      if (oldCode && oldCode !== newCode) {
        cite.value = '';
      }
    },
  );

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

    // 合并 requestOptions.context 到 property.extra.context
    const mergedProperty = applyRequestOptionsContext(options.property, getRequestOptions);

    // 发送消息
    await chatBusinessManager.value.sendMessage(message, sessionCode, {
      ...options,
      ...(mergedProperty ? { property: mergedProperty } : {}),
    });
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

  const handleArtifactClick: OnArtifactClick = async file => {
    const sessionCode = chatHelper.value?.session.current?.value?.sessionCode;
    if (!sessionCode) {
      throw new Error('[ChatBot] Cannot resolve artifact URL: no active session');
    }

    const result = await chatHelper.value!.session.getPvFileDownloadUrl(sessionCode, file.outputId);
    return {
      download_url: result?.download_url,
      preview_url: result?.preview_url,
    };
  };

  /**
   * 处理发送消息
   */
  const handleSendMessage = async (
    content: UserMessage['content'],
    _docSchema: TagSchema,
    options?: { interrupt?: Interrupt; payload?: InterruptResume },
  ) => {
    try {
      if (options?.payload && resumeUserQuestionWithInput) {
        userInput.value = [[]];
        cite.value = '';
        selectedResources.value = [];
        await resumeUserQuestionWithInput(content, options);
        return;
      }

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
      const sendOptions = Object.keys(extra).length ? { property: { extra } } : {};
      await doSendMessage(content as IUserMessage['content'], sendOptions);
    } catch (error) {
      reportError(error, 'Failed to send message');
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
    try {
      await chatBusinessManager.value.stopGeneration();
      emit('stop');
    } catch (error) {
      reportError(error, 'Failed to stop generation');
    }
  };

  return {
    userInput,
    cite,
    handleUpdateModelValue,
    doSendMessage,
    handleSendMessage,
    handleArtifactClick,
    handleUpload,
    handleStopSending,
    stopGeneration,
  };
}
