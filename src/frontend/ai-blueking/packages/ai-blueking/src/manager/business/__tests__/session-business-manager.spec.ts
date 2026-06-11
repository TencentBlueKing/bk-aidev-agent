import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';

import { SessionBusinessManager } from '../session-business-manager';

import type { ISession } from '@blueking/chat-helper';

function createSessionModule(overrides: Record<string, unknown> = {}) {
  const current = ref<ISession | null>(null);
  const list = ref<ISession[]>([]);

  const sessionModule = {
    current,
    list,
    getSessions: vi.fn().mockImplementation(async () => {
      // default: no-op, list controlled by tests
    }),
    chooseSession: vi.fn().mockImplementation(async (sessionCode: string) => {
      const target = list.value.find(item => item.sessionCode === sessionCode) ?? null;
      current.value = target;
    }),
    createSession: vi.fn().mockImplementation(async (session: ISession) => {
      const created: ISession = {
        ...session,
        sessionContentCount: session.sessionContentCount ?? 0,
      };
      list.value.unshift(created);
      current.value = created;
    }),
    deleteSession: vi.fn(),
    getSession: vi.fn(),
    updateSession: vi.fn(),
    isCreateLoading: ref(false),
    isCurrentLoading: ref(false),
    isDeleteLoading: ref(false),
    isListLoading: ref(false),
    isUpdateLoading: ref(false),
    ...overrides,
  };

  return sessionModule;
}

describe('SessionBusinessManager.loadRecentSession', () => {
  let sessionModule: ReturnType<typeof createSessionModule>;
  let manager: SessionBusinessManager;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionModule = createSessionModule();
    manager = new SessionBusinessManager(sessionModule as never, null, null, {});
  });

  it('should skip re-initialization when current session already exists', async () => {
    const existingSession: ISession = {
      sessionCode: 'new_session_179123123123',
      sessionName: '新会话',
      sessionContentCount: 0,
    };
    sessionModule.current.value = existingSession;
    sessionModule.list.value = [existingSession];

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.chooseSession).not.toHaveBeenCalled();
    expect(sessionModule.createSession).not.toHaveBeenCalled();
    expect(sessionModule.getSessions).not.toHaveBeenCalled();
  });

  it('should switch empty recent session without loading messages', async () => {
    sessionModule.list.value = [
      {
        sessionCode: 'empty-session',
        sessionName: '空会话',
        sessionContentCount: 0,
      },
    ];

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.chooseSession).toHaveBeenCalledWith('empty-session', { loadMessages: false });
    expect(sessionModule.createSession).not.toHaveBeenCalled();
  });

  it('should switch initialSessionCode without loading messages when session is empty', async () => {
    manager = new SessionBusinessManager(sessionModule as never, null, null, {
      initialSessionCode: 'initial-empty',
    });
    sessionModule.list.value = [
      {
        sessionCode: 'initial-empty',
        sessionName: '初始空会话',
        sessionContentCount: 0,
      },
    ];

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.chooseSession).toHaveBeenCalledWith('initial-empty', { loadMessages: false });
  });

  it('should switch initialSessionCode with message loading when session has content', async () => {
    manager = new SessionBusinessManager(sessionModule as never, null, null, {
      initialSessionCode: 'initial-with-content',
    });
    sessionModule.list.value = [
      {
        sessionCode: 'initial-with-content',
        sessionName: '有内容会话',
        sessionContentCount: 3,
      },
    ];

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.chooseSession).toHaveBeenCalledWith('initial-with-content', { loadMessages: true });
  });

  it('should switch initialSessionCode with message loading when content count is missing', async () => {
    manager = new SessionBusinessManager(sessionModule as never, null, null, {
      initialSessionCode: 'initial-without-count',
    });
    sessionModule.list.value = [
      {
        sessionCode: 'initial-without-count',
        sessionName: '旧接口会话',
      },
    ];

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.chooseSession).toHaveBeenCalledWith('initial-without-count', { loadMessages: true });
  });

  it('should not re-switch after createNewSession when loadRecentSession is called again', async () => {
    sessionModule.list.value = [];

    await manager.loadRecentSession({ skipLoadSessions: true });
    expect(sessionModule.createSession).toHaveBeenCalledTimes(1);
    expect(sessionModule.chooseSession).not.toHaveBeenCalled();

    vi.clearAllMocks();

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.chooseSession).not.toHaveBeenCalled();
    expect(sessionModule.createSession).not.toHaveBeenCalled();
  });
});
