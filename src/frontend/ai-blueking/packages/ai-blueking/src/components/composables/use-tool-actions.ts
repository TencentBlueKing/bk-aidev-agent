/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref } from 'vue';

import { MessageRole } from '@blueking/chat-x';

import { applyRequestOptionsContext, findLastUserMessageBefore, findLastUserMessageIdBefore } from '../../utils';

import type { ChatBusinessManager } from '../../manager/business/chat-business-manager';
import type { IShortcut } from '../../manager/business/types';
import type { IChatHelper, IRequestOptions } from '../../types';
import type { ChatBotEmitFn } from './use-chatbot-init';
import type { IMessage, IUserMessage } from '@blueking/chat-helper';
import type { IToolBtn, Message, Shortcut, TagSchema, UserMessage } from '@blueking/chat-x';

export interface UseToolActionsParams {
  chatBusinessManager: Ref<ChatBusinessManager | null>;
  chatHelper: Ref<IChatHelper | null>;
  cite: Ref<string>;
  emit: ChatBotEmitFn;
  buildShortcutProperty: (shortcut: Shortcut, formModel: Record<string, unknown>) => any;
  focusInput: () => void;
  getShortcutFromMessage: (message: Message) => IShortcut | null;
  /** 返回最新 requestOptions 的 getter（每次调用时读取，确保响应式） */
  getRequestOptions?: () => IRequestOptions | undefined;
  scrollToBottom: () => Promise<void>;
}

export interface UseToolActionsReturn {
  handleAgentAction: (tool: IToolBtn, messages: Message[]) => Promise<string[] | void>;
  handleAgentFeedback: (
    tool: IToolBtn,
    messages: Message[],
    reasonList: string[],
    otherReason: string,
  ) => Promise<void>;
  handleStopStreaming: () => Promise<void>;
  handleUserAction: (tool: IToolBtn, message: Message) => Promise<void>;
  handleUserInputConfirm: (message: Message, content: UserMessage['content'], docSchema: TagSchema) => Promise<void>;
  handleUserShortcutConfirm: (message: Message, formModel: Record<string, unknown>) => Promise<void>;
}

export function useToolActions(params: UseToolActionsParams): UseToolActionsReturn {
  const {
    emit,
    chatHelper,
    chatBusinessManager,
    cite,
    focusInput,
    scrollToBottom,
    getShortcutFromMessage,
    buildShortcutProperty,
    getRequestOptions,
  } = params;

  /**
   * 处理删除消息（AI 消息组 + 对应的用户消息）
   */
  const handleDeleteMessages = async (aiMessages: Message[]) => {
    if (!chatBusinessManager.value || !chatHelper.value) {
      console.error('[ChatBot] Cannot delete messages: chatBusinessManager not initialized');
      return;
    }

    try {
      const allMessages = chatBusinessManager.value.messages.value as Message[];
      const lastUserMessage = findLastUserMessageBefore(allMessages, aiMessages[0]);

      if (!lastUserMessage) {
        console.error('[ChatBot] No user message found before AI messages');
        return;
      }

      const messagesToDelete = [lastUserMessage, ...aiMessages];
      await chatHelper.value.message.deleteMessages(messagesToDelete as any);
    } catch (error) {
      console.error('[ChatBot] Failed to delete messages:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 处理重新生成
   */
  const handleRegenerate = async (aiMessages: Message[]) => {
    if (!chatBusinessManager.value || !chatHelper.value) {
      console.error('[ChatBot] Cannot regenerate: chatBusinessManager not initialized');
      return;
    }

    const sessionCode = chatHelper.value.session.current?.value?.sessionCode;
    if (!sessionCode) {
      console.error('[ChatBot] Cannot regenerate: no active session');
      return;
    }

    try {
      await chatBusinessManager.value.regenerateFromAIMessages(aiMessages as any, sessionCode);
      scrollToBottom();
    } catch (error) {
      console.error('[ChatBot] Failed to regenerate:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 处理删除用户消息（用户消息 + 对应的 AI 回复）
   */
  const handleDeleteUserMessage = async (userMessage: Message) => {
    if (!chatBusinessManager.value || !chatHelper.value) {
      console.error('[ChatBot] Cannot delete message: chatHelper not initialized');
      return;
    }

    try {
      const allMessages = chatBusinessManager.value.messages.value as Message[];
      const userMessageIndex = allMessages.findIndex((m: Message) => m === userMessage);
      if (userMessageIndex === -1) {
        console.error('[ChatBot] User message not found in messages list');
        return;
      }

      const aiMessages: Message[] = [];
      for (let i = userMessageIndex + 1; i < allMessages.length; i++) {
        const msg = allMessages[i];
        if (msg.role === MessageRole.User) {
          break;
        }
        aiMessages.push(msg as Message);
      }

      const messagesToDelete = [userMessage, ...aiMessages];
      await chatHelper.value.message.deleteMessages(messagesToDelete as IMessage[]);
    } catch (error) {
      console.error('[ChatBot] Failed to delete user message:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 处理 AI 消息工具操作
   */
  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    if (tool.id === 'cite') {
      const content = messages
        .filter(message => message.role !== MessageRole.Reasoning)
        .map(message => (typeof message.content === 'string' ? message.content : JSON.stringify(message.content || '')))
        .join('\n');
      cite.value = content;
      focusInput();
      return;
    }

    if (tool.id === 'rebuild') {
      await handleRegenerate(messages);
      return;
    }

    if (tool.id === 'delete') {
      await handleDeleteMessages(messages);
      return;
    }

    if (tool.id === 'like' || tool.id === 'unlike') {
      const rate = tool.id === 'like' ? 5 : 0;
      try {
        const reasons = await chatHelper.value?.session.getSessionFeedbackReasons(rate);
        return reasons || [];
      } catch (error) {
        console.error('[ChatBot] Failed to get feedback reasons:', error);
        return [];
      }
    }

    console.log('handleAgentAction', tool, messages);
  };

  /**
   * 处理 Agent 反馈提交（like/unlike）
   */
  const handleAgentFeedback = async (
    tool: IToolBtn,
    messages: Message[],
    reasonList: string[],
    otherReason: string,
  ) => {
    if (!chatHelper.value) {
      console.error('[ChatBot] Cannot submit feedback: chatHelper not initialized');
      return;
    }

    const sessionCode = chatHelper.value.session.current?.value?.sessionCode;
    if (!sessionCode) {
      console.error('[ChatBot] Cannot submit feedback: no active session');
      return;
    }

    const allMessages = (chatBusinessManager.value?.messages.value || []) as Message[];
    const userMessageId = findLastUserMessageIdBefore(allMessages, messages[0]);

    if (userMessageId === undefined) {
      console.error('[ChatBot] Cannot submit feedback: no user message found');
      return;
    }

    const rate = tool.id === 'like' ? 5 : 0;

    try {
      await chatHelper.value.session.postSessionFeedback({
        sessionCode,
        sessionContentIds: [userMessageId],
        rate,
        labels: reasonList,
        comment: otherReason,
      });
      emit('feedback', tool, messages[0], reasonList, otherReason);
    } catch (error) {
      console.error('[ChatBot] Failed to submit feedback:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 处理用户消息工具操作
   */
  const handleUserAction = async (tool: IToolBtn, message: Message) => {
    if (tool.id === 'delete') {
      await handleDeleteUserMessage(message);
      return;
    }

    if (tool.id === 'cite') {
      const content = typeof message.content === 'string' ? message.content : JSON.stringify(message.content || '');
      cite.value = content;
      focusInput();
      return;
    }

    console.log('handleUserAction', tool, message);
  };

  /**
   * 处理用户消息编辑确认
   */
  const handleUserInputConfirm = async (message: Message, content: UserMessage['content'], _docSchema: TagSchema) => {
    if (!chatHelper.value) {
      console.error('[ChatBot] Cannot edit message: chatHelper not initialized');
      return;
    }

    const sessionCode = chatHelper.value.session.current?.value?.sessionCode;
    if (!sessionCode) {
      console.error('[ChatBot] Cannot edit message: no active session');
      return;
    }

    const messageId = message.id;
    if (messageId === undefined) {
      console.error('[ChatBot] Cannot edit message: message has no id');
      return;
    }

    try {
      const existingProperty = (message as unknown as { property?: Record<string, unknown> }).property;
      const mergedProperty = applyRequestOptionsContext(existingProperty, getRequestOptions);
      await chatBusinessManager.value?.resendMessageWithProperty(
        String(messageId),
        sessionCode,
        typeof content === 'string' ? content : '',
        mergedProperty,
      );
      scrollToBottom();
    } catch (error) {
      console.error('[ChatBot] Failed to edit and resend message:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 处理用户快捷指令消息编辑确认
   */
  const handleUserShortcutConfirm = async (message: Message, formModel: Record<string, unknown>) => {
    if (!chatBusinessManager.value || !chatHelper.value) {
      console.error('[ChatBot] Cannot edit shortcut message: chatHelper not initialized');
      return;
    }

    const sessionCode = chatHelper.value.session.current?.value?.sessionCode;
    if (!sessionCode) {
      console.error('[ChatBot] Cannot edit shortcut message: no active session');
      return;
    }

    const messageId = message.id;
    if (messageId === undefined) {
      console.error('[ChatBot] Cannot edit shortcut message: message has no id');
      return;
    }

    try {
      const shortcut = getShortcutFromMessage(message);
      if (!shortcut) {
        console.error('[ChatBot] Cannot edit shortcut message: shortcut not found');
        return;
      }

      const property = buildShortcutProperty(shortcut as Shortcut, formModel);
      const mergedProperty = applyRequestOptionsContext(property, getRequestOptions);
      const newContent = String(formModel.input ?? '');

      await chatBusinessManager.value.resendMessageWithProperty(
        String(messageId),
        sessionCode,
        newContent,
        mergedProperty,
      );
      scrollToBottom();
    } catch (error) {
      console.error('[ChatBot] Failed to edit shortcut message:', error);
      emit('error', error as Error);
    }
  };

  const handleStopStreaming = async () => {
    if (!chatBusinessManager.value) {
      console.error('[ChatBot] Cannot stop generation: chatBusinessManager not initialized');
      return;
    }
    await chatBusinessManager.value.stopGeneration();
    emit('stop');
  };

  return {
    handleAgentAction,
    handleAgentFeedback,
    handleUserAction,
    handleUserInputConfirm,
    handleUserShortcutConfirm,
    handleStopStreaming,
  };
}
