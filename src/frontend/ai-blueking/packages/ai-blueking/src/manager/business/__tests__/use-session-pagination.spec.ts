import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';

import { useSession } from '@blueking/chat-helper';

import type { ISession, ISessionListResult } from '@blueking/chat-helper';

function createPageResult(
  page: number,
  numPages: number,
  sessions: ISession[],
  count?: number,
): ISessionListResult {
  return {
    page,
    numPages,
    count: count ?? sessions.length,
    results: sessions,
  };
}

describe('useSession pagination', () => {
  let getSessionsMock: ReturnType<typeof vi.fn>;
  let session: ReturnType<typeof useSession>;

  beforeEach(() => {
    getSessionsMock = vi.fn();
    const mediator = {
      http: {
        session: {
          getSessions: getSessionsMock,
          plusSession: vi.fn(),
          modifySession: vi.fn(),
          deleteSession: vi.fn(),
          batchDeleteSessions: vi.fn(),
          getSession: vi.fn(),
          postSessionFeedback: vi.fn(),
          getSessionFeedbackReasons: vi.fn(),
          renameSession: vi.fn(),
          uploadFile: vi.fn(),
        },
      },
      agent: {
        abortChat: vi.fn(),
        resumeStreamingChat: vi.fn(),
        pollResumeSession: vi.fn(),
      },
      message: {
        list: ref([]),
        getMessages: vi.fn(),
      },
    };

    session = useSession(mediator as never);
  });

  it('should request page=1&page_size=20 and replace list', async () => {
    const page1 = [
      { sessionCode: 's1', sessionName: '会话1' },
      { sessionCode: 's2', sessionName: '会话2' },
    ];
    getSessionsMock.mockResolvedValue(createPageResult(1, 3, page1, 52));

    await session.getSessions();

    expect(getSessionsMock).toHaveBeenCalledWith({ page: 1, page_size: 20 });
    expect(session.list.value).toEqual(page1);
    expect(session.page.value).toBe(1);
    expect(session.numPages.value).toBe(3);
    expect(session.count.value).toBe(52);
    expect(session.hasMore.value).toBe(true);
  });

  it('should append next page and dedupe by sessionCode', async () => {
    getSessionsMock
      .mockResolvedValueOnce(
        createPageResult(1, 2, [
          { sessionCode: 's1', sessionName: '会话1' },
          { sessionCode: 's2', sessionName: '会话2' },
        ], 3),
      )
      .mockResolvedValueOnce(
        createPageResult(2, 2, [
          { sessionCode: 's2', sessionName: '会话2重复' },
          { sessionCode: 's3', sessionName: '会话3' },
        ], 3),
      );

    await session.getSessions();
    await session.loadMoreSessions();

    expect(getSessionsMock).toHaveBeenNthCalledWith(2, { page: 2, page_size: 20 });
    expect(session.list.value.map(s => s.sessionCode)).toEqual(['s1', 's2', 's3']);
    expect(session.page.value).toBe(2);
    expect(session.hasMore.value).toBe(false);
  });

  it('should set hasMore false when page >= numPages', async () => {
    getSessionsMock.mockResolvedValue(
      createPageResult(1, 1, [{ sessionCode: 's1', sessionName: '会话1' }], 1),
    );

    await session.getSessions();

    expect(session.hasMore.value).toBe(false);
  });

  // HTTP 层会将旧接口数组响应规范化为 page=1 / numPages=1，此处验证业务层不会误触发加载更多
  it('should not load more for legacy non-paginated list shape', async () => {
    const legacyList = [
      { sessionCode: 's1', sessionName: '会话1' },
      { sessionCode: 's2', sessionName: '会话2' },
    ];
    getSessionsMock.mockResolvedValue(createPageResult(1, 1, legacyList, legacyList.length));

    await session.getSessions();
    await session.loadMoreSessions();

    expect(session.list.value).toEqual(legacyList);
    expect(session.hasMore.value).toBe(false);
    expect(getSessionsMock).toHaveBeenCalledTimes(1);
  });

  it('should not request again while loading more', async () => {
    let resolveSecond!: (value: ISessionListResult) => void;
    getSessionsMock
      .mockResolvedValueOnce(
        createPageResult(1, 3, [{ sessionCode: 's1', sessionName: '会话1' }], 30),
      )
      .mockImplementationOnce(
        () =>
          new Promise<ISessionListResult>(resolve => {
            resolveSecond = resolve;
          }),
      );

    await session.getSessions();
    const firstLoad = session.loadMoreSessions();
    const secondLoad = session.loadMoreSessions();

    expect(getSessionsMock).toHaveBeenCalledTimes(2);

    resolveSecond(
      createPageResult(2, 3, [{ sessionCode: 's2', sessionName: '会话2' }], 30),
    );
    await Promise.all([firstLoad, secondLoad]);

    expect(getSessionsMock).toHaveBeenCalledTimes(2);
    expect(session.list.value.map(s => s.sessionCode)).toEqual(['s1', 's2']);
  });

  it('should not load more when hasMore is false', async () => {
    getSessionsMock.mockResolvedValue(
      createPageResult(1, 1, [{ sessionCode: 's1', sessionName: '会话1' }], 1),
    );

    await session.getSessions();
    await session.loadMoreSessions();

    expect(getSessionsMock).toHaveBeenCalledTimes(1);
  });
});
