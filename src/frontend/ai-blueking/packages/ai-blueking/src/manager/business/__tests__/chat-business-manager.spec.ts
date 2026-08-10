import { describe, it, expect, vi, beforeEach } from 'vitest';
import { nextTick, ref, shallowRef } from 'vue';

import { MessageRole } from '@blueking/chat-helper';

import { ChatBusinessManager } from '../chat-business-manager';

vi.mock('../../../utils', () => ({
  findLastUserMessageBefore: vi.fn(),
}));

import { findLastUserMessageBefore } from '../../../utils';

function createMocks() {
  const mockAgentModule = {
    chat: vi.fn().mockResolvedValue(undefined),
    abortChat: vi.fn(),
    stopChat: vi.fn().mockResolvedValue(undefined),
    getAgentInfo: vi.fn(),
    getLlms: vi.fn().mockResolvedValue([]),
    handleRole: vi.fn(),
    info: ref(null),
    isChatting: ref(false),
    isModelsLoading: ref(false),
    models: ref([]),
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
    updateSession: vi.fn().mockResolvedValue(undefined),
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
        undefined,
      );
    });

    it('should throw when sessionCode is empty', async () => {
      await expect(manager.sendMessage('hello', '')).rejects.toThrow('No active session');
    });

    it('should auto-rename session when first message', async () => {
      mocks.mockMessageModule.list = shallowRef([{ id: '1', role: MessageRole.User, content: 'hello' }]);
      const onSessionRenamed = vi.fn();
      mocks.mockSessionModule.renameSession = vi.fn().mockImplementation(async () => {
        mocks.mockSessionModule.list.value = [{ sessionCode: 'session-1', sessionName: 'AI Generated Name' }];
        return { sessionCode: 'session-1', sessionName: 'AI Generated Name' };
      });
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
        { onSessionRenamed },
      );

      await manager.sendMessage('hello', 'session-1');
      await Promise.resolve();

      expect(mocks.mockSessionModule.renameSession).toHaveBeenCalledWith('session-1');
      expect(onSessionRenamed).toHaveBeenCalledWith('AI Generated Name', 'session-1');
    });

    it('should emit rename with API new name even when local session still has old name', async () => {
      // 业务常见：current 由 getSession 单独设置，不在分页 list 中；updateSessionInList 无法写回新名
      mocks.mockMessageModule.list = shallowRef([{ id: '1', role: MessageRole.User, content: 'hello' }]);
      const onSessionRenamed = vi.fn();
      mocks.mockSessionModule.list.value = [];
      mocks.mockSessionModule.current.value = { sessionCode: 'session-1', sessionName: '新会话' };
      mocks.mockSessionModule.renameSession = vi.fn().mockResolvedValue({
        sessionCode: 'session-1',
        sessionName: '重命名失败',
      });
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
        { onSessionRenamed },
      );

      await manager.sendMessage('hello', 'session-1');
      await Promise.resolve();

      expect(onSessionRenamed).toHaveBeenCalledWith('重命名失败', 'session-1');
      expect(onSessionRenamed).not.toHaveBeenCalledWith('新会话', expect.anything());
    });

    it('should still emit rename with sessionCode when user switched session before rename resolves', async () => {
      mocks.mockMessageModule.list = shallowRef([{ id: '1', role: MessageRole.User, content: 'hello' }]);
      const onSessionRenamed = vi.fn();
      let resolveRename: (value: { sessionCode: string; sessionName: string }) => void = () => {};
      mocks.mockSessionModule.renameSession = vi.fn().mockImplementation(
        () =>
          new Promise(resolve => {
            resolveRename = resolve;
          }),
      );
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
        { onSessionRenamed },
      );

      await manager.sendMessage('hello', 'session-1');
      // rename 尚未返回时用户已切到其他会话 — 仍应抛出，并由业务按 sessionCode 维护列表
      mocks.mockSessionModule.current.value = { sessionCode: 'session-2', sessionName: '另一个会话' };
      resolveRename({ sessionCode: 'session-1', sessionName: 'AI Generated Name' });
      await Promise.resolve();

      expect(onSessionRenamed).toHaveBeenCalledWith('AI Generated Name', 'session-1');
    });

    it('should not emit rename when auto-rename fails', async () => {
      mocks.mockMessageModule.list = shallowRef([{ id: '1', role: MessageRole.User, content: 'hello' }]);
      const onSessionRenamed = vi.fn();
      mocks.mockSessionModule.renameSession = vi.fn().mockRejectedValue(new Error('rename failed'));
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
        { onSessionRenamed },
      );

      await manager.sendMessage('hello', 'session-1');
      await Promise.resolve();

      expect(onSessionRenamed).not.toHaveBeenCalled();
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
        undefined,
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

      await expect(manager.regenerateMessage('999', 'session-1')).rejects.toThrow('Message not found: 999');
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
        undefined,
      );
    });

    it('should throw when no AI messages provided', async () => {
      await expect(manager.regenerateFromAIMessages([], 'session-1')).rejects.toThrow('No AI messages provided');
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
        undefined,
      );
      expect(manager.isGenerating.value).toBe(true);
    });
  });

  describe('stopGeneration', () => {
    it('should abort frontend SSE then call stopChat with current sessionCode', async () => {
      manager.isGenerating.value = true;
      const callOrder: string[] = [];
      mocks.mockAgentModule.abortChat.mockImplementation(() => {
        callOrder.push('abortChat');
      });
      mocks.mockAgentModule.stopChat.mockImplementation(async () => {
        callOrder.push('stopChat');
      });

      await manager.stopGeneration();

      expect(mocks.mockAgentModule.abortChat).toHaveBeenCalled();
      expect(mocks.mockAgentModule.stopChat).toHaveBeenCalledWith('session-1');
      expect(callOrder).toEqual(['abortChat', 'stopChat']);
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

    it('should rethrow when stopChat fails so callers can surface the error', async () => {
      const failure = new Error('stop failed');
      mocks.mockAgentModule.stopChat.mockRejectedValue(failure);

      await expect(manager.stopGeneration()).rejects.toThrow(failure);
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

  describe('model selection', () => {
    const sampleModels = [
      {
        id: 1,
        llm_code: 'hy3-preview',
        llm_name: '混元3',
        llm_type: 'chat.completion',
        max_token_size: 32768,
        property: { default: true },
        space_auth_mode: '',
        user_auth_mode: '',
      },
      {
        id: 2,
        llm_code: 'deepseek',
        llm_name: 'DeepSeek',
        llm_type: 'chat.completion',
        max_token_size: 64000,
        property: {},
        space_auth_mode: '',
        user_auth_mode: '',
      },
    ];

    it('should load models via agent.getLlms and select default', async () => {
      mocks.mockAgentModule.getLlms.mockResolvedValue(sampleModels);

      await manager.loadModels({ force: true });

      expect(mocks.mockAgentModule.getLlms).toHaveBeenCalled();
      expect(manager.models.value).toEqual(sampleModels);
      expect(manager.selectedLlmCode.value).toBe('hy3-preview');
      expect(manager.selectedModelName.value).toBe('混元3');
    });

    it('should reuse cached agent.models without calling getLlms', async () => {
      mocks.mockAgentModule.models.value = sampleModels;

      await manager.loadModels();

      expect(mocks.mockAgentModule.getLlms).not.toHaveBeenCalled();
      expect(manager.selectedLlmCode.value).toBe('hy3-preview');
    });

    it('should pass selected llm_code on send/regenerate/resend', async () => {
      manager.setModels(sampleModels as any);
      manager.setSelectedModelByName('DeepSeek');

      await manager.sendMessage('hello', 'session-1');
      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        undefined,
        'deepseek',
      );

      mocks.mockAgentModule.chat.mockClear();
      mocks.mockMessageModule.list = shallowRef([{ id: '1', role: MessageRole.User, content: 'hello' }]);
      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );
      manager.setModels(sampleModels as any);
      manager.setSelectedModelByName('DeepSeek');

      await manager.regenerateMessage('1', 'session-1');
      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        undefined,
        'deepseek',
      );
    });

    it('should allow options.model to override selected model', async () => {
      manager.setModels(sampleModels as any);

      await manager.sendMessage('hello', 'session-1', { model: 'override-code' });

      expect(mocks.mockAgentModule.chat).toHaveBeenCalledWith(
        'hello',
        'session-1',
        undefined,
        undefined,
        undefined,
        'override-code',
      );
    });

    it('should clear selection when loadModels fails', async () => {
      mocks.mockAgentModule.getLlms.mockRejectedValue(new Error('network'));

      await manager.loadModels({ force: true });

      expect(manager.models.value).toEqual([]);
      expect(manager.selectedLlmCode.value).toBeUndefined();
    });

    it('should prefer session.model over default on first setModels/loadModels', async () => {
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'with-model',
        model: 'deepseek',
      };

      manager.setModels(sampleModels as any);
      expect(manager.selectedLlmCode.value).toBe('deepseek');

      manager = new ChatBusinessManager(
        mocks.mockAgentModule as any,
        mocks.mockMessageModule as any,
        mocks.mockSessionModule as any,
        mocks.mockEventEmitter,
      );
      mocks.mockAgentModule.getLlms.mockResolvedValue(sampleModels);

      await manager.loadModels({ force: true });

      expect(manager.selectedLlmCode.value).toBe('deepseek');
    });

    it('should fall back to default when session has no model', () => {
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'no-model',
      };

      manager.setModels(sampleModels as any);

      expect(manager.selectedLlmCode.value).toBe('hy3-preview');
    });

    it('should follow session.model when current session changes', async () => {
      manager.setModels(sampleModels as any);
      manager.setSelectedModelByName('DeepSeek');
      expect(manager.selectedLlmCode.value).toBe('deepseek');

      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-2',
        sessionName: 'history',
        model: 'hy3-preview',
      };
      await nextTick();

      expect(manager.selectedLlmCode.value).toBe('hy3-preview');
    });

    it('should not re-apply session.model when same session is patched', async () => {
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'chat',
        model: 'hy3-preview',
      };
      await nextTick();
      manager.setModels(sampleModels as any);
      manager.setSelectedModelByName('DeepSeek');
      expect(manager.selectedLlmCode.value).toBe('deepseek');

      // 模拟 updateSessionInList 用旧 model 重写 current（同 sessionCode）
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'chat',
        model: 'hy3-preview',
      };
      await nextTick();

      expect(manager.selectedLlmCode.value).toBe('deepseek');
    });

    it('should wait for session before applying default, then follow session.model on each change', async () => {
      mocks.mockSessionModule.current.value = null;
      await nextTick();

      manager.setModels(sampleModels as any);
      expect(manager.selectedLlmCode.value).toBeUndefined();

      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'late-session',
        model: 'deepseek',
      };
      await nextTick();
      expect(manager.selectedLlmCode.value).toBe('deepseek');

      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-2',
        sessionName: 'another',
        model: 'hy3-preview',
      };
      await nextTick();
      expect(manager.selectedLlmCode.value).toBe('hy3-preview');
    });

    it('should keep default when session model is not in model list after load', () => {
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'unknown-model',
        model: 'not-in-list',
      };

      manager.setModels(sampleModels as any);

      expect(manager.selectedLlmCode.value).toBe('hy3-preview');
    });

    it('should persist selected model via updateSession', async () => {
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'chat',
        model: 'hy3-preview',
      };
      await nextTick();
      manager.setModels(sampleModels as any);
      mocks.mockSessionModule.updateSession.mockClear();

      manager.setSelectedModelByName('DeepSeek');
      await nextTick();

      expect(manager.selectedLlmCode.value).toBe('deepseek');
      expect(mocks.mockSessionModule.updateSession).toHaveBeenCalledWith(
        expect.objectContaining({
          sessionCode: 'session-1',
          model: 'deepseek',
        }),
      );
    });

    it('should skip updateSession when selected model equals current.session.model', async () => {
      mocks.mockSessionModule.current.value = {
        sessionCode: 'session-1',
        sessionName: 'chat',
        model: 'deepseek',
      };
      await nextTick();
      manager.setModels(sampleModels as any);
      mocks.mockSessionModule.updateSession.mockClear();

      manager.setSelectedModelByName('DeepSeek');
      await nextTick();

      expect(mocks.mockSessionModule.updateSession).not.toHaveBeenCalled();
    });

    it('should expose selectedModelSupportsVision from property.support_vision', () => {
      const visionModels = [
        {
          id: 1,
          llm_code: 'vision-model',
          llm_name: 'Vision',
          llm_type: 'chat.completion',
          max_token_size: 32768,
          property: { support_vision: true },
          space_auth_mode: '',
          user_auth_mode: '',
        },
        {
          id: 2,
          llm_code: 'text-model',
          llm_name: 'Text',
          llm_type: 'chat.completion',
          max_token_size: 32768,
          property: { support_vision: false },
          space_auth_mode: '',
          user_auth_mode: '',
        },
      ];
      manager.setModels(visionModels as any);
      manager.setSelectedModelByName('Vision');
      expect(manager.selectedModelSupportsVision.value).toBe(true);

      manager.setSelectedModelByName('Text');
      expect(manager.selectedModelSupportsVision.value).toBe(false);
    });
  });
});
