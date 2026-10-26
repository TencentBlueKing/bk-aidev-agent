/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { EventType } from '../event';
import { useMessage } from '../message';
import { MessageRole, MessageStatus } from '../message/type';
import { SessionStatus } from '../session/type';
import { useAgent } from './use-agent';

import type { IMediatorModule } from '../mediator';
import type { IMessage } from '../message/type';

const flush = async () => {
  await Promise.resolve();
  await new Promise(resolve => setTimeout(resolve, 0));
};

function createHarness() {
  const streamRequest = vi.fn().mockResolvedValue(undefined);
  const stopChatHttp = vi.fn().mockResolvedValue(undefined);
  const getMessages = vi.fn().mockResolvedValue([]);
  const getSession = vi.fn().mockResolvedValue(undefined);
  const protocol = {
    onDone: vi.fn(),
    onError: vi.fn(),
    onMessage: vi.fn(),
    onStart: vi.fn(),
  };
  const mediator = {
    agent: null,
    http: {
      fetchClient: { streamRequest },
      message: { stopChat: stopChatHttp, getMessages },
      session: { isResumeSession: vi.fn().mockResolvedValue(false) },
      agent: { getLlms: vi.fn(), getAgentInfo: vi.fn() },
    },
    session: {
      current: ref({ sessionCode: 's1', status: SessionStatus.Running }),
      getSession,
    },
    message: null,
  } as unknown as IMediatorModule;
  (mediator as { message: unknown }).message = useMessage(mediator);
  const agent = useAgent(mediator, protocol);
  const lastStreamCallbacks = () => streamRequest.mock.calls.at(-1)?.[0];
  return { agent, mediator, protocol, streamRequest, stopChatHttp, getMessages, getSession, lastStreamCallbacks };
}

const pushUserAndStreamingAssistant = (harness: ReturnType<typeof createHarness>) => {
  const userMessage: IMessage = {
    role: MessageRole.User,
    content: 'hi',
    status: MessageStatus.Complete,
    sessionCode: 's1',
  };
  const assistantMessage: IMessage = {
    role: MessageRole.Assistant,
    content: 'partial',
    status: MessageStatus.Streaming,
    sessionCode: 's1',
  };
  harness.mediator.message!.list.value.push(userMessage, assistantMessage);
};

describe('useAgent stop seal', () => {
  it('封口后同步停止，且后续事件与关流都不再进入协议层', async () => {
    const harness = createHarness();
    pushUserAndStreamingAssistant(harness);
    await harness.agent.streamRequest({ sessionCode: 's1' });
    const callbacks = harness.lastStreamCallbacks();
    callbacks.onStart();
    expect(harness.agent.isChatting.value).toBe(true);

    const stopPromise = harness.agent.stopChat('s1');
    // 同步封口：不等停止请求返回
    expect(harness.agent.isChatting.value).toBe(false);
    expect(harness.mediator.message!.list.value.at(-1)?.status).toBe(MessageStatus.Stop);
    expect(harness.protocol.onDone).toHaveBeenCalledTimes(1);
    await stopPromise;

    harness.protocol.onMessage.mockClear();
    callbacks.onMessage({ type: EventType.TextMessageContent, messageId: 'm1', delta: 'more' });
    callbacks.onMessage({ type: EventType.MessagesSnapshot, messages: [] });
    callbacks.onMessage({ type: EventType.RunError, message: '用户已取消' });
    expect(harness.protocol.onMessage).not.toHaveBeenCalled();
    expect(harness.mediator.message!.list.value.at(-1)?.content).toBe('partial');

    callbacks.onDone();
    await flush();
    expect(harness.protocol.onDone).toHaveBeenCalledTimes(1);
    // 封口后关流不触发静默重连
    expect(harness.getSession).not.toHaveBeenCalled();
    expect(harness.streamRequest).toHaveBeenCalledTimes(1);
  });

  it('尾段为空时补一条与后端一致的用户已取消（error），列表不再以 User 结尾', async () => {
    const harness = createHarness();
    const userMessage: IMessage = {
      role: MessageRole.User,
      content: 'hi',
      status: MessageStatus.Complete,
      sessionCode: 's1',
    };
    harness.mediator.message!.list.value.push(userMessage);
    await harness.agent.streamRequest({ sessionCode: 's1' });

    await harness.agent.stopChat('s1');

    const last = harness.mediator.message!.list.value.at(-1);
    expect(last?.role).toBe(MessageRole.Assistant);
    expect(last?.content).toBe('用户已取消');
    expect(last?.status).toBe(MessageStatus.Error);
  });

  it('结算时跳过 Interrupt 中断消息', async () => {
    const harness = createHarness();
    pushUserAndStreamingAssistant(harness);
    const interruptMessage: IMessage = {
      role: MessageRole.Interrupt,
      content: { type: EventType.RunFinished, runId: 1, threadId: 't1' },
      status: MessageStatus.Pending,
      sessionCode: 's1',
    };
    harness.mediator.message!.list.value.push(interruptMessage);
    await harness.agent.streamRequest({ sessionCode: 's1' });

    await harness.agent.stopChat('s1');

    const list = harness.mediator.message!.list.value;
    expect(list[1]?.status).toBe(MessageStatus.Stop);
    expect(list[2]?.status).toBe(MessageStatus.Pending);
  });

  it('会话不匹配时不封口', async () => {
    const harness = createHarness();
    pushUserAndStreamingAssistant(harness);
    await harness.agent.streamRequest({ sessionCode: 's1' });
    harness.lastStreamCallbacks().onStart();

    await harness.agent.stopChat('other-session');

    expect(harness.agent.isChatting.value).toBe(true);
    expect(harness.protocol.onDone).not.toHaveBeenCalled();
    expect(harness.mediator.message!.list.value.at(-1)?.status).toBe(MessageStatus.Streaming);
  });

  it('先 abortChat 再 stopChat 时封口不做任何事', async () => {
    const harness = createHarness();
    pushUserAndStreamingAssistant(harness);
    await harness.agent.streamRequest({ sessionCode: 's1' });
    harness.agent.abortChat();

    await harness.agent.stopChat('s1');

    expect(harness.protocol.onDone).not.toHaveBeenCalled();
    expect(harness.mediator.message!.list.value.at(-1)?.status).toBe(MessageStatus.Streaming);
  });

  it('同会话 start 新流等待在途 stop 落定，attach 不等待', async () => {
    const harness = createHarness();
    pushUserAndStreamingAssistant(harness);
    await harness.agent.streamRequest({ sessionCode: 's1' });

    let resolveStop!: () => void;
    harness.stopChatHttp.mockImplementationOnce(
      () =>
        new Promise<void>(resolve => {
          resolveStop = resolve;
        }),
    );
    const stopPromise = harness.agent.stopChat('s1');

    const attachPromise = harness.agent.streamRequest({ sessionCode: 's1', streamMode: 'attach' });
    await attachPromise;
    expect(harness.streamRequest).toHaveBeenCalledTimes(2);

    const startPromise = harness.agent.streamRequest({ sessionCode: 's1' });
    await flush();
    // start 仍在等 stop，不应开第三条流
    expect(harness.streamRequest).toHaveBeenCalledTimes(2);

    resolveStop();
    await stopPromise;
    await startPromise;
    expect(harness.streamRequest).toHaveBeenCalledTimes(3);
  });

  describe('排队等待在途 stop 的 start', () => {
    const queueStartBehindPendingStop = async (harness: ReturnType<typeof createHarness>) => {
      pushUserAndStreamingAssistant(harness);
      await harness.agent.streamRequest({ sessionCode: 's1' });
      let resolveStop!: () => void;
      harness.stopChatHttp.mockImplementationOnce(
        () =>
          new Promise<void>(resolve => {
            resolveStop = resolve;
          }),
      );
      const stopPromise = harness.agent.stopChat('s1');
      harness.mediator.message!.list.value.push({
        role: MessageRole.User,
        content: 'next',
        status: MessageStatus.Complete,
        sessionCode: 's1',
      });
      const startPromise = harness.agent.streamRequest({ sessionCode: 's1' });
      await flush();
      return { resolveStop: () => resolveStop(), stopPromise, startPromise };
    };

    it('等待期间保持生成中，以便界面展示停止按钮', async () => {
      const harness = createHarness();
      const { resolveStop, stopPromise, startPromise } = await queueStartBehindPendingStop(harness);

      expect(harness.agent.isChatting.value).toBe(true);

      resolveStop();
      await stopPromise;
      await startPromise;
      expect(harness.streamRequest).toHaveBeenCalledTimes(2);
    });

    it('等待期间 abortChat 后不再开流', async () => {
      const harness = createHarness();
      const { resolveStop, stopPromise, startPromise } = await queueStartBehindPendingStop(harness);

      harness.agent.abortChat();
      resolveStop();
      await stopPromise;
      await startPromise;

      expect(harness.streamRequest).toHaveBeenCalledTimes(1);
      expect(harness.agent.isChatting.value).toBe(false);
    });

    it('等待期间切走会话后不再开流，并退出生成态', async () => {
      const harness = createHarness();
      const { resolveStop, stopPromise, startPromise } = await queueStartBehindPendingStop(harness);

      harness.mediator.session!.current.value = { sessionCode: 's2', status: SessionStatus.Finished } as never;
      resolveStop();
      await stopPromise;
      await startPromise;

      expect(harness.streamRequest).toHaveBeenCalledTimes(1);
      expect(harness.agent.isChatting.value).toBe(false);
    });

    it('等待期间再次 stopChat 只取消排队的 start，不重复发停止请求', async () => {
      const harness = createHarness();
      const { resolveStop, stopPromise, startPromise } = await queueStartBehindPendingStop(harness);

      const secondStop = harness.agent.stopChat('s1');
      expect(harness.agent.isChatting.value).toBe(false);
      resolveStop();
      await stopPromise;
      await secondStop;
      await startPromise;

      expect(harness.stopChatHttp).toHaveBeenCalledTimes(1);
      expect(harness.streamRequest).toHaveBeenCalledTimes(1);
      const last = harness.mediator.message!.list.value.at(-1);
      expect(last?.content).toBe('用户已取消');
    });
  });

  describe('settleStoppedTurn 与后端取消回写对齐', () => {
    it('尾段只有思考/工具、无助手正文时补用户已取消', async () => {
      const harness = createHarness();
      harness.mediator.message!.list.value.push(
        { role: MessageRole.User, content: 'hi', status: MessageStatus.Complete, sessionCode: 's1' },
        { role: MessageRole.Reasoning, content: ['thinking'], status: MessageStatus.Streaming, sessionCode: 's1' },
        {
          role: MessageRole.Assistant,
          content: '',
          toolCalls: [],
          status: MessageStatus.Pending,
          sessionCode: 's1',
        },
      );
      await harness.agent.streamRequest({ sessionCode: 's1' });

      await harness.agent.stopChat('s1');

      const list = harness.mediator.message!.list.value;
      expect(list[1]?.status).toBe(MessageStatus.Stop);
      expect(list.at(-1)?.content).toBe('用户已取消');
      expect(list.at(-1)?.status).toBe(MessageStatus.Error);
    });

    it('尾段已有助手正文时不补用户已取消', async () => {
      const harness = createHarness();
      pushUserAndStreamingAssistant(harness);
      await harness.agent.streamRequest({ sessionCode: 's1' });

      await harness.agent.stopChat('s1');

      const list = harness.mediator.message!.list.value;
      expect(list).toHaveLength(2);
      expect(list.at(-1)?.content).toBe('partial');
    });
  });

  it('停止请求失败时仍 reject，且后续 start 照常开流', async () => {
    const harness = createHarness();
    pushUserAndStreamingAssistant(harness);
    await harness.agent.streamRequest({ sessionCode: 's1' });
    harness.stopChatHttp.mockRejectedValueOnce(new Error('stop failed'));

    await expect(harness.agent.stopChat('s1')).rejects.toThrow('stop failed');
    // 失败不解除封口
    expect(harness.agent.isChatting.value).toBe(false);
    expect(harness.mediator.message!.list.value.at(-1)?.status).toBe(MessageStatus.Stop);

    await harness.agent.streamRequest({ sessionCode: 's1' });
    expect(harness.streamRequest).toHaveBeenCalledTimes(2);
  });

  it('input 型流封口时只回填最后一条用户消息 id', async () => {
    const harness = createHarness();
    harness.getMessages.mockResolvedValue([
      { role: MessageRole.User, content: 'hello', status: MessageStatus.Complete, id: 'real-1' },
    ]);
    await harness.agent.streamRequest({ sessionCode: 's1', input: 'hello' });
    const pushedUser = harness.mediator.message!.list.value.find(item => item.role === MessageRole.User);
    expect(pushedUser?.id).toBeUndefined();

    await harness.agent.stopChat('s1');
    await flush();

    expect(pushedUser?.id).toBe('real-1');
    expect(harness.getMessages).toHaveBeenCalledWith('s1');
  });
});
