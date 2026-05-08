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

import { AGUIProtocol, ApprovalInterruptTicketStatus, type IResume } from '../event';
import { MessageRole, MessageStatus } from '../message';

import type { IRequestConfig, ISSEProtocol } from '../http';
import type { IMediatorModule } from '../mediator';
import type { IInterruptMessage, IMessageProperty, IUserMessage } from '../message/type';
import type { IAgentInfo } from './type';

/**
 * Agent 模块
 * @param options - 配置选项
 * @param mediator - 中介者模块，用于获取其他模块的引用
 */
export const useAgent = (mediator: IMediatorModule, protocol: ISSEProtocol) => {
  const info = ref<IAgentInfo | null>(null);
  const isInfoLoading = ref(false);
  const isChatting = ref(false);
  let usedProtocol: ISSEProtocol = protocol || new AGUIProtocol();
  let abortController: AbortController | null = null;

  const getAgentInfo = () => {
    isInfoLoading.value = true;
    return mediator.http?.agent
      .getAgentInfo()
      .then((res: IAgentInfo) => {
        info.value = res;
      })
      ['finally'](() => {
        isInfoLoading.value = false;
      });
  };

  // 处理角色消息
  const handleRole = (data: IAgentInfo, sessionCode: string) => {
    const lastRoleMessage = data.promptSetting?.content?.at(-1);
    if (lastRoleMessage?.role === MessageRole.Pause) {
      mediator.message?.createAndPlusMessage({
        role: MessageRole.Assistant,
        content: lastRoleMessage.content,
        status: MessageStatus.Complete,
        sessionCode,
        property: {
          extra: {
            pause: true,
          },
        },
      });
    }
  };

  const streamRequest = async (sessionCode: string, url?: string, config?: IRequestConfig, resume?: IResume) => {
    // ag-ui 协议需要注入消息模块
    if (usedProtocol instanceof AGUIProtocol) {
      usedProtocol.injectMessageModule(mediator.message);
    }
    // 事件代理
    const onDone = () => {
      isChatting.value = false;
      usedProtocol.onDone?.call(usedProtocol);
    };
    const onError = (error: Error) => {
      isChatting.value = false;
      usedProtocol.onError?.call(usedProtocol, error);
    };
    const onMessage = (event: unknown) => {
      usedProtocol.onMessage?.call(usedProtocol, event);
    };
    const onStart = () => {
      isChatting.value = true;
      usedProtocol.onStart?.call(usedProtocol);
    };
    // 创建 AbortController
    abortController = new AbortController();
    // 发起聊天
    mediator.http?.fetchClient.streamRequest({
      url: url || 'chat_completion/',
      method: 'POST',
      data: {
        session_code: sessionCode,
        resume,
        execute_kwargs: {
          stream: true,
        },
      },
      controller: abortController,
      onDone,
      onError,
      onMessage,
      onStart,
      ...config,
    });
  };

  /**
   * 发送聊天消息
   * @param userInput - 用户输入的消息内容
   * @param sessionCode - 会话代码
   * @param url - 请求 URL（可选）
   * @param config - 请求配置（可选）
   * @param property - 消息属性，用于传递引用内容或快捷键相关信息（可选）
   */
  const chat = async (
    userInput: IUserMessage['content'],
    sessionCode: string,
    url?: string,
    config?: IRequestConfig,
    property?: IMessageProperty,
  ) => {
    // 先新增一个 message
    await mediator.message?.createAndPlusMessage({
      role: MessageRole.User,
      content: userInput,
      status: MessageStatus.Complete,
      sessionCode,
      ...(property && { property }),
    });
    // 发起聊天
    streamRequest(sessionCode, url, config);
  };

  /**
   * 恢复流式聊天
   * 如果最后一条消息处于流式传输中或是用户消息，重新建立连接
   * @param sessionCode - 会话代码
   * @param url - 请求 URL（可选）
   * @param config - 请求配置（可选）
   */
  const resumeStreamingChat = (sessionCode: string, url?: string, config?: IRequestConfig) => {
    const lastMessage = mediator.message?.list.value.at(-1);
    if (lastMessage?.status === MessageStatus.Streaming || lastMessage?.role === MessageRole.User) {
      streamRequest(sessionCode, url, config);
    }
  };

  /**
   * 轮询接口，判断是否可以继续聊天
   * @param sessionCode - 会话编码
   * @returns 是否可以继续聊天
   */
  const pollResumeSession = (sessionCode: string) => {
    const lastMessage = mediator.message?.list.value.at(-1) as IInterruptMessage;
    const isInterruptMessage = lastMessage?.role === MessageRole.Interrupt;
    const isTicketPending = lastMessage?.content?.interrupt?.metadata?.ticket?.status === ApprovalInterruptTicketStatus.Pending;
    if (isInterruptMessage && isTicketPending) {
      setTimeout(() => {
        // 如果会话不匹配，则不继续轮询
        if (sessionCode !== mediator.session?.current?.value?.sessionCode) return;
        // 轮询接口，判断是否可以继续聊天
        mediator.http?.session.isResumeSession(sessionCode).then(res => {
          if (res) {
            // 可以继续聊天，重新发起聊天
            streamRequest(sessionCode)
          } else {
            // 不可以继续聊天，继续轮询
            pollResumeSession(sessionCode);
          }
        });
      }, 30000)
    }
  };

  /**
   * 中止聊天（纯前端中止，后端继续处理）
   */
  const abortChat = () => {
    abortController?.abort?.();
    abortController = null;
  };

  /**
   * 停止会话，后端中止
   * @param sessionCode - 会话代码
   */
  const stopChat = async (sessionCode: string) => {
    return mediator.http.message?.stopChat(sessionCode);
  };

  /**
   * 重新发送消息（乐观更新）
   * 删除指定用户消息及其后续所有消息，同时创建新消息并重新发送
   *
   * @param messageId - 用户消息 ID（id 字段）
   * @param sessionCode - 会话编码
   * @param newContent - 新内容（可选，不传则使用原消息内容；支持多模态）
   * @param url - 请求 URL（可选）
   * @param config - 请求配置（可选）
   */
  const resendMessage = async (
    messageId: string,
    sessionCode: string,
    newContent?: IUserMessage['content'],
    url?: string,
    config?: IRequestConfig,
  ) => {
    const messages = mediator.message?.list.value || [];

    // 1. 找到目标用户消息
    const messageIndex = messages.findIndex(m => String(m.id) === messageId);
    if (messageIndex === -1) {
      throw new Error(`Message not found: ${messageId}`);
    }

    const targetMessage = messages[messageIndex];
    if (targetMessage.role !== MessageRole.User) {
      throw new Error('Can only resend user messages');
    }

    // 2. 获取原消息内容和 property（在删除前保存）
    const originalContent = targetMessage.content;
    const originalProperty = targetMessage.property;

    // 3. 确定最终发送的内容
    const finalContent = newContent ?? originalContent;

    // 4. 收集需要删除的消息（目标用户消息 + 后续所有消息）
    const messagesToDelete = messages.slice(messageIndex);

    // 5. 并行执行删除和创建（乐观更新：立即更新 UI，API 调用在后台进行）
    // 不等待 API 返回，让 UI 立即响应
    const deletePromise = mediator.message?.deleteMessages(messagesToDelete);
    const createPromise = mediator.message?.createAndPlusMessage({
      role: MessageRole.User,
      content: finalContent,
      status: MessageStatus.Complete,
      sessionCode,
      ...(originalProperty && { property: originalProperty }),
    });

    // 6. 立即发起流式请求（不等待删除和创建的 API 完成）
    streamRequest(sessionCode, url, config);

    // 7. 在后台等待 API 完成，处理可能的错误
    Promise.all([deletePromise, createPromise])['catch'](error => {
      console.error('[resendMessage] API error:', error);
    });
  };

  const reset = (protocol: ISSEProtocol) => {
    // 重置状态
    usedProtocol = protocol || new AGUIProtocol();
    info.value = null;
    isInfoLoading.value = false;
  };

  return {
    info,
    isInfoLoading,
    isChatting,
    chat,
    handleRole,
    resendMessage,
    resumeStreamingChat,
    abortChat,
    stopChat,
    getAgentInfo,
    reset,
    pollResumeSession,
  };
};

export type IAgentModule = ReturnType<typeof useAgent>;
