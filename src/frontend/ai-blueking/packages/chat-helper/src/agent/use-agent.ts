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
import type { IAgentInfo, ILlmItem, ILlmListQuery, StreamMode } from './type';
import { SessionStatus } from '../session/type';

/** SSE 静默重连最大次数（退避总时长约 23s，落在后端 orphan grace ~30s 内） */
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 8000;

const getReconnectDelayMs = (attempt: number): number =>
  Math.min(RECONNECT_BASE_DELAY_MS * 2 ** (attempt - 1), RECONNECT_MAX_DELAY_MS);

/** 后端 attach_only 且无可接管流时抛出（见 StreamAttachUnavailableError） */
const isStreamAttachUnavailableError = (error: Error): boolean => /No active or replayable stream/i.test(error.message);

/**
 * 判断流式错误是否可静默重连。
 * 不重试：Abort、attach 无流、401/403 等业务 4xx（408/429 除外）；可重试：网络错误、5xx、无状态码的中断。
 */
const isRecoverableStreamError = (error: Error): boolean => {
  if (error.name === 'AbortError') {
    return false;
  }

  if (isStreamAttachUnavailableError(error)) {
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
  const models = ref<ILlmItem[]>([]);
  const isModelsLoading = ref(false);
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
  /** 流世代号：新开流时递增，用于忽略已被替换的旧 SSE 回调 */
  let activeStreamId = 0;
  /** 尚未结束的那条流的世代号；仅当它仍等于 activeStreamId 时才可被 stopChat 封口 */
  let openStreamId: number | null = null;
  /** 正在进行中的停止请求；同会话下一轮 start 需等它落定后再开新 producer */
  let pendingStop: { promise: Promise<unknown>; sessionCode: string } | null = null;
  /** 正在排队等 pendingStop 的 start（尚未发出请求）；被 stopChat / abortChat / 新的排队 start 替换即作废 */
  let queuedStart: { sessionCode: string } | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectWaitResolve: ((continued: boolean) => void) | null = null;
  let activeStreamContext: {
    sessionCode: string;
    model?: string;
    url?: string;
    config?: IRequestConfig;
    streamMode: StreamMode;
    input?: string;
  } | null = null;

  /**
   * 获取可用模型列表，写入 models；失败时清空列表并抛出
   */
  const getLlms = (params?: ILlmListQuery, config?: IRequestConfig) => {
    isModelsLoading.value = true;
    const request = mediator.http?.agent.getLlms(params, config);
    if (!request) {
      isModelsLoading.value = false;
      models.value = [];
      return Promise.resolve([] as ILlmItem[]);
    }
    return request
      .then((res: ILlmItem[]) => {
        models.value = res;
        return res;
      })
      ['catch']((error: unknown) => {
        models.value = [];
        throw error;
      })
      ['finally'](() => {
        isModelsLoading.value = false;
      });
  };

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
    model?: string,
  ) => {
    return mediator.http?.message.userOperation(sessionCode, operation, payload, config).then(() => {
      if (operation !== UserOperation.ApprovalCancel) {
        streamRequest({ sessionCode, config, model });
      } else {
        clearLongPollTimer();
        pollResumeSession(sessionCode, model);
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

  /** 仅为最后一条用户消息回填后端 id（input 型流的乐观消息用），不整表替换列表 */
  const backfillLastUserMessageId = (sessionCode: string) => {
    const request = mediator.http?.message?.getMessages(sessionCode);
    if (!request) {
      return;
    }
    void request
      .then(res => {
        const lastUserMessage = mediator.message?.list.value.findLast(item => item.role === MessageRole.User);
        const lastApiUserMessage = res.findLast(item => item.role === MessageRole.User);
        if (lastUserMessage && lastApiUserMessage) {
          lastUserMessage.id = lastApiUserMessage.id;
        }
      })
      .catch((): undefined => undefined);
  };

  /**
   * 尝试静默重连。
   * @param streamId - 发起重连的流世代；任一 await 后若已被新流/abort 取代则立即退出，避免 abort 掉更新流
   * @returns reconnected | finished（服务端已结束）| failed（需对外报错或中止）
   */
  const attemptSilentReconnect = async (
    sessionCode: string,
    streamId: number,
  ): Promise<'reconnected' | 'finished' | 'failed'> => {
    const isOwnerStream = () => streamId === activeStreamId && !manualAbort;

    if (!isOwnerStream() || !isSameActiveSession(sessionCode)) {
      return 'failed';
    }

    try {
      await mediator.session?.getSession(sessionCode);
    } catch {
      // 状态刷新失败时沿用本地 session.status
    }

    if (!isOwnerStream() || !isSameActiveSession(sessionCode)) {
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
    if (!waited || !isOwnerStream() || !isSameActiveSession(sessionCode)) {
      return 'failed';
    }

    if (mediator.session?.current.value?.status !== SessionStatus.Running) {
      return 'finished';
    }

    // 发起新流前再校验一次：防止 await 后窗口期被新用户请求抢走 activeStreamId
    if (!isOwnerStream()) {
      return 'failed';
    }

    pruneTrailingIncompleteMessages();
    const lastMessageId = mediator.message?.list.value.at(-1)?.id;
    const ctx = activeStreamContext;
    streamRequest({
      sessionCode,
      model: ctx?.model,
      url: ctx?.url,
      config: ctx?.config,
      lastMessageId: lastMessageId !== undefined ? String(lastMessageId) : undefined,
      isReconnect: true,
      /** 静默重连：仅接管已有流，禁止后端新建 producer */
      streamMode: 'attach',
    });
    return 'reconnected';
  };

  const streamRequest = async ({
    sessionCode,
    model,
    url,
    config,
    resume,
    input,
    lastMessageId,
    isReconnect = false,
    /** start 可启动新一轮执行；attach 仅接管/回放已有流 */
    streamMode = 'start',
  }: {
    sessionCode: string;
    model?: string;
    url?: string;
    config?: IRequestConfig;
    resume?: IResume;
    input?: string;
    lastMessageId?: string;
    /** 内部静默重连，不重置重连计数 */
    isReconnect?: boolean;
    streamMode?: StreamMode;
  }): Promise<void> => {
    // 同会话新一轮 start 必须等在途 stop 落定，避免新 producer 在取消标记生效前启动。
    // attach（切会话/静默重连）不等待。
    if (streamMode === 'start' && pendingStop?.sessionCode === sessionCode) {
      const ticket = { sessionCode };
      queuedStart = ticket;
      // 等待期间保持生成态，界面仍展示停止按钮、禁止再次发送
      isChatting.value = true;
      await pendingStop.promise.catch((): undefined => undefined);
      const stillQueued = queuedStart === ticket;
      if (stillQueued) {
        queuedStart = null;
      }
      if (!stillQueued || !isSameActiveSession(sessionCode)) {
        if (stillQueued) {
          isChatting.value = false;
        }
        return;
      }
    }

    if (!isReconnect) {
      resetStreamReconnectState();
    }

    activeStreamContext = { sessionCode, model, url, config, streamMode, input };

    // 先递增世代再 abort 旧连接，避免旧流 onDone 误触发二次重连
    const streamId = ++activeStreamId;
    openStreamId = streamId;
    const previousController = chatAbortController;
    chatAbortController = new AbortController();
    previousController?.abort?.();

    const isActiveStream = () => streamId === activeStreamId;
    const closeOpenStream = () => {
      if (openStreamId === streamId) {
        openStreamId = null;
      }
    };

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
      if (!isActiveStream()) {
        return;
      }
      closeOpenStream();
      isChatting.value = false;
      usedProtocol.onDone?.call(usedProtocol);
      if (input) {
        backfillLastUserMessageId(sessionCode);
      }
      // 轮询接口，判断是否可以继续聊天
      pollResumeSession(sessionCode);
    };

    const failWithError = (error: Error) => {
      if (!isActiveStream()) {
        return;
      }
      closeOpenStream();
      isChatting.value = false;
      usedProtocol.onError?.call(usedProtocol, error);
    };

    // 事件代理
    const onDone = () => {
      if (!isActiveStream()) {
        return;
      }
      // 用户 abort：本地状态已在 abortChat 结算，勿走 completion/poll
      if (manualAbort) {
        return;
      }
      if (runFinished) {
        finishSuccessfully();
        return;
      }

      // 连接被干净掐断且未收到终端事件（RUN_FINISHED / RUN_ERROR）：尝试静默重连
      void attemptSilentReconnect(sessionCode, streamId).then(result => {
        if (!isActiveStream()) {
          return;
        }
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
          closeOpenStream();
          isChatting.value = false;
          return;
        }
        failWithError(new Error('Connection lost, please try again'));
      });
    };

    const onError = (error: Error) => {
      if (!isActiveStream() || manualAbort) {
        return;
      }

      // attach 时后端无可接管流：视为本轮已结束，勿静默重连空转
      if (streamMode === 'attach' && isStreamAttachUnavailableError(error)) {
        const settleAttachUnavailable = (): void => {
          if (!isActiveStream() || manualAbort || !isSameActiveSession(sessionCode)) {
            if (isActiveStream()) {
              closeOpenStream();
              isChatting.value = false;
            }
            return;
          }
          if (mediator.session?.current.value?.status !== SessionStatus.Running) {
            finishSuccessfully();
            return;
          }
          closeOpenStream();
          isChatting.value = false;
        };
        const refresh = mediator.session?.getSession(sessionCode);
        if (refresh) {
          void refresh.catch((): undefined => undefined).then(settleAttachUnavailable);
        } else {
          settleAttachUnavailable();
        }
        return;
      }

      if (!isRecoverableStreamError(error)) {
        failWithError(error);
        return;
      }

      void attemptSilentReconnect(sessionCode, streamId).then(result => {
        if (!isActiveStream()) {
          return;
        }
        if (result === 'reconnected') {
          return;
        }
        if (result === 'finished') {
          finishSuccessfully();
          return;
        }
        if (manualAbort || !isSameActiveSession(sessionCode)) {
          closeOpenStream();
          isChatting.value = false;
          return;
        }
        failWithError(error);
      });
    };

    const onMessage = (event: unknown) => {
      if (!isActiveStream()) {
        return;
      }
      const typedEvent = event as IEvent;
      // RUN_FINISHED / RUN_ERROR 均为终端事件：关流后走正常收尾，勿静默重连
      // （用户 stop 后后端推 RUN_ERROR「用户已取消」，而非 RUN_FINISHED）
      if (typedEvent?.type === EventType.RunFinished || typedEvent?.type === EventType.RunError) {
        runFinished = true;
      }
      usedProtocol.onMessage?.call(usedProtocol, event);
    };

    const onStart = () => {
      if (!isActiveStream()) {
        return;
      }
      isChatting.value = true;
      usedProtocol.onStart?.call(usedProtocol);
    };

    // 发起聊天（controller / 回调必须在 ...config 之后，防止被覆盖）
    void mediator.http?.fetchClient
      .streamRequest({
        url: url || 'chat_completion/',
        method: 'POST',
        data: {
          session_code: sessionCode,
          model,
          input,
          execute_kwargs: {
            stream: true,
            stream_mode: streamMode,
            persist_input: !!input,
            last_message_id: lastMessageId,
            resume,
          },
        },
        ...config,
        controller: chatAbortController,
        onDone,
        onError,
        onMessage,
        onStart,
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
   * @param model - 模型标识（可选）
   */
  const chat = async (
    userInput: IUserMessage['content'],
    sessionCode: string,
    url?: string,
    config?: IRequestConfig,
    property?: IMessageProperty,
    model?: string,
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
    streamRequest({ sessionCode, model, url, config });
  };

  /**
   * 恢复流式聊天
   * 如果最后一条消息处于流式传输中或是用户消息，重新建立连接
   * @param sessionCode - 会话代码
   * @param url - 请求 URL（可选）
   * @param config - 请求配置（可选）
   * @param model - 模型标识（可选）
   */
  const resumeStreamingChat = (sessionCode: string, url?: string, config?: IRequestConfig, model?: string) => {
    if (mediator.session?.current.value?.status === SessionStatus.Running) {
      const lastMessageId = mediator.message?.list.value.at(-1)?.id;
      streamRequest({
        sessionCode,
        model,
        url,
        config,
        lastMessageId,
        /** 切会话/刷新恢复：仅接管已有流 */
        streamMode: 'attach',
      });
    }
  };

  /**
   * 轮询接口，判断是否可以继续聊天
   * @param sessionCode - 会话编码
   * @returns 是否可以继续聊天
   */
  const pollResumeSession = (sessionCode: string, model?: string) => {
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
            model,
            resume: {
              interruptId: pendingApprovalInterrupt.id,
              status: ResumeStatus.Resolved,
            },
          });
        } else {
          longPollTimer = setTimeout(() => {
            // 如果会话不匹配，则不继续轮询
            if (sessionCode !== mediator.session?.current?.value?.sessionCode) return;
            pollResumeSession(sessionCode, model);
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
   * 按流世代封口（用户主动停止时同步执行）。
   * 使当前流世代失效，后续 SSE 事件不再进入协议层；但不断开连接，
   * 让后端在原连接上完成取消收尾。无可封流时（已结束 / 已 abort）不做任何事。
   * @returns 是否实际封住了一条流
   */
  const sealOpenStream = (sessionCode: string): boolean => {
    if (openStreamId === null || openStreamId !== activeStreamId) {
      return false;
    }
    if (activeStreamContext?.sessionCode !== sessionCode) {
      return false;
    }
    const sealedInput = activeStreamContext.input;
    mediator.message?.settleStoppedTurn?.(sessionCode);
    if (sealedInput) {
      backfillLastUserMessageId(sessionCode);
    }
    isChatting.value = false;
    clearReconnectTimer(false);
    clearLongPollTimer();
    // 先失效世代：此后该连接的 onMessage/onDone/onError 与重连尝试都会直接返回
    activeStreamId += 1;
    openStreamId = null;
    // 本轮唯一的 receive-end 出口；真实关流的 onDone 已因世代失效不会再触发
    usedProtocol.onDone?.call(usedProtocol);
    return true;
  };

  /**
   * 中止聊天（纯前端中止，后端继续处理）
   * 会使当前流世代失效，避免 abort 后的 onDone 误触发 finishSuccessfully / pollResumeSession
   */
  const abortChat = () => {
    manualAbort = true;
    // 先失效世代，再 abort：FetchClient 同步触发的 onDone 会因 isActiveStream=false 直接返回
    activeStreamId += 1;
    openStreamId = null;
    pendingStop = null;
    queuedStart = null;
    clearReconnectTimer(false);
    clearLongPollTimer();
    isChatting.value = false;
    chatAbortController?.abort?.();
    chatAbortController = null;
  };

  /**
   * 取消排队中的 start：它尚未发到后端，本地结算即可，无需再发停止请求
   * @returns 是否实际取消了排队的 start
   */
  const cancelQueuedStart = (sessionCode: string): boolean => {
    if (queuedStart?.sessionCode !== sessionCode) {
      return false;
    }
    queuedStart = null;
    isChatting.value = false;
    mediator.message?.settleStoppedTurn?.(sessionCode);
    return true;
  };

  /**
   * 停止会话，后端中止。
   * 发请求前先同步封口，界面立即停止接受本轮流；请求记为 pendingStop，
   * 同会话下一轮 start 会等它落定。失败仍 reject，且不解除封口。
   * 若同会话有排队等待中的 start，只取消该 start 并等上一轮停止请求落定（其失败由上一轮调用方处理）。
   * @param sessionCode - 会话代码
   */
  const stopChat = async (sessionCode: string): Promise<unknown> => {
    if (cancelQueuedStart(sessionCode)) {
      return pendingStop?.promise.catch((): undefined => undefined);
    }
    sealOpenStream(sessionCode);
    const promise: Promise<unknown> = Promise.resolve(mediator.http?.message?.stopChat(sessionCode));
    const record = { sessionCode, promise };
    pendingStop = record;
    try {
      return await promise;
    } finally {
      if (pendingStop === record) {
        pendingStop = null;
      }
    }
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
   * @param model - 模型标识（可选）
   */
  const resendMessage = async (
    messageId: string,
    sessionCode: string,
    newContent?: IUserMessage['content'],
    url?: string,
    config?: IRequestConfig,
    model?: string,
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
    streamRequest({ sessionCode, model, url, config });

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
    models.value = [];
    isModelsLoading.value = false;
    activeStreamContext = null;
    reconnectAttempt = 0;
    runFinished = false;
  };

  return {
    info,
    isInfoLoading,
    isChatting,
    models,
    isModelsLoading,
    chat,
    handleRole,
    resendMessage,
    resumeStreamingChat,
    abortChat,
    stopChat,
    getAgentInfo,
    getLlms,
    reset,
    pollResumeSession,
    clearLongPollTimer,
    userOperationStreamRequest,
    streamRequest,
  };
};

export type IAgentModule = ReturnType<typeof useAgent>;
