import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

import { useShareHandlers } from '../use-share-handlers';

import type { ReportSdkErrorOptions } from '../../types';

vi.mock('bkui-vue', () => ({
  Message: vi.fn(),
}));

vi.mock('../../utils', async importOriginal => {
  const actual = await importOriginal<typeof import('../../utils')>();
  return {
    ...actual,
    copyToClipboard: vi.fn().mockResolvedValue(undefined),
  };
});

describe('useShareHandlers', () => {
  it('reports share failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const emit = vi.fn();
    const shareBusinessManager = {
      shareMessages: vi.fn().mockRejectedValue(new Error('share failed')),
    };

    const { handleConfirmShare } = useShareHandlers({
      chatBotRef: ref({
        exitShareMode: vi.fn(),
      }),
      emit,
      forwarders: {
        shareMessages: vi.fn(),
      },
      reportSdkError,
      shareBusinessManager: shareBusinessManager as never,
    });

    await handleConfirmShare([{ id: '1' }] as never);

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('share');
    expect(payload.action).toBe('confirmShare');
    expect(payload.source).toBe('business');
    expect(emit).not.toHaveBeenCalled();
  });

  it('skips ShareBusinessManager and emits confirm-share for custom source', async () => {
    const reportSdkError = vi.fn();
    const emit = vi.fn();
    const exitShareMode = vi.fn();
    const shareBusinessManager = {
      shareMessages: vi.fn(),
    };

    const { handleConfirmShare } = useShareHandlers({
      chatBotRef: ref({
        exitShareMode,
      }),
      emit,
      forwarders: {
        shareMessages: vi.fn(),
      },
      reportSdkError,
      shareBusinessManager: shareBusinessManager as never,
    });

    const messages = [{ id: '1' }] as never;
    const source = { id: 'save', triggerSelection: true } as never;
    await handleConfirmShare(messages, source);

    expect(shareBusinessManager.shareMessages).not.toHaveBeenCalled();
    expect(exitShareMode).toHaveBeenCalled();
    expect(emit).toHaveBeenCalledWith('confirm-share', messages, source);
  });

  it('runs share and emits confirm-share for builtin share source', async () => {
    const reportSdkError = vi.fn();
    const emit = vi.fn();
    const shareMessages = vi.fn();
    const exitShareMode = vi.fn();
    const shareBusinessManager = {
      shareMessages: vi.fn().mockResolvedValue({
        shareUrl: 'https://example.com/share',
        userMessageIds: ['1'],
      }),
    };

    const { handleConfirmShare } = useShareHandlers({
      chatBotRef: ref({
        exitShareMode,
      }),
      emit,
      forwarders: {
        shareMessages,
      },
      reportSdkError,
      shareBusinessManager: shareBusinessManager as never,
    });

    const messages = [{ id: '1' }] as never;
    await handleConfirmShare(messages, { id: 'share' } as never);

    expect(shareBusinessManager.shareMessages).toHaveBeenCalled();
    expect(shareMessages).toHaveBeenCalledWith(['1']);
    expect(emit).toHaveBeenCalledWith('confirm-share', messages, { id: 'share' });
  });
});
