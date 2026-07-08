import { describe, expect, it } from 'vitest';

import { AGUIProtocol, EventType, MessageRole, MessageStatus, useMessage } from '@blueking/chat-helper';

import type { IMediatorModule } from '@blueking/chat-helper';

const createProtocol = () => {
  const messageModule = useMessage({} as IMediatorModule);
  const protocol = new AGUIProtocol();
  protocol.injectMessageModule(messageModule);
  return { messageModule, protocol };
};

describe('AGUIProtocol replay after snapshot', () => {
  it('reuses snapshot text message when replay starts from the same message id', () => {
    const { messageModule, protocol } = createProtocol();

    protocol.onMessage({
      messages: [
        {
          content: 'cached prefix',
          id: '1',
          message_id: 'assistant-mid',
          role: MessageRole.Assistant,
          session_code: 'session-1',
          status: MessageStatus.Streaming,
        },
      ],
      type: EventType.MessagesSnapshot,
    });

    protocol.onMessage({
      messageId: 'assistant-mid',
      role: MessageRole.Assistant,
      type: EventType.TextMessageStart,
    });
    protocol.onMessage({
      delta: 'cached prefix',
      messageId: 'assistant-mid',
      type: EventType.TextMessageContent,
    });
    protocol.onMessage({
      delta: ' new suffix',
      messageId: 'assistant-mid',
      type: EventType.TextMessageContent,
    });

    expect(messageModule.list.value).toHaveLength(1);
    expect(messageModule.list.value[0]).toMatchObject({
      content: 'cached prefix new suffix',
      messageId: 'assistant-mid',
      status: MessageStatus.Streaming,
    });
  });
});
