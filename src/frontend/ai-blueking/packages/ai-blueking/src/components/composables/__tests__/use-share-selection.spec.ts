import { ref, shallowRef } from 'vue';

import { describe, it, expect, vi, beforeEach } from 'vitest';

import { createMockChatHelper, createMockEmit, createMockAIMessage } from '../../../__tests__/helpers';

vi.mock('bkui-vue', () => ({
  Message: vi.fn(),
}));

const shareMessagesMock = vi.fn().mockResolvedValue({
  shareUrl: 'https://example.com/share',
  userMessageIds: ['1'],
});

vi.mock('../../../manager/business/share-business-manager', () => ({
  ShareBusinessManager: vi.fn().mockImplementation(() => ({
    shareMessages: shareMessagesMock,
  })),
}));

vi.mock('../../../utils', () => ({
  copyToClipboard: vi.fn().mockResolvedValue(true),
}));

import { ShareBusinessManager } from '../../../manager/business/share-business-manager';
import { useShareSelection } from '../use-share-selection';
import type { UseShareSelectionParams } from '../use-share-selection';

function createParams(overrides: Partial<UseShareSelectionParams> = {}): UseShareSelectionParams {
  return {
    emit: createMockEmit(),
    chatHelper: shallowRef(createMockChatHelper()),
    isStandaloneMode: ref(true),
    ...overrides,
  };
}

describe('useShareSelection', () => {
  beforeEach(() => {
    shareMessagesMock.mockClear();
    vi.mocked(ShareBusinessManager).mockClear();
  });

  describe('handleConfirmShare', () => {
    it('should call ShareBusinessManager.shareMessages in standalone mode for builtin share', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      await handleConfirmShare(messages);

      expect(ShareBusinessManager).toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, undefined);
    });

    it('should call ShareBusinessManager when source.id is share', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      const source = { id: 'share' };
      await handleConfirmShare(messages, source as any);

      expect(ShareBusinessManager).toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, source);
    });

    it('should not call ShareBusinessManager for custom triggerSelection source', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      const source = { id: 'save', triggerSelection: true };
      await handleConfirmShare(messages, source as any);

      expect(ShareBusinessManager).not.toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, source);
    });

    it('should only emit confirm-share in integration mode', async () => {
      const params = createParams({ isStandaloneMode: ref(false) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      await handleConfirmShare(messages);

      expect(ShareBusinessManager).not.toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, undefined);
    });

    it('should not call ShareBusinessManager when chatHelper is null', async () => {
      const params = createParams({ isStandaloneMode: ref(true), chatHelper: shallowRef(null) });
      const { handleConfirmShare } = useShareSelection(params);

      await handleConfirmShare([createMockAIMessage()] as any);

      expect(params.emit).toHaveBeenCalledWith('confirm-share', expect.any(Array), undefined);
    });
  });
});
