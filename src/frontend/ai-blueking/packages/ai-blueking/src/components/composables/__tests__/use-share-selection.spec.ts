import { ref, shallowRef } from 'vue';

import { describe, it, expect, vi } from 'vitest';

import { createMockChatHelper, createMockEmit, createMockAIMessage } from '../../../__tests__/helpers';

vi.mock('bkui-vue', () => ({
  Message: vi.fn(),
}));

vi.mock('../../../manager/business/share-business-manager', () => ({
  ShareBusinessManager: vi.fn().mockImplementation(() => ({
    shareMessages: vi.fn().mockResolvedValue({
      shareUrl: 'https://example.com/share',
      userMessageIds: ['1'],
    }),
  })),
}));

vi.mock('../../../utils', () => ({
  copyToClipboard: vi.fn().mockResolvedValue(true),
}));

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
  describe('handleConfirmShare', () => {
    it('should call ShareBusinessManager.shareMessages in standalone mode', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      await handleConfirmShare(messages);

      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages);
    });

    it('should only emit confirm-share in integration mode', async () => {
      const params = createParams({ isStandaloneMode: ref(false) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      await handleConfirmShare(messages);

      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages);
    });

    it('should not call ShareBusinessManager when chatHelper is null', async () => {
      const params = createParams({ isStandaloneMode: ref(true), chatHelper: shallowRef(null) });
      const { handleConfirmShare } = useShareSelection(params);

      await handleConfirmShare([createMockAIMessage()] as any);

      expect(params.emit).toHaveBeenCalledWith('confirm-share', expect.any(Array));
    });
  });
});
