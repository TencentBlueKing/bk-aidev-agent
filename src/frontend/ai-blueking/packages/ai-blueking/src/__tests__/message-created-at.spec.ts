import { describe, expect, it } from 'vitest';
import { ref } from 'vue';

import {
  AGUIProtocol,
  EventType,
  MessageRole,
  MessageStatus,
  transferMessage2MessageApi,
  transferMessageApi2Message,
} from '@blueking/chat-helper';

import type { IMessage, IMessageModule, IRunFinishedEvent } from '@blueking/chat-helper';

const CREATED_AT = '2026-08-14T08:00:00Z';
const RUN_FINISHED_TIMESTAMP = 1786697775554;
const RUN_FINISHED_CREATED_AT = '2026-08-14T08:56:15.554Z';

function createMessageModule(initial: IMessage[] = []): IMessageModule {
  const list = ref<IMessage[]>([...initial]);
  return {
    list,
    getCurrentLoadingMessage: () =>
      list.value.findLast(item => [MessageStatus.Pending, MessageStatus.Streaming].includes(item.status)),
    getMessageByMessageId: (id: string) => list.value.find(item => item.messageId === id),
    plusMessage: (message: IMessage) => {
      list.value.push(message);
    },
  } as IMessageModule;
}

describe('transferMessageApi2Message created_at', () => {
  it('should map session_contents created_at onto createdAt', () => {
    const result = transferMessageApi2Message({
      id: '12',
      message_id: 'msg-12',
      role: MessageRole.Assistant,
      content: 'hello',
      status: MessageStatus.Complete,
      created_at: CREATED_AT,
    });

    expect(result.createdAt).toBe(CREATED_AT);
  });

  it('should map createdAt back to created_at when posting messages', () => {
    const result = transferMessage2MessageApi({
      id: '12',
      messageId: 'msg-12',
      role: MessageRole.User,
      content: 'hi',
      status: MessageStatus.Complete,
      createdAt: CREATED_AT,
    });

    expect(result.created_at).toBe(CREATED_AT);
  });
});

describe('AGUIProtocol created_at', () => {
  it('should keep created_at from chat_completion MESSAGES_SNAPSHOT', () => {
    const messageModule = createMessageModule();
    const protocol = new AGUIProtocol();
    protocol.injectMessageModule(messageModule);

    protocol.onMessage({
      type: EventType.MessagesSnapshot,
      messages: [
        {
          role: MessageRole.User,
          content: 'hi',
          status: MessageStatus.Complete,
          created_at: CREATED_AT,
        },
        {
          role: MessageRole.Assistant,
          content: 'hello',
          status: MessageStatus.Complete,
          createdAt: '2026-08-14T08:01:00Z',
        },
      ],
    });

    expect(messageModule.list.value[0]?.createdAt).toBe(CREATED_AT);
    expect(messageModule.list.value[1]?.createdAt).toBe('2026-08-14T08:01:00Z');
  });

  it('should convert RUN_FINISHED timestamp to createdAt for this-run messages', () => {
    const messageModule = createMessageModule([
      {
        role: MessageRole.User,
        content: 'old question',
        status: MessageStatus.Complete,
        createdAt: '2026-08-13T01:00:00Z',
      },
      {
        role: MessageRole.User,
        content: 'new question',
        status: MessageStatus.Complete,
      },
      {
        role: MessageRole.Assistant,
        content: 'streaming...',
        status: MessageStatus.Streaming,
        messageId: 'asst-1',
      },
    ]);
    const protocol = new AGUIProtocol();
    protocol.injectMessageModule(messageModule);

    protocol.onMessage({
      type: EventType.RunFinished,
      timestamp: RUN_FINISHED_TIMESTAMP,
      threadId: 'new_session_1785122045012',
      runId: '019fff7c-663d-7a20-95ea-fdacb6c7839c',
      outcome: { type: 'success' },
    } as IRunFinishedEvent);

    expect(messageModule.list.value[0]?.createdAt).toBe('2026-08-13T01:00:00Z');
    expect(messageModule.list.value[1]?.createdAt).toBe(RUN_FINISHED_CREATED_AT);
    expect(messageModule.list.value[2]?.createdAt).toBe(RUN_FINISHED_CREATED_AT);
    expect(messageModule.list.value[2]?.status).toBe(MessageStatus.Complete);
  });
});
