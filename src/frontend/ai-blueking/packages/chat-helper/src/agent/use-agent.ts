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

import {
  AGUIProtocol,
  ApprovalInterruptTicketStatus,
  EventType,
  IApprovalInterrupt,
  ResumeStatus,
  RunFinishedOutcomeType,
  type IEvent,
  type IResume,
} from '../event';
import { MessageRole, MessageStatus, UserOperation } from '../message';

import type { IRequestConfig, IRequestError, ISSEProtocol } from '../http';
import type { IMediatorModule } from '../mediator';
import type { IInterruptMessage, IMessageProperty, IUserMessage, IUserOperationPayload } from '../message/type';
import type { IAgentInfo } from './type';
import { SessionStatus } from '../session/type';

/** SSE 静默重连最大次数（退避总时长约 23s，落在后端 orphan grace ~30s 内） */
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 8000;
type StreamMode = 'start' | 'attach';

const getReconnectDelayMs = (attempt: number): number =>
  Math.min(RECONNECT_BASE_DELAY_MS * 2 ** (attempt - 1), RECONNECT_MAX_DELAY_MS);

/**
 * 判断流式错误是否可静默重连。
 * 不重试：Abort、401/403 等业务 4xx（408/429 除外）；可重试：网络错误、5xx、无状态码的中断。
 */
const isRecoverableStreamError = (error: Error): boolean => {
  if (error.name === 'AbortError') {
    return false;
  }

  const requestError = error as IRequestError;
  const statusFromResponse = requestError.response?.status;
  const statusFromMessage = error.message.match(/status code (\d+)/i);
  const status = statusFromResponse ?? (statusFromMessage ? Number(statusFromMessage[1]) : undefined);

  if (status !== undefined) {
    if (status === 408 || status === 429) {
      return true;
    }
    if (status >= 400 && status < 500) {
      return false;
    }
    if (status >= 500) {
      return true;
    }
  }

  return true;
};

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
  let chatAbortController: AbortController | null = null;
  let resumeAbortController: AbortController | null = null;
  let longPollTimer: ReturnType<typeof setTimeout> | null = null;

  /** 用户主动中止（abortChat），禁止自动重连 */
  let manualAbort = false;
  /** 当前轮次已静默重连次数 */
  let reconnectAttempt = 0;
  /** 本轮流是否已收到 RUN_FINISHED */
  let runFinished = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectWaitResolve: ((continued: boolean) => void) | null = null;
  let activeStreamContext: {
    sessionCode: string;
    url?: string;
    config?: IRequestConfig;
  } | null = null;

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

  const userOperationStreamRequest = (
    sessionCode: string,
    operation: UserOperation,
    payload: IUserOperationPayload,
    config?: IRequestConfig,
  ) => {
    return mediator.http?.message.userOperation(sessionCode, operation, payload, config).then(() => {
      if (operation !== UserOperation.ApprovalCancel) {
        streamRequest({ sessionCode, config });
      } else {
        clearLongPollTimer();
        pollResumeSession(sessionCode);
      }
    });
  };

  const clearReconnectTimer = (continued = false) => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (reconnectWaitResolve) {
      const resolve = reconnectWaitResolve;
      reconnectWaitResolve = null;
      resolve(continued);
    }
  };

  const waitForReconnectDelay = (ms: number): Promise<boolean> =>
    new Promise(resolve => {
      reconnectWaitResolve = resolve;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        reconnectWaitResolve = null;
        resolve(true);
      }, ms);
    });

  const resetStreamReconnectState = () => {
    manualAbort = false;
    reconnectAttempt = 0;
    runFinished = false;
    clearReconnectTimer(false);
  };

  /** 裁掉尾部尚未完成的非用户消息，避免断线重放时重复气泡 */
  const pruneTrailingIncompleteMessages = () => {
    const list = mediator.message?.list.value;
    if (!list?.length) {
      return;
    }
    while (list.length > 0) {
      const last = list[list.length - 1];
      if (last.role === MessageRole.User) {
        break;
      }
      if (last.status === MessageStatus.Streaming || last.status === MessageStatus.Pending) {
        list.pop();
        continue;
      }
      break;
    }
  };

  const isSameActiveSession = (sessionCode: string): boolean =>
    sessionCode === mediator.session?.current?.value?.sessionCode;

  /**
   * 尝试静默重连。
   * @returns reconnected | finished（服务端已结束）| failed（需对外报错或中止）
   */
  const attemptSilentReconnect = async (
    sessionCode: string,
  ): Promise<'reconnected' | 'finished' | 'failed'> => {
    if (manualAbort || !isSameActiveSession(sessionCode)) {
      return 'failed';
    }

    try {
      await mediator.session?.getSession(sessionCode);
    } catch {
      // 状态刷新失败时沿用本地 session.status
    }

    if (manualAbort || !isSameActiveSession(sessionCode)) {
      return 'failed';
    }

    if (mediator.session?.current.value?.status !== SessionStatus.Running) {
      return 'finished';
    }

    if (reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      return 'failed';
    }

    reconnectAttempt += 1;
    // 静默重连期间保持「生成中」态
    isChatting.value = true;
    const delayMs = getReconnectDelayMs(reconnectAttempt);
    const waited = await waitForReconnectDelay(delayMs);
    if (!waited || manualAbort || !isSameActiveSession(sessionCode)) {
      return 'failed';
    }

    if (mediator.session?.current.value?.status !== SessionStatus.Running) {
      return 'finished';
    }

    pruneTrailingIncompleteMessages();
    const lastMessageId = mediator.message?.list.value.at(-1)?.id;
    const ctx = activeStreamContext;
    streamRequest({
      sessionCode,
      url: ctx?.url,
      config: ctx?.config,
      lastMessageId: lastMessageId !== undefined ? String(lastMessageId) : undefined,
      isReconnect: true,
      streamMode: 'attach',
    });
    return 'reconnected';
  };

  const streamRequest = async ({
    sessionCode,
    url,
    config,
    resume,
    input,
    lastMessageId,
    isReconnect = false,
    streamMode = 'start',
  }: {
    sessionCode: string;
    url?: string;
    config?: IRequestConfig;
    resume?: IResume;
    input?: string;
    lastMessageId?: string;
    /** 内部静默重连，不重置重连计数 */
    isReconnect?: boolean;
    /** start 可启动新一轮执行；attach 仅接管/回放已有流 */
    streamMode?: StreamMode;
  }) => {
    if (!isReconnect) {
      resetStreamReconnectState();
    }

    activeStreamContext = { sessionCode, url, config };

    // ag-ui 协议需要注入消息模块
    if (usedProtocol instanceof AGUIProtocol) {
      usedProtocol.injectMessageModule(mediator.message);
    }
    if (input) {
      // 列表新增一个用户消息
      mediator.message?.list.value.push({
        role: MessageRole.User,
        content: input,
        status: MessageStatus.Complete,
        sessionCode,
      });
    }

    const finishSuccessfully = () => {
      isChatting.value = false;
      usedProtocol.onDone?.call(usedProtocol);
      if (input) {
        // 刷新列表，获取前端 mock message 的 id，并更新到列表中
        mediator.http?.message?.getMessages(sessionCode).then(res => {
          const lastUserMessage = mediator.message?.list.value.findLast(item => item.role === MessageRole.User);
          const lastApiUserMessage = res.findLast(item => item.role === MessageRole.User);
          if (lastUserMessage && lastApiUserMessage) {
            lastUserMessage.id = lastApiUserMessage.id;
          }
        });
      }
      // 轮询接口，判断是否可以继续聊天
      pollResumeSession(sessionCode);
    };

    const failWithError = (error: Error) => {
      isChatting.value = false;
      usedProtocol.onError?.call(usedProtocol, error);
    };

    // 事件代理
    const onDone = () => {
      // 用户 abort：FetchClient 将 AbortError 转为 onDone，不重连
      if (manualAbort || runFinished) {
        finishSuccessfully();
        return;
      }

      // 连接被干净掐断且未收到 RUN_FINISHED：尝试静默重连
      void attemptSilentReconnect(sessionCode).then(result => {
        if (result === 'reconnected') {
          // 保持 isChatting=true，不展示错误
          return;
        }
        if (result === 'finished') {
          finishSuccessfully();
          return;
        }
        // abort / 切会话导致的失败：静默结束，不展示错误气泡
        if (manualAbort || !isSameActiveSession(sessionCode)) {
          isChatting.value = false;
          return;
        }
        failWithError(new Error('Connection lost, please try again'));
      });
    };

    const onError = (error: Error) => {
      if (manualAbort) {
        return;
      }

      if (!isRecoverableStreamError(error)) {
        failWithError(error);
        return;
      }

      void attemptSilentReconnect(sessionCode).then(result => {
        if (result === 'reconnected') {
          return;
        }
        if (result === 'finished') {
          finishSuccessfully();
          return;
        }
        if (manualAbort || !isSameActiveSession(sessionCode)) {
          isChatting.value = false;
          return;
        }
        failWithError(error);
      });
    };

    const onMessage = (event: unknown) => {
      const typedEvent = event as IEvent;
      if (typedEvent?.type === EventType.RunFinished) {
        runFinished = true;
      }
      usedProtocol.onMessage?.call(usedProtocol, event);
    };

    const onStart = () => {
      isChatting.value = true;
      usedProtocol.onStart?.call(usedProtocol);
    };

    // 创建 AbortController
    chatAbortController = new AbortController();
    // 发起聊天
    void mediator.http?.fetchClient
      .streamRequest({
        url: url || 'chat_completion/',
        method: 'POST',
        data: {
          session_code: sessionCode,
          input,
          execute_kwargs: {
            stream: true,
            stream_mode: streamMode,
            persist_input: !!input,
            last_message_id: lastMessageId,
            resume,
          },
        },
        controller: chatAbortController,
        onDone,
        onError,
        onMessage,
        onStart,
        ...config,
      })
      .catch(() => {
        // 非 abort 错误已通过 onError 回调处理；abort 为正常结束
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
    streamRequest({ sessionCode, url, config });
  };

  /**
   * 恢复流式聊天
   * 如果最后一条消息处于流式传输中或是用户消息，重新建立连接
   * @param sessionCode - 会话代码
   * @param url - 请求 URL（可选）
   * @param config - 请求配置（可选）
   */
  const resumeStreamingChat = (sessionCode: string, url?: string, config?: IRequestConfig) => {
    if (mediator.session?.current.value?.status === SessionStatus.Running) {
      const lastMessageId = mediator.message?.list.value.at(-1)?.id;
      streamRequest({ sessionCode, url, config, lastMessageId, streamMode: 'attach' });
    }
  };

  /**
   * 轮询接口，判断是否可以继续聊天
   * @param sessionCode - 会话编码
   * @returns 是否可以继续聊天
   */
  const pollResumeSession = (sessionCode: string) => {
    const lastMessage = mediator.message?.list.value.at(-1) as IInterruptMessage;
    const pendingApprovalInterrupt =
      lastMessage?.content?.outcome?.type === RunFinishedOutcomeType.Interrupt
        ? lastMessage.content.outcome.interrupts.find(interrupt =>
            [ApprovalInterruptTicketStatus.Pending, ApprovalInterruptTicketStatus.Draft].includes(
              (interrupt as IApprovalInterrupt).metadata?.ticket?.status,
            ),
          )
        : undefined;
    const getIsTicketLoading = () => {
      const isInterruptMessage = lastMessage?.role === MessageRole.Interrupt;
      return isInterruptMessage && !!pendingApprovalInterrupt;
    };
    if (getIsTicketLoading()) {
      // 清除轮询定时器和中断轮询控制器
      clearLongPollTimer();
      resumeAbortController = new AbortController();
      // 轮询接口，判断是否可以继续聊天
      mediator.http?.session.isResumeSession(sessionCode, { controller: resumeAbortController }).then(res => {
        if (res) {
          // 可以继续聊天，重新发起聊天（携带 execute_kwargs.resume 通知后端恢复中断）
          streamRequest({
            sessionCode,
            resume: {
              interruptId: pendingApprovalInterrupt.id,
              status: ResumeStatus.Resolved,
            },
          });
        } else {
          longPollTimer = setTimeout(() => {
              // 如果会话不匹配，则不继续轮询
            if (sessionCode !== mediator.session?.current?.value?.sessionCode) return;
            pollResumeSession(sessionCode);
          }, 10000);
        }
      });
    }
  };

  const clearLongPollTimer = () => {
    clearTimeout(longPollTimer);
    longPollTimer = null;
    resumeAbortController?.abort?.();
    resumeAbortController = null;
  };

  /**
   * 中止聊天（纯前端中止，后端继续处理）
   */
  const abortChat = () => {
    manualAbort = true;
    clearReconnectTimer(false);
    chatAbortController?.abort?.();
    chatAbortController = null;
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
    streamRequest({ sessionCode, url, config });

    // 7. 在后台等待 API 完成，处理可能的错误
    Promise.all([deletePromise, createPromise])['catch'](error => {
      console.error('[resendMessage] API error:', error);
    });
  };

  const reset = (protocol: ISSEProtocol) => {
    abortChat();
    // 重置状态（保留 manualAbort=true，避免 abort 异步 onDone 误触发重连；下次 streamRequest 会复位）
    usedProtocol = protocol || new AGUIProtocol();
    info.value = null;
    isInfoLoading.value = false;
    isChatting.value = false;
    activeStreamContext = null;
    reconnectAttempt = 0;
    runFinished = false;
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
    clearLongPollTimer,
    userOperationStreamRequest,
    streamRequest,
  };
};

export type IAgentModule = ReturnType<typeof useAgent>;
