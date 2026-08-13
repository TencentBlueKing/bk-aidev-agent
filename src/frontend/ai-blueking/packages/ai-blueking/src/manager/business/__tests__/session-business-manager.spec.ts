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
    page: ref(0),
    numPages: ref(0),
    count: ref(0),
    hasMore: ref(false),
    getSessions: vi.fn().mockImplementation(async () => {
      // default: no-op, list controlled by tests
    }),
    loadMoreSessions: vi.fn().mockResolvedValue(undefined),
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
    updateSession: vi.fn().mockImplementation(async (session: ISession) => {
      current.value = { ...(current.value ?? { sessionCode: session.sessionCode, sessionName: '' }), ...session };
      const idx = list.value.findIndex(item => item.sessionCode === session.sessionCode);
      if (idx >= 0) {
        list.value[idx] = { ...list.value[idx], ...session };
      }
    }),
    isCreateLoading: ref(false),
    isCurrentLoading: ref(false),
    isDeleteLoading: ref(false),
    isListLoading: ref(false),
    isLoadingMore: ref(false),
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

  // 回归：alwaysCreateNewSession 为 true 时即使最近会话是空会话，也必须真正新建，
  // 不能被「复用空会话」逻辑改写成切换到已有空会话。
  it('should always create a new session when alwaysCreateNewSession is true even if recent session is empty', async () => {
    sessionModule.list.value = [
      {
        sessionCode: 'recent-empty',
        sessionName: '空会话',
        sessionContentCount: 0,
      },
    ];

    await manager.loadRecentSession({ skipLoadSessions: true, alwaysCreateNewSession: true });

    expect(sessionModule.createSession).toHaveBeenCalledTimes(1);
    // 不能复用切换到已有的空会话
    expect(sessionModule.chooseSession).not.toHaveBeenCalledWith('recent-empty', { loadMessages: false });
  });

  // skipLoadSessions 时不应在新建路径里重复拉取会话列表
  it('should not reload sessions when creating during loadRecentSession with skipLoadSessions', async () => {
    sessionModule.list.value = [];

    await manager.loadRecentSession({ skipLoadSessions: true });

    expect(sessionModule.createSession).toHaveBeenCalledTimes(1);
    expect(sessionModule.getSessions).not.toHaveBeenCalled();
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

describe('SessionBusinessManager.createNewSession', () => {
  let sessionModule: ReturnType<typeof createSessionModule>;
  let manager: SessionBusinessManager;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionModule = createSessionModule();
    manager = new SessionBusinessManager(sessionModule as never, null, null, {});
  });

  it('should return null when current session is already empty', async () => {
    const emptySession: ISession = {
      sessionCode: 'current-empty',
      sessionName: '空会话',
      sessionContentCount: 0,
    };
    sessionModule.current.value = emptySession;
    sessionModule.list.value = [emptySession];

    const result = await manager.createNewSession();

    expect(result).toBeNull();
    expect(sessionModule.createSession).not.toHaveBeenCalled();
    expect(sessionModule.chooseSession).not.toHaveBeenCalled();
  });

  it('should switch to latest empty session instead of creating new one', async () => {
    sessionModule.current.value = null;
    sessionModule.list.value = [
      { sessionCode: 'latest-empty', sessionName: '空会话', sessionContentCount: 0 },
      { sessionCode: 'old-session', sessionName: '旧会话', sessionContentCount: 5 },
    ];

    const result = await manager.createNewSession();

    expect(result).toBeNull();
    expect(sessionModule.chooseSession).toHaveBeenCalledWith('latest-empty', { loadMessages: false });
    expect(sessionModule.createSession).not.toHaveBeenCalled();
  });

  it('should create new session when latest session has content', async () => {
    sessionModule.current.value = null;
    sessionModule.list.value = [{ sessionCode: 'has-content', sessionName: '有内容', sessionContentCount: 3 }];

    const result = await manager.createNewSession();

    expect(result).not.toBeNull();
    expect(sessionModule.createSession).toHaveBeenCalled();
    expect(sessionModule.chooseSession).not.toHaveBeenCalled();
  });

  it('should create new session when session list is empty', async () => {
    sessionModule.current.value = null;
    sessionModule.list.value = [];

    const result = await manager.createNewSession();

    expect(result).not.toBeNull();
    expect(sessionModule.createSession).toHaveBeenCalled();
  });

  // 回归：聊天后 sessionContentCount 快照仍为 0，但实时消息列表已有真实内容，
  // 此时应真正新建会话，而不是把当前会话误判为空导致点击无反应。
  it('should create new session when current session has live messages despite stale count', async () => {
    const chattedSession: ISession = {
      sessionCode: 'chatted-session',
      sessionName: '新会话',
      sessionContentCount: 0,
    };
    sessionModule.current.value = chattedSession;
    sessionModule.list.value = [chattedSession];

    const messageModule = { list: ref([{ role: 'user', content: 'hi' }]) };
    manager = new SessionBusinessManager(sessionModule as never, null, null, {}, messageModule as never);

    const result = await manager.createNewSession();

    expect(result).not.toBeNull();
    expect(sessionModule.createSession).toHaveBeenCalled();
    // 不能把刚聊过的当前会话当作空会话复用
    expect(sessionModule.chooseSession).not.toHaveBeenCalledWith('chatted-session', { loadMessages: false });
  });

  // pause 预设消息不算真实内容，仍应按空会话处理
  it('should treat session with only pause messages as empty', async () => {
    const emptySession: ISession = {
      sessionCode: 'pause-only',
      sessionName: '空会话',
      sessionContentCount: 0,
    };
    sessionModule.current.value = emptySession;
    sessionModule.list.value = [emptySession];

    const messageModule = { list: ref([{ role: 'pause', content: 'x', property: { extra: { pause: true } } }]) };
    manager = new SessionBusinessManager(sessionModule as never, null, null, {}, messageModule as never);

    const result = await manager.createNewSession();

    expect(result).toBeNull();
    expect(sessionModule.createSession).not.toHaveBeenCalled();
  });

  it('should pass model to createSession when creating with model option', async () => {
    sessionModule.current.value = null;
    sessionModule.list.value = [{ sessionCode: 'has-content', sessionName: '有内容', sessionContentCount: 3 }];

    await manager.createNewSession({ model: 'deepseek' });

    expect(sessionModule.createSession).toHaveBeenCalledWith(
      expect.objectContaining({
        model: 'deepseek',
        sessionName: '新会话',
      }),
    );
  });

  it('should updateSession before switch when reusing empty session with a different model', async () => {
    sessionModule.current.value = null;
    sessionModule.list.value = [
      { sessionCode: 'latest-empty', sessionName: '空会话', sessionContentCount: 0, model: 'hy3-preview' },
    ];

    const callOrder: string[] = [];
    sessionModule.updateSession.mockImplementation(async (session: ISession) => {
      callOrder.push('updateSession');
      const current = sessionModule.current;
      current.value = { ...(current.value ?? { sessionCode: session.sessionCode, sessionName: '' }), ...session };
      const idx = sessionModule.list.value.findIndex(item => item.sessionCode === session.sessionCode);
      if (idx >= 0) {
        sessionModule.list.value[idx] = { ...sessionModule.list.value[idx], ...session };
      }
    });
    sessionModule.chooseSession.mockImplementation(async (sessionCode: string) => {
      callOrder.push('chooseSession');
      const target = sessionModule.list.value.find(item => item.sessionCode === sessionCode) ?? null;
      sessionModule.current.value = target;
    });

    const result = await manager.createNewSession({ model: 'deepseek' });

    expect(result).toBeNull();
    expect(sessionModule.createSession).not.toHaveBeenCalled();
    expect(sessionModule.updateSession).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionCode: 'latest-empty',
        model: 'deepseek',
      }),
    );
    expect(sessionModule.chooseSession).toHaveBeenCalledWith('latest-empty', { loadMessages: false });
    expect(callOrder).toEqual(['updateSession', 'chooseSession']);
  });

  it('should not updateSession when reusing empty session with same model', async () => {
    sessionModule.current.value = null;
    sessionModule.list.value = [
      { sessionCode: 'latest-empty', sessionName: '空会话', sessionContentCount: 0, model: 'deepseek' },
    ];

    await manager.createNewSession({ model: 'deepseek' });

    expect(sessionModule.updateSession).not.toHaveBeenCalled();
  });
});

describe('SessionBusinessManager model resolution', () => {
  let sessionModule: ReturnType<typeof createSessionModule>;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionModule = createSessionModule();
  });

  it('should use ModelSelectionManager to resolve model into available list', async () => {
    const { ModelSelectionManager } = await import('../model-selection-manager');
    const agentModule = {
      getLlms: vi.fn(),
      models: ref([
        {
          id: 1,
          llm_code: 'hy3-preview',
          llm_name: '混元3',
          llm_type: 'chat.completion',
          max_token_size: 1,
          property: { default: true },
          space_auth_mode: '',
          user_auth_mode: '',
        },
        {
          id: 2,
          llm_code: 'deepseek',
          llm_name: 'DeepSeek',
          llm_type: 'chat.completion',
          max_token_size: 1,
          property: {},
          space_auth_mode: '',
          user_auth_mode: '',
        },
      ]),
    };
    const modelSelection = new ModelSelectionManager(agentModule as never, sessionModule as never);
    await modelSelection.ensureLoaded();

    const manager = new SessionBusinessManager(
      sessionModule as never,
      agentModule as never,
      null,
      {},
      null,
      modelSelection,
    );
    sessionModule.current.value = null;
    sessionModule.list.value = [{ sessionCode: 'has-content', sessionName: '有内容', sessionContentCount: 3 }];

    await manager.createNewSession({ model: 'not-in-list' });

    expect(sessionModule.createSession).toHaveBeenCalledWith(
      expect.objectContaining({
        model: 'hy3-preview',
      }),
    );
  });

  it('should throw ModelUnavailableError when enabled but models are empty', async () => {
    const { ModelSelectionManager, ModelUnavailableError } = await import('../model-selection-manager');
    const agentModule = {
      getLlms: vi.fn().mockResolvedValue([]),
      models: ref([]),
    };
    const modelSelection = new ModelSelectionManager(agentModule as never, sessionModule as never);
    const manager = new SessionBusinessManager(
      sessionModule as never,
      agentModule as never,
      null,
      {},
      null,
      modelSelection,
    );
    sessionModule.current.value = null;
    sessionModule.list.value = [];

    await expect(manager.createSession({ name: '新会话' })).rejects.toThrow(ModelUnavailableError);
    expect(sessionModule.createSession).not.toHaveBeenCalled();
  });
});

describe('SessionBusinessManager pagination', () => {
  let sessionModule: ReturnType<typeof createSessionModule>;
  let manager: SessionBusinessManager;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionModule = createSessionModule();
    manager = new SessionBusinessManager(sessionModule as never, null, null, {});
  });

  it('should call getSessions when loadSessions', async () => {
    await manager.loadSessions();
    expect(sessionModule.getSessions).toHaveBeenCalledTimes(1);
  });

  it('should call loadMoreSessions when loadMoreSessions', async () => {
    await manager.loadMoreSessions();
    expect(sessionModule.loadMoreSessions).toHaveBeenCalledTimes(1);
  });

  it('should expose hasMoreSessions and isLoadingMore from session module', () => {
    sessionModule.hasMore.value = true;
    sessionModule.isLoadingMore.value = true;

    expect(manager.hasMoreSessions.value).toBe(true);
    expect(manager.isLoadingMore.value).toBe(true);
  });
});
