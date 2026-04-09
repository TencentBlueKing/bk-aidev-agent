/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { type Ref, ref } from 'vue';

import { MessageRole } from '@blueking/chat-helper';

import { findLastUserMessageBefore } from '../../utils';

import type { ChatBusinessConfig, IEventEmitter, SendMessageOptions } from './types';
import type { IAgentModule, IMessage, IMessageModule, ISessionModule, IUserMessage } from '@blueking/chat-helper';

/**
 * 聊天业务管理器
 *
 * 职责：
 * - 封装聊天流程
 * - 处理引用文本、欢迎语等小鲸特有逻辑
 * - 管理聊天状态
 * - 处理消息发送后的副作用（如自动重命名）
 * - 不管理数据，只编排业务流程
 */
export class ChatBusinessManager {
  private _isGenerating: Ref<boolean>;
  private _isStopLoading: Ref<boolean>;

  private agentModule: IAgentModule;
  private config: ChatBusinessConfig;
  private eventEmitter: IEventEmitter | null;

  private messageModule: IMessageModule;
  private sessionModule: ISessionModule | null;
  /**
   * 自动重命名会话（当第一条消息发送成功后）
   * @param sessionCode 会话编码
   */
  private autoRenameSessionIfNeeded(sessionCode: string): void {
    // 没有 sessionModule 则跳过
    if (!this.sessionModule) {
      return;
    }

    // 判断是否为第一条消息（消息列表只有 1 条用户消息）
    const messageCount = this.messageModule.list.value.length;
    if (messageCount !== 1) {
      return;
    }

    // 异步执行重命名，不阻塞后续流程
    this.sessionModule.renameSession(sessionCode).catch((error: unknown) => {
      console.error('[ChatBusinessManager] Auto rename session failed:', error);
    });
  }

  /**
   * 发射事件（内部方法）
   */
  private emit(event: string, data: any): void {
    this.eventEmitter?.emit(event, data);
  }

  constructor(
    agentModule: IAgentModule,
    messageModule: IMessageModule,
    sessionModule: ISessionModule | null = null,
    eventEmitter: IEventEmitter | null = null,
    config: ChatBusinessConfig = {},
  ) {
    this.agentModule = agentModule;
    this.messageModule = messageModule;
    this.sessionModule = sessionModule;
    this.eventEmitter = eventEmitter;
    this.config = config;

    this._isGenerating = ref(false);
    this._isStopLoading = ref(false);
  }
  /**
   * 是否正在生成
   */
  get isGenerating() {
    return this._isGenerating;
  }

  /**
   * 停止生成接口是否正在调用中
   */
  get isStopLoading() {
    return this._isStopLoading;
  }

  get isMessagesLoading() {
    return this.messageModule.isListLoading;
  }

  /**
   * 暴露消息列表
   */
  get messages() {
    return this.messageModule.list;
  }

  /**
   * 欢迎语
   */
  get openingRemark() {
    return this.config.openingRemark || '';
  }

  /**
   * 预定义问题
   */
  get predefinedQuestions() {
    return this.config.predefinedQuestions || [];
  }

  /**
   * 批量删除消息
   * @param messages 消息数组（会自动筛选 user message 的 id 进行删除）
   */
  async batchDeleteMessages(messages: IMessage[]): Promise<void> {
    try {
      // deleteMessages 会自动筛选 user message 的 id 调用 API
      await this.messageModule.deleteMessages(messages);

      const messageIds = messages.map(m => m.id).filter(Boolean);
      this.emit('messages-batch-deleted', {
        messageIds,
      });
    } catch (error) {
      console.error('Failed to batch delete messages:', error);
      this.emit('chat-error', {
        action: 'batch-delete-messages',
        error,
      });
      throw error;
    }
  }

  /**
   * 删除消息
   * @param message 消息对象（必须是 user message，API 会自动删除对应的 AI 回复）
   */
  async deleteMessage(message: IMessage): Promise<void> {
    try {
      // deleteMessages 接收消息数组，内部会筛选 user message 的 id
      await this.messageModule.deleteMessages([message]);

      this.emit('message-deleted', {
        messageId: message.id,
      });
    } catch (error) {
      console.error('Failed to delete message:', error);
      this.emit('chat-error', {
        action: 'delete-message',
        error,
      });
      throw error;
    }
  }

  /**
   * 处理流式响应结束
   */
  handleStreamEnd(): void {
    this._isGenerating.value = false;
    this.emit('receive-end', {});
  }

  /**
   * 处理流式响应错误
   */
  handleStreamError(error: Error): void {
    this._isGenerating.value = false;
    this.emit('receive-error', { error });
  }

  /**
   * 处理流式响应开始
   */
  handleStreamStart(): void {
    this._isGenerating.value = true;
    this.emit('receive-start', {});
  }

  /**
   * 从 AI 消息组重新生成
   * 找到 AI 消息组前面的用户消息，然后执行重新生成
   *
   * @param aiMessages AI 消息组（来自 MessageContainer 的 onAgentAction）
   * @param sessionCode 当前会话编码
   */
  async regenerateFromAIMessages(aiMessages: IMessage[], sessionCode: string): Promise<void> {
    try {
      if (!aiMessages || aiMessages.length === 0) {
        throw new Error('No AI messages provided');
      }

      const messages = this.messages.value;

      // 使用工具函数查找 AI 消息组之前最近的用户消息
      const lastUserMessage = findLastUserMessageBefore(messages, aiMessages[0]);

      if (!lastUserMessage) {
        throw new Error('No user message found before AI messages');
      }

      // 用户消息一定有 id
      const userMessageId = lastUserMessage.id;
      if (userMessageId === undefined) {
        throw new Error('User message has no id');
      }

      // 调用 regenerateMessage 执行实际的重新生成逻辑
      await this.regenerateMessage(String(userMessageId), sessionCode);
    } catch (error) {
      console.error('Failed to regenerate from AI messages:', error);
      this.emit('chat-error', {
        action: 'regenerate',
        error,
      });
      throw error;
    }
  }

  /**
   * 重新生成消息（乐观更新）
   * 从指定的用户消息位置开始，删除该消息及后续消息并重新发送
   *
   * @param messageId 用户消息 ID（id 字段，字符串形式）
   * @param sessionCode 当前会话编码
   */
  async regenerateMessage(messageId: string, sessionCode: string): Promise<void> {
    try {
      const messages = this.messages.value;

      // 1. 定位用户消息（用户消息一定有 id 字段）
      const messageIndex = messages.findIndex((m: IMessage) => String(m.id) === messageId);
      if (messageIndex === -1) {
        throw new Error(`Message not found: ${messageId}`);
      }

      const originalMessage = messages[messageIndex];
      if (originalMessage.role !== MessageRole.User) {
        throw new Error('Can only regenerate from user messages');
      }

      // 2. 获取需要删除的消息（该消息及其后的所有消息）
      const messagesToDelete = messages.slice(messageIndex);

      // 3. 获取原消息内容和属性（在删除前保存）
      const content =
        typeof originalMessage.content === 'string' ? originalMessage.content : JSON.stringify(originalMessage.content);
      const property = (originalMessage as IUserMessage).property;

      // 4. 设置生成状态
      this._isGenerating.value = true;

      // 5. 并行执行删除和创建（乐观更新：立即更新 UI，API 调用在后台进行）
      // 删除是乐观更新，立即从列表移除
      const deletePromise = this.messageModule.deleteMessages(messagesToDelete);

      // chat 内部的 createAndPlusMessage 也是乐观更新，立即添加新消息
      // 同时发起流式请求
      this.agentModule.chat(content, sessionCode, undefined, undefined, property);

      // 6. 发射事件
      this.emit('chat-regenerate', { messageId });

      // 7. 在后台等待删除 API 完成，处理可能的错误
      deletePromise.catch((error: unknown) => {
        console.error('[regenerateMessage] Delete API error:', error);
      });
    } catch (error) {
      console.error('Failed to regenerate message:', error);
      this._isGenerating.value = false;
      this.emit('chat-error', {
        action: 'regenerate',
        error,
      });
      throw error;
    }
  }

  /**
   * 重新发送消息（带新内容和属性）
   * 删除指定用户消息及其后续所有消息，然后用新内容重新发送
   *
   * @param messageId 用户消息 ID（id 字段，字符串形式）
   * @param sessionCode 当前会话编码
   * @param newContent 新的消息内容
   * @param newProperty 新的消息属性（可选）
   */
  async resendMessageWithProperty(
    messageId: string,
    sessionCode: string,
    newContent: string,
    newProperty?: IUserMessage['property'],
  ): Promise<void> {
    try {
      const messages = this.messages.value;

      // 1. 定位用户消息
      const messageIndex = messages.findIndex((m: IMessage) => String(m.id) === messageId);
      if (messageIndex === -1) {
        throw new Error(`Message not found: ${messageId}`);
      }

      const originalMessage = messages[messageIndex];
      if (originalMessage.role !== MessageRole.User) {
        throw new Error('Can only resend user messages');
      }

      // 2. 获取需要删除的消息（该消息及其后的所有消息）
      const messagesToDelete = messages.slice(messageIndex);

      // 3. 设置生成状态
      this._isGenerating.value = true;

      // 4. 并行执行删除和创建（乐观更新）
      const deletePromise = this.messageModule.deleteMessages(messagesToDelete);

      // 使用新内容和新属性发送
      this.agentModule.chat(newContent, sessionCode, undefined, undefined, newProperty);

      // 5. 发射事件
      this.emit('chat-resend', { messageId });

      // 6. 后台等待删除 API 完成
      deletePromise.catch((error: unknown) => {
        console.error('[resendMessageWithProperty] Delete API error:', error);
      });
    } catch (error) {
      console.error('Failed to resend message with property:', error);
      this._isGenerating.value = false;
      this.emit('chat-error', {
        action: 'resend',
        error,
      });
      throw error;
    }
  }

  /**
   * 重试消息
   * @param messageId 消息 ID
   */
  async retryMessage(messageId: string): Promise<void> {
    try {
      // TODO: 实现重试逻辑
      // 这需要 AG-UI SDK 提供相应的方法
      console.warn('retryMessage not implemented yet');

      this.emit('chat-retry', {
        messageId,
      });
    } catch (error) {
      console.error('Failed to retry message:', error);
      this.emit('chat-error', {
        action: 'retry',
        error,
      });
      throw error;
    }
  }

  /**
   * 发送消息
   * @param content 消息内容（字符串或多模态内容数组）
   * @param sessionCode 会话编码
   * @param options 发送选项
   */
  async sendMessage(
    content: IUserMessage['content'],
    sessionCode: string,
    options: SendMessageOptions = {},
  ): Promise<void> {
    try {
      if (!sessionCode) {
        throw new Error('No active session. Please create or select a session first.');
      }

      // 设置生成状态
      this._isGenerating.value = true;

      // 触发发送前事件
      this.emit('send-message', {
        content,
      });

      await this.agentModule.chat(content, sessionCode, undefined, undefined, options.property);

      // 自动重命名：当第一条消息发送成功后
      this.autoRenameSessionIfNeeded(sessionCode);

      // 注意：chat() 是流式的，完成会在 protocol 的 onDone 中处理
    } catch (error) {
      console.error('Failed to send message:', error);
      this._isGenerating.value = false;

      this.emit('chat-error', {
        action: 'send',
        error,
      });

      throw error;
    }
  }

  /**
   * 停止生成
   */
  async stopGeneration(): Promise<void> {
    const sessionCode = this.sessionModule?.current?.value?.sessionCode ?? '';
    this._isStopLoading.value = true;
    try {
      await this.agentModule.stopChat(sessionCode);
      this._isGenerating.value = false;
      this.emit('stop', {});
    } catch (error) {
      console.error('Failed to stop generation:', error);
      this.emit('chat-error', {
        action: 'stop',
        error,
      });
    } finally {
      this._isStopLoading.value = false;
    }
  }
}
