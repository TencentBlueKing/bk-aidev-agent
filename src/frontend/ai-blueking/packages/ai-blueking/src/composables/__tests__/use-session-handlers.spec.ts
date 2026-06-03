import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

import { useSessionHandlers } from '../use-session-handlers';

import type { ReportSdkErrorOptions } from '../../types';

function createParams(reportSdkError = vi.fn()) {
  return {
    chatBotRef: ref(undefined),
    chatHelper: {
      message: { list: ref([]) },
      session: {
        current: ref({ sessionCode: 's-1', sessionName: 'old' }),
        list: ref([]),
        renameSession: vi.fn().mockRejectedValue(new Error('rename failed')),
        updateSession: vi.fn().mockRejectedValue(new Error('update failed')),
      },
    },
    currentSession: ref({ sessionCode: 's-1', sessionName: 'old' }),
    forwarders: {
      autoGenerateName: vi.fn(),
      rename: vi.fn(),
    },
    reportSdkError,
    sessionBusinessManager: {
      deleteSession: vi.fn().mockRejectedValue(new Error('delete failed')),
      switchSession: vi.fn().mockRejectedValue(new Error('switch failed')),
      updateSessionName: vi.fn().mockRejectedValue(new Error('update name failed')),
    },
  } as unknown as Parameters<typeof useSessionHandlers>[0];
}

describe('useSessionHandlers error reporting', () => {
  it('reports session rename failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const { handleRename } = useSessionHandlers(createParams(reportSdkError));

    await handleRename('new-name');

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('session');
    expect(payload.action).toBe('rename');
    expect(payload.source).toBe('business');
  });

  it('reports auto generate name failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const { handleAutoGenerateName } = useSessionHandlers(createParams(reportSdkError));

    await handleAutoGenerateName();

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('session');
    expect(payload.action).toBe('autoGenerateName');
  });

  it('reports updateSessionName failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const { updateSessionName } = useSessionHandlers(createParams(reportSdkError));

    await updateSessionName('s-1', 'new-name');

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('session');
    expect(payload.action).toBe('updateSessionName');
  });

  it('reports history session switch failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const { handleHistorySessionSwitch } = useSessionHandlers(createParams(reportSdkError));

    await handleHistorySessionSwitch('s-2');

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('session');
    expect(payload.action).toBe('historySwitch');
    expect(payload.source).toBe('business');
  });

  it('reports history session delete failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const { handleHistorySessionDelete } = useSessionHandlers(createParams(reportSdkError));

    await handleHistorySessionDelete('s-2');

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('session');
    expect(payload.action).toBe('historyDelete');
  });

  it('reports history session rename failure with semantic apiName', async () => {
    const reportSdkError = vi.fn();
    const { handleHistorySessionRename } = useSessionHandlers(createParams(reportSdkError));

    await handleHistorySessionRename('s-2', 'new-name');

    expect(reportSdkError).toHaveBeenCalledTimes(1);
    const payload = reportSdkError.mock.calls[0][0] as ReportSdkErrorOptions;
    expect(payload.apiName).toBe('session');
    expect(payload.action).toBe('historyRename');
  });
});
