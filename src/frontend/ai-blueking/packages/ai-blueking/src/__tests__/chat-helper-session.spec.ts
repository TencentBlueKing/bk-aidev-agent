import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

import { useSession } from '@blueking/chat-helper';

import type { IMediatorModule, ISession } from '@blueking/chat-helper';

function createMediator() {
  const createdSession: ISession = {
    sessionCode: 'new_session_1781160451977',
    sessionContentCount: 0,
    sessionName: '新会话',
  };

  const mediator = {
    agent: {
      abortChat: vi.fn(),
      resumeStreamingChat: vi.fn(),
      pollResumeSession: vi.fn(),
    },
    http: {
      session: {
        plusSession: vi.fn().mockResolvedValue(createdSession),
        getSession: vi.fn().mockResolvedValue(createdSession),
      },
    },
    message: {
      getMessages: vi.fn().mockResolvedValue([]),
      list: ref([]),
    },
    session: null,
    registerAgent: vi.fn(),
    registerHttp: vi.fn(),
    registerMessage: vi.fn(),
    registerSession: vi.fn(),
  };

  return {
    createdSession,
    mediator: mediator as unknown as IMediatorModule,
    sessionHttp: mediator.http.session,
    messageModule: mediator.message,
  };
}

describe('chat-helper useSession', () => {
  it('should not GET session detail after creating an empty session', async () => {
    const { createdSession, mediator, sessionHttp, messageModule } = createMediator();
    const session = useSession(mediator);

    await session.createSession(createdSession);

    expect(sessionHttp.plusSession).toHaveBeenCalledWith(createdSession);
    expect(sessionHttp.getSession).not.toHaveBeenCalled();
    expect(messageModule.getMessages).not.toHaveBeenCalled();
    expect(session.current.value).toEqual(createdSession);
  });

  it('should still GET session detail when switching to a normal session', async () => {
    const { createdSession, mediator, sessionHttp, messageModule } = createMediator();
    const session = useSession(mediator);
    session.list.value = [createdSession];

    await session.chooseSession(createdSession.sessionCode);

    expect(sessionHttp.getSession).toHaveBeenCalledWith(createdSession.sessionCode);
    expect(messageModule.getMessages).toHaveBeenCalledWith(createdSession.sessionCode);
  });

  it('should update current and return API name when renamed session is not in list', async () => {
    const { mediator, sessionHttp } = createMediator();
    sessionHttp.renameSession = vi.fn().mockResolvedValue({
      sessionCode: 'wb_session_300edd5b93',
      sessionName: '重命名失败',
    });
    const session = useSession(mediator);
    session.list.value = [];
    session.current.value = {
      sessionCode: 'wb_session_300edd5b93',
      sessionName: '新会话',
    };

    const renamed = await session.renameSession('wb_session_300edd5b93');

    expect(renamed).toEqual({
      sessionCode: 'wb_session_300edd5b93',
      sessionName: '重命名失败',
    });
    expect(session.current.value?.sessionName).toBe('重命名失败');
  });
});
