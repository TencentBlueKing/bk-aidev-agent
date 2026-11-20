import { shallowRef } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import {
  createErrorReporterParams,
  createMockChatHelper,
  createMockEmit,
  createMockSessionBusinessManager,
} from '../../../__tests__/helpers';
import { useForkSession } from '../use-fork-session';

import type { UseForkSessionParams } from '../use-fork-session';
import type { Message, MessageForkInfo } from '@blueking/chat-x';

function createParams(overrides: Partial<UseForkSessionParams> = {}): UseForkSessionParams {
  const emit = overrides.emit ?? createMockEmit();
  return {
    emit,
    reportError: createErrorReporterParams(emit).reportError,
    chatHelper: shallowRef(createMockChatHelper()),
    sessionBusinessManager: shallowRef(createMockSessionBusinessManager()),
    exitShareMode: vi.fn(),
    clearCite: vi.fn(),
    ...overrides,
  };
}

describe('useForkSession', () => {
  it('forks from the persisted content id and emits session-switched', async () => {
    const params = createParams();
    const forked = { sessionCode: 'e5f6a7b8', sessionName: '排查发布失败(1)' };
    (params.sessionBusinessManager.value!.forkSession as ReturnType<typeof vi.fn>).mockResolvedValue(forked);
    (params.sessionBusinessManager.value!.getForkContentId as ReturnType<typeof vi.fn>).mockResolvedValue(1052);
    params.sessionBusinessManager.value!.currentSession.value = forked;
    const { forkFromMessages } = useForkSession(params);
    const messages = [{ messageId: 'stream-1', role: 'assistant' }] as unknown as Message[];

    await forkFromMessages(messages);

    expect(params.sessionBusinessManager.value!.getForkContentId).toHaveBeenCalledWith(messages);
    expect(params.exitShareMode).toHaveBeenCalled();
    expect(params.clearCite).toHaveBeenCalled();
    expect(params.sessionBusinessManager.value!.forkSession).toHaveBeenCalledWith(1052);
    expect(params.emit).toHaveBeenCalledWith('session-switched', forked);
  });

  it('does not fork when no persisted content id can be resolved', async () => {
    const params = createParams();
    const { forkFromMessages } = useForkSession(params);

    await forkFromMessages([{ id: 'assistant-tmp', role: 'assistant' }] as Message[]);

    expect(params.sessionBusinessManager.value!.forkSession).not.toHaveBeenCalled();
    expect(params.exitShareMode).not.toHaveBeenCalled();
    expect(params.emit).not.toHaveBeenCalled();
  });

  it('reports an error when resolving the content id fails', async () => {
    const params = createParams();
    (params.sessionBusinessManager.value!.getForkContentId as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('network'),
    );
    const { forkFromMessages } = useForkSession(params);

    await forkFromMessages([{ role: 'assistant' }] as Message[]);

    expect(params.sessionBusinessManager.value!.forkSession).not.toHaveBeenCalled();
    expect(params.emit).toHaveBeenCalledWith('error', expect.any(Error));
  });

  it('opens the source session and emits session-switched', async () => {
    const params = createParams();
    const source = { sessionCode: 'a1b2c3d4', sessionName: '排查发布失败' };
    params.sessionBusinessManager.value!.currentSession.value = source;
    const { handleForkSourceClick } = useForkSession(params);
    const forkInfo: MessageForkInfo = {
      source_session_code: 'a1b2c3d4',
      source_content_id: 1052,
    };

    await handleForkSourceClick(forkInfo);

    expect(params.sessionBusinessManager.value!.openForkSource).toHaveBeenCalledWith('a1b2c3d4');
    expect(params.emit).toHaveBeenCalledWith('session-switched', source);
  });
});
