import { describe, it, expect, vi } from 'vitest';
import { ref, shallowRef } from 'vue';

import {
  createErrorReporterParams,
  createMockChatHelper,
  createMockChatBusinessManager,
  createMockEmit,
  createMockUserMessage,
  createMockAIMessage,
  createMockShortcut,
} from '../../../__tests__/helpers';

vi.mock('@blueking/chat-x', () => ({
  MessageRole: { User: 'user', Reasoning: 'reasoning' },
}));

vi.mock('../../../utils', async importOriginal => {
  const actual = await importOriginal<typeof import('../../../utils')>();
  return {
    ...actual,
    findLastUserMessageBefore: vi.fn((messages: any[], aiMessage: any) => {
      const idx = messages.indexOf(aiMessage);
      for (let i = idx - 1; i >= 0; i--) {
        if (messages[i].role === 'user') return messages[i];
      }
      return null;
    }),
    findLastUserMessageIdBefore: vi.fn((messages: any[], aiMessage: any) => {
      const idx = messages.indexOf(aiMessage);
      for (let i = idx - 1; i >= 0; i--) {
        if (messages[i].role === 'user') return messages[i].id;
      }
      return undefined;
    }),
    applyRequestOptionsContext: vi.fn((property: any, getRequestOptions?: () => any) => {
      if (!getRequestOptions) return property;
      const opts = getRequestOptions();
      if (!opts?.context) return property;
      return { ...(property ?? {}), extra: { ...((property ?? {}).extra ?? {}), context: opts.context } };
    }),
    resolveContextEntries: vi.fn(() => []),
  };
});

import { useToolActions } from '../use-tool-actions';
import type { UseToolActionsParams } from '../use-tool-actions';

function createParams(overrides: Partial<UseToolActionsParams> = {}): UseToolActionsParams {
  const emit = overrides.emit ?? createMockEmit();
  return {
    emit,
    reportError: createErrorReporterParams(emit).reportError,
    chatHelper: shallowRef(createMockChatHelper()),
    chatBusinessManager: shallowRef(createMockChatBusinessManager()),
    cite: ref(''),
    focusInput: vi.fn(),
    getShortcutFromMessage: vi.fn().mockReturnValue(null),
    buildShortcutProperty: vi.fn().mockReturnValue({ extra: {} }),
    stopGeneration: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe('useToolActions', () => {
  describe('handleAgentAction', () => {
    it('should set cite and call focusInput for cite action', async () => {
      const params = createParams();
      const { handleAgentAction } = useToolActions(params);

      const messages = [createMockAIMessage({ content: 'Hello', role: 'assistant' })] as any;

      await handleAgentAction({ id: 'cite' } as any, messages);

      expect(params.cite.value).toBe('Hello');
      expect(params.focusInput).toHaveBeenCalled();
    });

    it('should filter out reasoning messages for cite', async () => {
      const params = createParams();
      const { handleAgentAction } = useToolActions(params);

      const messages = [
        { id: 1, role: 'reasoning', content: 'thinking...' },
        { id: 2, role: 'assistant', content: 'Answer' },
      ] as any;

      await handleAgentAction({ id: 'cite' } as any, messages);

      expect(params.cite.value).toBe('Answer');
    });

    it('should call regenerateFromAIMessages for rebuild action', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { handleAgentAction } = useToolActions(params);

      const messages = [createMockAIMessage()] as any;
      await handleAgentAction({ id: 'rebuild' } as any, messages);

      expect(params.chatBusinessManager.value!.regenerateFromAIMessages).toHaveBeenCalledWith(messages, 'session-1');
    });

    it('should call deleteMessages for delete action', async () => {
      const params = createParams();
      const userMsg = createMockUserMessage();
      const aiMsg = createMockAIMessage();
      (params.chatBusinessManager.value!.messages as any).value = [userMsg, aiMsg];

      const { handleAgentAction } = useToolActions(params);
      await handleAgentAction({ id: 'delete' } as any, [aiMsg] as any);

      expect(params.chatHelper.value!.message.deleteMessages).toHaveBeenCalledWith(
        expect.arrayContaining([userMsg, aiMsg]),
      );
    });

    it('should call getSessionFeedbackReasons for like action', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.getSessionFeedbackReasons as any).mockResolvedValue(['reason1']);
      const { handleAgentAction } = useToolActions(params);

      const result = await handleAgentAction({ id: 'like' } as any, [] as any);

      expect(params.chatHelper.value!.session.getSessionFeedbackReasons).toHaveBeenCalledWith(5);
      expect(result).toEqual(['reason1']);
    });

    it('should call getSessionFeedbackReasons for unlike action with rate 0', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.getSessionFeedbackReasons as any).mockResolvedValue(['bad']);
      const { handleAgentAction } = useToolActions(params);

      const result = await handleAgentAction({ id: 'unlike' } as any, [] as any);

      expect(params.chatHelper.value!.session.getSessionFeedbackReasons).toHaveBeenCalledWith(0);
      expect(result).toEqual(['bad']);
    });

    it('should emit agent-action for custom tool ids', async () => {
      const params = createParams();
      const { handleAgentAction } = useToolActions(params);

      const messages = [createMockAIMessage()] as any;
      const tool = { id: 'collect', name: '收藏' };
      await handleAgentAction(tool as any, messages);

      expect(params.emit).toHaveBeenCalledWith('agent-action', tool, messages);
    });
  });

  describe('handleAgentFeedback', () => {
    it('should call postSessionFeedback and emit feedback', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const userMsg = createMockUserMessage({ id: 'u1' });
      const aiMsg = createMockAIMessage({ id: 'a1' });
      (params.chatBusinessManager.value!.messages as any).value = [userMsg, aiMsg];

      const { handleAgentFeedback } = useToolActions(params);

      await handleAgentFeedback({ id: 'like' } as any, [aiMsg] as any, ['helpful'], 'great answer');

      expect(params.chatHelper.value!.session.postSessionFeedback).toHaveBeenCalledWith({
        sessionCode: 'session-1',
        sessionContentIds: ['u1'],
        rate: 5,
        labels: ['helpful'],
        comment: 'great answer',
      });
      expect(params.emit).toHaveBeenCalledWith('feedback', { id: 'like' }, aiMsg, ['helpful'], 'great answer');
    });

    it('should not call postSessionFeedback when chatHelper is null', async () => {
      const params = createParams({ chatHelper: shallowRef(null) });
      const { handleAgentFeedback } = useToolActions(params);

      await handleAgentFeedback({ id: 'like' } as any, [] as any, [], '');
      // Should just log error and return
    });

    it('should not call postSessionFeedback when no session', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = null;
      const { handleAgentFeedback } = useToolActions(params);

      await handleAgentFeedback({ id: 'like' } as any, [] as any, [], '');
      expect(params.chatHelper.value!.session.postSessionFeedback).not.toHaveBeenCalled();
    });
  });

  describe('handleUserAction', () => {
    it('should delete user message and following AI messages', async () => {
      const params = createParams();
      const userMsg = createMockUserMessage({ id: 'u1' });
      const aiMsg1 = createMockAIMessage({ id: 'a1' });
      const aiMsg2 = createMockAIMessage({ id: 'a2' });
      (params.chatBusinessManager.value!.messages as any).value = [userMsg, aiMsg1, aiMsg2];

      const { handleUserAction } = useToolActions(params);
      await handleUserAction({ id: 'delete' } as any, userMsg as any);

      expect(params.chatHelper.value!.message.deleteMessages).toHaveBeenCalledWith([userMsg, aiMsg1, aiMsg2]);
    });

    it('should set cite and focusInput for cite action', async () => {
      const params = createParams();
      const { handleUserAction } = useToolActions(params);

      const message = createMockUserMessage({ content: 'my question' });
      await handleUserAction({ id: 'cite' } as any, message as any);

      expect(params.cite.value).toBe('my question');
      expect(params.focusInput).toHaveBeenCalled();
    });
  });

  describe('handleUserInputConfirm', () => {
    it('should call resendMessageWithProperty with correct params', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };

      const { handleUserInputConfirm } = useToolActions(params);

      const message = createMockUserMessage({ id: 'msg-1' });
      await handleUserInputConfirm(message as any, 'new content', [] as any);

      expect(params.chatBusinessManager.value!.resendMessageWithProperty).toHaveBeenCalledWith(
        'msg-1',
        'session-1',
        'new content',
        undefined,
      );
    });

    it('should not call resendMessage when no chatHelper', async () => {
      const params = createParams({ chatHelper: shallowRef(null) });
      const { handleUserInputConfirm } = useToolActions(params);

      const message = createMockUserMessage({ id: 'msg-1' });
      await handleUserInputConfirm(message as any, 'content', [] as any);
      // Should just log error and return
    });
  });

  describe('handleUserShortcutConfirm', () => {
    it('should get shortcut and call resendMessageWithProperty', async () => {
      const shortcut = createMockShortcut();
      const property = { extra: { command: 'cmd-1' } };
      const params = createParams({
        getShortcutFromMessage: vi.fn().mockReturnValue(shortcut),
        buildShortcutProperty: vi.fn().mockReturnValue(property),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };

      const { handleUserShortcutConfirm } = useToolActions(params);

      const message = createMockUserMessage({ id: 'msg-1' });
      const formModel = { input: 'new value' };
      await handleUserShortcutConfirm(message as any, formModel);

      expect(params.getShortcutFromMessage).toHaveBeenCalledWith(message);
      expect(params.buildShortcutProperty).toHaveBeenCalledWith(shortcut, formModel);
      expect(params.chatBusinessManager.value!.resendMessageWithProperty).toHaveBeenCalledWith(
        'msg-1',
        'session-1',
        'new value',
        property,
      );
    });

    it('should not proceed when shortcut is not found', async () => {
      const params = createParams({
        getShortcutFromMessage: vi.fn().mockReturnValue(null),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };

      const { handleUserShortcutConfirm } = useToolActions(params);

      const message = createMockUserMessage({ id: 'msg-1' });
      await handleUserShortcutConfirm(message as any, {});

      expect(params.chatBusinessManager.value!.resendMessageWithProperty).not.toHaveBeenCalled();
    });

    it('should merge requestOptions.context into shortcut property', async () => {
      const { applyRequestOptionsContext } = await import('../../../utils');
      const shortcut = createMockShortcut();
      const property = { extra: { command: 'cmd-1', context: [{ input: 'hello', __key: 'input' }] } };

      (applyRequestOptionsContext as any).mockReturnValue({
        extra: { command: 'cmd-1', context: [{ input: 'hello', __key: 'input' }, { env: 'prod', __key: 'env' }] },
      });

      const params = createParams({
        getShortcutFromMessage: vi.fn().mockReturnValue(shortcut),
        buildShortcutProperty: vi.fn().mockReturnValue(property),
        getRequestOptions: () => ({ context: { env: 'prod' } }),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };

      const { handleUserShortcutConfirm } = useToolActions(params);

      const message = createMockUserMessage({ id: 'msg-1' });
      await handleUserShortcutConfirm(message as any, { input: 'new value' });

      expect(applyRequestOptionsContext).toHaveBeenCalledWith(property, expect.any(Function));
      expect(params.chatBusinessManager.value!.resendMessageWithProperty).toHaveBeenCalledWith(
        'msg-1',
        'session-1',
        'new value',
        expect.objectContaining({
          extra: expect.objectContaining({
            command: 'cmd-1',
            context: expect.arrayContaining([
              expect.objectContaining({ __key: 'input' }),
              expect.objectContaining({ __key: 'env' }),
            ]),
          }),
        }),
      );
    });
  });

  describe('handleStopStreaming', () => {
    it('should delegate to the shared stopGeneration entry', async () => {
      const params = createParams();
      const { handleStopStreaming } = useToolActions(params);

      await handleStopStreaming();

      expect(params.stopGeneration).toHaveBeenCalled();
    });
  });
});
