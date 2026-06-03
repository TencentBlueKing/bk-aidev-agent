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

describe('useShareHandlers error reporting', () => {
  it('reports share failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const shareBusinessManager = {
      shareMessages: vi.fn().mockRejectedValue(new Error('share failed')),
    };

    const { handleConfirmShare } = useShareHandlers({
      chatBotRef: ref({
        exitShareMode: vi.fn(),
      }),
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
  });
});
