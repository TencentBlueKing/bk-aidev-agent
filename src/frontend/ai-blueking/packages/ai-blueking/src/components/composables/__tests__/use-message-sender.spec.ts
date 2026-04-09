import { describe, it, expect } from 'vitest';
import { ref, shallowRef } from 'vue';

import { createMockChatHelper, createMockChatBusinessManager, createMockEmit } from '../../../__tests__/helpers';

import { useMessageSender } from '../use-message-sender';
import type { UseMessageSenderParams } from '../use-message-sender';

function createParams(overrides: Partial<UseMessageSenderParams> = {}): UseMessageSenderParams {
  return {
    emit: createMockEmit(),
    chatHelper: shallowRef(createMockChatHelper()),
    chatBusinessManager: shallowRef(createMockChatBusinessManager()),
    selectedShortcut: ref(null),
    selectedResources: shallowRef([]),
    ...overrides,
  };
}

describe('useMessageSender', () => {
  describe('doSendMessage', () => {
    it('should clear input, cite, and resources after sending', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage, userInput, cite } = useMessageSender(params);

      userInput.value = 'hello';
      cite.value = 'some cite';
      params.selectedResources.value = [{ id: 'r1' }] as any;

      await doSendMessage('hello');

      expect(userInput.value).toEqual([[]]);
      expect(cite.value).toBe('');
      expect(params.selectedResources.value).toEqual([]);
    });

    it('should emit send-message event', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      await doSendMessage('hello');

      expect(params.emit).toHaveBeenCalledWith('send-message', 'hello');
    });

    it('should call chatBusinessManager.sendMessage', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      await doSendMessage('hello', { property: { extra: { cite: 'test' } } });

      expect(params.chatBusinessManager.value!.sendMessage).toHaveBeenCalledWith('hello', 'session-1', {
        property: { extra: { cite: 'test' } },
      });
    });

    it('should throw when chatHelper is null', async () => {
      const params = createParams({ chatHelper: shallowRef(null) });
      const { doSendMessage } = useMessageSender(params);

      await expect(doSendMessage('hello')).rejects.toThrow('chatBusinessManager not initialized');
    });

    it('should throw when no active session', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = null;
      const { doSendMessage } = useMessageSender(params);

      await expect(doSendMessage('hello')).rejects.toThrow('no active session');
    });
  });

  describe('handleSendMessage', () => {
    it('should build extra with cite, command, and resources', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      params.selectedShortcut = ref({ id: 'cmd-1' }) as any;
      params.selectedResources = shallowRef([{ id: 'r1', label: 'Resource 1' }]) as any;

      const sender = useMessageSender(params);
      sender.cite.value = 'cited text';

      await sender.handleSendMessage('test message', [] as any);

      expect(params.chatBusinessManager.value!.sendMessage).toHaveBeenCalledWith('test message', 'session-1', {
        property: {
          extra: {
            cite: 'cited text',
            command: 'cmd-1',
            resources: [{ id: 'r1', label: 'Resource 1' }],
          },
        },
      });
    });

    it('should emit error on failure', async () => {
      const params = createParams({ chatHelper: shallowRef(null), chatBusinessManager: shallowRef(null) });
      const { handleSendMessage } = useMessageSender(params);

      await handleSendMessage('test', [] as any);

      expect(params.emit).toHaveBeenCalledWith('error', expect.any(Error));
    });
  });

  describe('handleUpload', () => {
    it('should call session.uploadFile and return result', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { handleUpload } = useMessageSender(params);

      const file = new File(['content'], 'test.png');
      const result = await handleUpload(file);

      expect(params.chatHelper.value!.session.uploadFile).toHaveBeenCalledWith('session-1', file);
      expect(result).toEqual({ download_url: 'https://example.com/file.png' });
    });

    it('should throw when no active session', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = null;
      const { handleUpload } = useMessageSender(params);

      const file = new File(['content'], 'test.png');
      await expect(handleUpload(file)).rejects.toThrow('no active session');
    });
  });

  describe('handleUpdateModelValue', () => {
    it('should update userInput and selectedResources', () => {
      const params = createParams();
      const { handleUpdateModelValue, userInput } = useMessageSender(params);

      const resources = [{ id: 'r1', label: 'R1' }] as any;
      handleUpdateModelValue('new input', resources);

      expect(userInput.value).toBe('new input');
      expect(params.selectedResources.value).toEqual(resources);
    });
  });

  describe('stopGeneration', () => {
    it('should call chatBusinessManager.stopGeneration and emit stop', async () => {
      const params = createParams();
      const { stopGeneration } = useMessageSender(params);

      await stopGeneration();

      expect(params.chatBusinessManager.value!.stopGeneration).toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('stop');
    });

    it('should not throw when chatBusinessManager is null', async () => {
      const params = createParams({ chatBusinessManager: shallowRef(null) });
      const { stopGeneration } = useMessageSender(params);

      await expect(stopGeneration()).resolves.toBeUndefined();
    });
  });
});
