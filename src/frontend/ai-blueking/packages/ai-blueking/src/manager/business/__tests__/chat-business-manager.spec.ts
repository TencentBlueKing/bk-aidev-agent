import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref, shallowRef } from 'vue';

import { MessageRole } from '@blueking/chat-helper';

import { ChatBusinessManager } from '../chat-business-manager';

vi.mock('../../../utils', () => ({
  findLastUserMessageBefore: vi.fn(),
}));

import { findLastUserMessageBefore } from '../../../utils';

function createMocks() {
  const mockAgentModule = {
    chat: vi.fn().mockResolvedValue(undefined),
    stopChat: vi.fn().mockResolvedValue(undefined),
    getAgentInfo: vi.fn(),
    handleRole: vi.fn(),
    info: ref(null),
    isChatting: ref(false),
    resendMessage: vi.fn(),
  };
  const mockMessageModule = {
    list: shallowRef([]),
    isListLoading: ref(false),
    deleteMessages: vi.fn().mockResolvedValue(undefined),
    shareMessages: vi.fn(),
  };
  const mockSessionModule = {
    current: ref({ sessionCode: 'session-1' }),
    renameSession: vi.fn().mockResolvedValue(undefined),
    list: ref([]),
  };
  const mockEventEmitter = {
    emit: vi.fn(),
  };

  return { mockAgentModule, mockMessageModule, mockSessionModule, mockEventEmitter };
}

describe('ChatBusinessManager', () => {
  let manager: ChatBusinessManager;
  let mocks: ReturnType<typeof createMocks>;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks = createMocks();
    manager = new ChatBusinessManager(
      mocks.mockAgentModule as any,
      mocks.mockMessageModule as any,
      mocks.mockSessionModule as any,
      mocks.mockEventEmitter,
    );
  });

  describe('sendMessage', () => {
    it('should call agentModule.chat and set isGenerating', async () => {
      await manager.sendMessage('hello', 'session-1');

      expect(manager.isGenerating.value).toBe(true);
      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        undefined,
      );
    });

    it('should throw when sessionCode is empty', async () => {
      await expect(manager.sendMessage('hello', '')).rejects.toThrow(
        'No active session',
      );
    });

    it('should auto-rename session when first message', async () => {
      mocks.mockMessageModule.list = shallowRef([
        { id: '1', role: MessageRole.User, content: 'hello' },
      ]);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      await manager.sendMessage('hello', 'session-1');

      expect(mocks.mockSessionModule.renameSession).toHaveBeenCalledWith('session-1');
    });

    it('should not auto-rename when more than one message exists', async () => {
      mocks.mockMessageModule.list = shallowRef([
        { id: '1', role: MessageRole.User, content: 'hello' },
        { id: '2', role: MessageRole.Assistant, content: 'hi' },
      ]);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      await manager.sendMessage('hello', 'session-1');

      expect(mocks.mockSessionModule.renameSession).not.toHaveBeenCalled();
    });

    it('should pass property from options to agentModule.chat', async () => {
      const property = { quote: 'some text' };
      await manager.sendMessage('hello', 'session-1', { property: property as any });

      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        property,
      );
    });
  });

  describe('regenerateMessage', () => {
    it('should locate user message, delete from that index, and resend', async () => {
      const messages = [
        { id: '1', role: MessageRole.User, content: 'hello' },
        { id: '2', role: MessageRole.Assistant, content: 'hi' },
      ];
      mocks.mockMessageModule.list = shallowRef(messages);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      await manager.regenerateMessage('1', 'session-1');

      expect(mocks.mockMessageModule.deleteMessages).toHaveBeenCalledWith(messages);
      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        undefined,
      );
      expect(manager.isGenerating.value).toBe(true);
    });

    it('should throw when message is not found', async () => {
      mocks.mockMessageModule.list = shallowRef([]);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      await expect(manager.regenerateMessage('999', 'session-1')).rejects.toThrow(
        'Message not found: 999',
      );
    });
  });

  describe('regenerateFromAIMessages', () => {
    it('should find user message before AI messages and delegate to regenerateMessage', async () => {
      const userMsg = { id: '1', role: MessageRole.User, content: 'hello' };
      const aiMsg = { id: '2', role: MessageRole.Assistant, content: 'hi' };
      const messages = [userMsg, aiMsg];
      mocks.mockMessageModule.list = shallowRef(messages);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      vi.mocked(findLastUserMessageBefore).mockReturnValue(userMsg as any);

      await manager.regenerateFromAIMessages([aiMsg] as any, 'session-1');

      expect(findLastUserMessageBefore).toHaveBeenCalledWith(messages, aiMsg);
      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        undefined,
      );
    });

    it('should throw when no AI messages provided', async () => {
      await expect(manager.regenerateFromAIMessages([], 'session-1')).rejects.toThrow(
        'No AI messages provided',
      );
    });

    it('should throw when no user message found before AI messages', async () => {
      const aiMsg = { id: '2', role: MessageRole.Assistant, content: 'hi' };
      mocks.mockMessageModule.list = shallowRef([aiMsg]);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      vi.mocked(findLastUserMessageBefore).mockReturnValue(null);

      await expect(manager.regenerateFromAIMessages([aiMsg] as any, 'session-1')).rejects.toThrow(
        'No user message found before AI messages',
      );
    });
  });

  describe('resendMessageWithProperty', () => {
    it('should delete from message index and send with new content and property', async () => {
      const messages = [
        { id: '1', role: MessageRole.User, content: 'old content' },
        { id: '2', role: MessageRole.Assistant, content: 'reply' },
      ];
      mocks.mockMessageModule.list = shallowRef(messages);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );

      const newProperty = { quote: 'new quote' };
      await manager.resendMessageWithProperty('1', 'session-1', 'new content', newProperty as any);

      expect(mocks.mockMessageModule.deleteMessages).toHaveBeenCalledWith(messages);
      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'new content',
        'session-1',
        undefined,
        undefined,
        newProperty,
      );
      expect(manager.isGenerating.value).toBe(true);
    });
  });

  describe('stopGeneration', () => {
    it('should call stopChat with current sessionCode and update states', async () => {
      manager.isGenerating.value = true;

      await manager.stopGeneration();

      expect(mocks.mockAgentModule.stopChat).toHaveBeenCalledWith('session-1');
      expect(manager.isGenerating.value).toBe(false);
      expect(manager.isStopLoading.value).toBe(false);
    });

    it('should set isStopLoading to true during the call and false after', async () => {
      let capturedIsStopLoading = false;
      mocks.mockAgentModule.stopChat.mockImplementation(async () => {
        capturedIsStopLoading = manager.isStopLoading.value;
      });

      await manager.stopGeneration();

      expect(capturedIsStopLoading).toBe(true);
      expect(manager.isStopLoading.value).toBe(false);
    });
  });

  describe('deleteMessage', () => {
    it('should call messageModule.deleteMessages with the message in an array', async () => {
      const message = { id: '1', role: MessageRole.User, content: 'hello' };

      await manager.deleteMessage(message as any);

      expect(mocks.mockMessageModule.deleteMessages).toHaveBeenCalledWith([message]);
    });
  });

  describe('batchDeleteMessages', () => {
    it('should call messageModule.deleteMessages with the messages array', async () => {
      const messages = [
        { id: '1', role: MessageRole.User, content: 'msg1' },
        { id: '2', role: MessageRole.User, content: 'msg2' },
      ];

      await manager.batchDeleteMessages(messages as any);

      expect(mocks.mockMessageModule.deleteMessages).toHaveBeenCalledWith(messages);
      expect(mocks.mockEventEmitter.emit).toHaveBeenCalledWith('messages-batch-deleted', {
        messageIds: ['1', '2'],
      });
    });
  });

  describe('properties', () => {
    it('should expose isMessagesLoading from messageModule', () => {
      mocks.mockMessageModule.isListLoading.value = true;
      expect(manager.isMessagesLoading.value).toBe(true);
    });

    it('should expose openingRemark and predefinedQuestions from config', () => {
      const config = { openingRemark: 'Welcome!', predefinedQuestions: ['Q1', 'Q2'] };
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
        config,
      );

      expect(manager.openingRemark).toBe('Welcome!');
      expect(manager.predefinedQuestions).toEqual(['Q1', 'Q2']);
    });
  });
});
