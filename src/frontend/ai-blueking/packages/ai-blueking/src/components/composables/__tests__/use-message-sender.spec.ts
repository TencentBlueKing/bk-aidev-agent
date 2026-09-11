import { describe, it, expect, vi } from 'vitest';
import { nextTick, ref, shallowRef, computed } from 'vue';

import {
  createErrorReporterParams,
  createMockChatBusinessManager,
  createMockChatHelper,
  createMockEmit,
} from '../../../__tests__/helpers';

import { useMessageSender } from '../use-message-sender';
import type { UseMessageSenderParams } from '../use-message-sender';
import type { IRequestOptions } from '../../../types';

function createParams(overrides: Partial<UseMessageSenderParams> = {}): UseMessageSenderParams {
  const emit = overrides.emit ?? createMockEmit();
  return {
    emit,
    reportError: createErrorReporterParams(emit).reportError,
    chatHelper: shallowRef(createMockChatHelper()),
    chatBusinessManager: shallowRef(createMockChatBusinessManager()),
    selectedShortcut: ref(null),
    ...overrides,
  };
}

describe('useMessageSender', () => {
  describe('doSendMessage', () => {
    it('should clear input and cite after sending', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage, userInput, cite } = useMessageSender(params);

      userInput.value = 'hello';
      cite.value = 'some cite';

      await doSendMessage('hello');

      expect(userInput.value).toEqual([[]]);
      expect(cite.value).toBe('');
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
    it('should write docSchema at property top-level with cite/command, without extra.resources', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      params.selectedShortcut = ref({ id: 'cmd-1' }) as any;

      const sender = useMessageSender(params);
      sender.cite.value = 'cited text';

      const docSchema = [
        [
          { type: 'text', text: '分析 ' },
          {
            type: 'tag',
            data: { type: 'knowledgebase', label: '运维知识库', value: '58', icon: '', description: '' },
          },
        ],
      ];

      await sender.handleSendMessage('分析 @运维知识库', docSchema as any);

      expect(params.chatBusinessManager.value!.sendMessage).toHaveBeenCalledWith('分析 @运维知识库', 'session-1', {
        property: {
          extra: {
            cite: 'cited text',
            command: 'cmd-1',
          },
          docSchema,
        },
      });
      const sent = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sent.property.extra.resources).toBeUndefined();
    });

    it('should send plain text without property when there is no tag', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };

      const sender = useMessageSender(params);
      await sender.handleSendMessage('普通文本', [[{ type: 'text', text: '普通文本' }]] as any);

      expect(params.chatBusinessManager.value!.sendMessage).toHaveBeenCalledWith('普通文本', 'session-1', {});
    });

    it('should emit error on failure', async () => {
      const params = createParams({ chatHelper: shallowRef(null), chatBusinessManager: shallowRef(null) });
      const { handleSendMessage } = useMessageSender(params);

      await handleSendMessage('test', [] as any);

      expect(params.emit).toHaveBeenCalledWith('error', expect.any(Error));
    });

    it('should pass artifact tags injected by chat-x through without re-deriving them', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const sender = useMessageSender(params);

      const artifactTag = {
        type: 'tag',
        data: {
          type: 'artifact',
          label: 'bk_apigw_resources_bp-aidev-develop (7).yaml',
          value: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml',
          icon: '',
          description: '',
        },
      };
      const content = [
        {
          type: 'binary',
          id: 'upload-id',
          outputId: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml',
          filename: 'bk_apigw_resources_bp-aidev-develop (7).yaml',
          mimeType: 'application/x-yaml',
        },
        { type: 'text', text: '分析这个文件' },
      ];
      const docSchema = [[{ type: 'text', text: '分析这个文件' }], [artifactTag]];

      await sender.handleSendMessage(content as any, docSchema as any);

      const sent = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sent.property.docSchema).toEqual(docSchema);
    });

    it('存在 ask-user-question options 时应走 resumeUserQuestionWithInput', async () => {
      const resumeUserQuestionWithInput = vi.fn().mockResolvedValue(undefined);
      const params = createParams({ resumeUserQuestionWithInput });
      const sender = useMessageSender(params);
      sender.cite.value = 'cited text';
      sender.userInput.value = '保留输入';

      const options = {
        payload: {
          interruptId: 'interrupt-1',
          reason: 'user_question',
          status: 'cancelled',
          payload: { answers: [] },
        },
      };

      await sender.handleSendMessage('自由文本', [] as any, options as any);

      expect(resumeUserQuestionWithInput).toHaveBeenCalledWith('自由文本', options);
      expect(sender.userInput.value).toEqual([[]]);
      expect(sender.cite.value).toBe('');
      expect(params.chatBusinessManager.value!.sendMessage).not.toHaveBeenCalled();
    });
  });

  describe('handleUpload', () => {
    it('should call session.uploadFiles once and return results', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const fileA = new File(['a'], 'a.png');
      const fileB = new File(['b'], 'b.png');
      (params.chatHelper.value!.session.uploadFiles as any).mockResolvedValue([
        { download_url: 'https://example.com/a.png' },
        { download_url: 'https://example.com/b.png' },
      ]);
      const { handleUpload } = useMessageSender(params);

      const result = await handleUpload([fileA, fileB]);

      expect(params.chatHelper.value!.session.uploadFiles).toHaveBeenCalledTimes(1);
      expect(params.chatHelper.value!.session.uploadFiles).toHaveBeenCalledWith('session-1', [fileA, fileB]);
      expect(params.chatHelper.value!.session.uploadFile).not.toHaveBeenCalled();
      expect(result).toEqual([
        { download_url: 'https://example.com/a.png' },
        { download_url: 'https://example.com/b.png' },
      ]);
    });

    it('should accept pv_files success without download_url', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      (params.chatHelper.value!.session.uploadFiles as any).mockResolvedValue([
        {
          type: 'file',
          id: 'files/doc.pdf',
          path: 'files/doc.pdf',
          name: 'doc.pdf',
          mime_type: 'application/pdf',
          size: 10,
          status: 'success',
        },
      ]);
      const { handleUpload } = useMessageSender(params);

      const result = await handleUpload([new File(['pdf'], 'doc.pdf')]);

      expect(result).toEqual([
        expect.objectContaining({ id: 'files/doc.pdf', status: 'success' }),
      ]);
    });

    it('should return failed items without aborting the batch', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      (params.chatHelper.value!.session.uploadFiles as any).mockResolvedValue([
        {
          type: 'file',
          id: 'files/ok.pdf',
          path: 'files/ok.pdf',
          name: 'ok.pdf',
          mime_type: 'application/pdf',
          size: 2,
          status: 'success',
        },
        {
          type: 'file',
          id: 'files/bad.exe',
          path: 'files/bad.exe',
          name: 'bad.exe',
          mime_type: 'application/octet-stream',
          size: 1,
          status: 'failed',
          error: 'extension not allowed',
        },
      ]);
      const { handleUpload } = useMessageSender(params);

      const result = await handleUpload([new File(['ok'], 'ok.pdf'), new File(['x'], 'bad.exe')]);

      expect(result[0]).toMatchObject({ status: 'success' });
      expect(result[1]).toMatchObject({ status: 'failed', error: 'extension not allowed' });
    });

    it('should throw when no active session', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = null;
      const { handleUpload } = useMessageSender(params);

      const file = new File(['content'], 'test.png');
      await expect(handleUpload([file])).rejects.toThrow('no active session');
    });
  });

  describe('handleArtifactClick', () => {
    it('should call session.getPvFileDownloadUrl and return download_url/preview_url', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { handleArtifactClick } = useMessageSender(params);

      const file = {
        name: 'report.pdf',
        outputId: 'outputs/report.pdf',
        size: 1024,
        type: 'pdf',
      };
      const result = await handleArtifactClick(file as any);

      expect(params.chatHelper.value!.session.getPvFileDownloadUrl).toHaveBeenCalledWith(
        'session-1',
        'outputs/report.pdf',
      );
      expect(result).toEqual({
        download_url: 'https://example.com/download',
        preview_url: 'https://example.com/preview',
      });
    });

    it('should throw when no active session', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = null;
      const { handleArtifactClick } = useMessageSender(params);

      await expect(
        handleArtifactClick({
          name: 'report.pdf',
          outputId: 'outputs/report.pdf',
          size: 1024,
          type: 'pdf',
        } as any),
      ).rejects.toThrow('no active session');
    });
  });

  describe('handleUpdateModelValue', () => {
    it('should update userInput and ignore the selected resource list', () => {
      const params = createParams();
      const { handleUpdateModelValue, userInput } = useMessageSender(params);

      handleUpdateModelValue('new input');

      expect(userInput.value).toBe('new input');
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

    it('should emit error instead of stop when the stop request fails', async () => {
      const params = createParams();
      const failure = new Error('stop failed');
      (params.chatBusinessManager.value!.stopGeneration as any).mockRejectedValue(failure);
      const { stopGeneration } = useMessageSender(params);

      await stopGeneration();

      expect(params.emit).toHaveBeenCalledWith('error', failure);
      expect(params.emit).not.toHaveBeenCalledWith('stop');
    });

    it('should wrap non-Error rejections into an Error', async () => {
      const params = createParams();
      (params.chatBusinessManager.value!.stopGeneration as any).mockRejectedValue('boom');
      const { stopGeneration } = useMessageSender(params);

      await stopGeneration();

      expect(params.emit).toHaveBeenCalledWith('error', expect.any(Error));
    });
  });

  describe('context merging', () => {
    it('should merge requestOptions.context into property', async () => {
      const params = createParams({
        getRequestOptions: () => ({ context: { env: 'prod', region: 'ap-guangzhou' } }),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      await doSendMessage('hello', { property: { extra: { command: 'cmd-1' } } });

      const sentOptions = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sentOptions.property.extra.command).toBe('cmd-1');
      expect(sentOptions.property.extra.context).toHaveLength(2);
      expect(sentOptions.property.extra.context[0]).toMatchObject({
        env: 'prod',
        context_type: 'input',
        __key: 'env',
        __value: 'prod',
      });
      expect(sentOptions.property.extra.context[1]).toMatchObject({
        region: 'ap-guangzhou',
        context_type: 'input',
        __key: 'region',
        __value: 'ap-guangzhou',
      });
    });

    it('should merge context with existing shortcut context', async () => {
      const params = createParams({
        getRequestOptions: () => ({ context: { env: 'prod' } }),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      const shortcutContext = [
        { input: 'hello', context_type: 'textarea', __label: 'Input', __key: 'input', __value: 'hello' },
      ];
      await doSendMessage('hello', { property: { extra: { context: shortcutContext } } });

      const sentOptions = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sentOptions.property.extra.context).toHaveLength(2);
      expect(sentOptions.property.extra.context[0]).toMatchObject({ __key: 'input' });
      expect(sentOptions.property.extra.context[1]).toMatchObject({ __key: 'env' });
    });

    it('should override shortcut context entries with same __key', async () => {
      const params = createParams({
        getRequestOptions: () => ({ context: { input: 'new value' } }),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      const shortcutContext = [
        { input: 'old value', context_type: 'textarea', __label: 'Input', __key: 'input', __value: 'old value' },
      ];
      await doSendMessage('hello', { property: { extra: { context: shortcutContext } } });

      const sentOptions = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sentOptions.property.extra.context).toHaveLength(1);
      expect(sentOptions.property.extra.context[0]).toMatchObject({ __key: 'input', input: 'new value' });
    });

    it('should support dynamic context via getter function', async () => {
      const contextValue = ref('prod');
      const params = createParams({
        getRequestOptions: () => ({ context: { env: contextValue.value } }),
      });
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      await doSendMessage('hello');
      const sentOptions1 = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sentOptions1.property.extra.context[0]).toMatchObject({ env: 'prod' });

      contextValue.value = 'staging';
      await doSendMessage('hello again');
      const sentOptions2 = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[1][2];
      expect(sentOptions2.property.extra.context[0]).toMatchObject({ env: 'staging' });
    });

    it('should not modify property when getRequestOptions is not provided', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { doSendMessage } = useMessageSender(params);

      await doSendMessage('hello', { property: { extra: { command: 'cmd-1' } } });

      const sentOptions = (params.chatBusinessManager.value!.sendMessage as any).mock.calls[0][2];
      expect(sentOptions.property.extra.command).toBe('cmd-1');
      expect(sentOptions.property.extra.context).toBeUndefined();
    });
  });

  describe('session change', () => {
    it('should clear cite when the current session changes', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { cite } = useMessageSender(params);

      cite.value = '引用内容';
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-2' };
      await nextTick();

      expect(cite.value).toBe('');
    });

    it('should keep cite when the current session stays the same', async () => {
      const params = createParams();
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1' };
      const { cite } = useMessageSender(params);

      cite.value = '引用内容';
      (params.chatHelper.value!.session.current as any).value = { sessionCode: 'session-1', sessionName: 'renamed' };
      await nextTick();

      expect(cite.value).toBe('引用内容');
    });
  });
});
