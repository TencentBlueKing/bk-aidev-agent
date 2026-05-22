import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';

import { BootstrapPhase, useChatBootstrap } from '../use-chat-bootstrap';

let getAgentInfoResolve: (() => void) | undefined;
let getAgentInfoResolvers: Array<() => void> = [];
let getSessionsCallCount = 0;

vi.mock('@blueking/chat-helper', async () => {
  const { ref: vueRef } = await import('vue');
  return {
    AGUIProtocol: vi.fn().mockImplementation(function (this: { injectMessageModule: ReturnType<typeof vi.fn> }) {
      this.injectMessageModule = vi.fn();
    }),
    useChatHelper: vi.fn().mockImplementation(() => ({
      agent: {
        getAgentInfo: vi.fn().mockImplementation(
          () =>
            new Promise<void>(resolve => {
              getAgentInfoResolve = resolve;
              getAgentInfoResolvers.push(resolve);
            }),
        ),
        info: vueRef(null),
        isChatting: vueRef(false),
      },
      session: {
        getSessions: vi.fn().mockImplementation(async () => {
          getSessionsCallCount += 1;
        }),
        list: vueRef([]),
        current: vueRef(null),
      },
      message: {
        list: vueRef([]),
      },
      http: {},
    })),
  };
});

describe('useChatBootstrap initialize', () => {
  beforeEach(() => {
    getAgentInfoResolve = undefined;
    getAgentInfoResolvers = [];
    getSessionsCallCount = 0;
    vi.clearAllMocks();
  });

  it('should reuse in-flight initialize promise for concurrent callers', async () => {
    const { initialize, phase } = useChatBootstrap({
      url: '/api/chat/',
      autoInit: false,
    });

    const first = initialize();
    const second = initialize();

    expect(phase.value).toBe(BootstrapPhase.LOADING_AGENT);
    expect(getSessionsCallCount).toBe(1);

    getAgentInfoResolve?.();
    await Promise.all([first, second]);

    expect(phase.value).toBe(BootstrapPhase.READY);
    expect(getSessionsCallCount).toBe(1);
  });

  it('should skip re-initialization after success', async () => {
    const bootstrap = useChatBootstrap({
      url: '/api/chat/',
      autoInit: false,
    });

    const initPromise = bootstrap.initialize();
    getAgentInfoResolve?.();
    await initPromise;

    getSessionsCallCount = 0;
    await bootstrap.initialize();

    expect(bootstrap.phase.value).toBe(BootstrapPhase.READY);
    expect(getSessionsCallCount).toBe(0);
  });

  it('should ignore stale initialization result after updateConfig starts a newer initialization', async () => {
    const bootstrap = useChatBootstrap({
      url: '/api/chat/',
      autoInit: false,
    });

    const staleInitialize = bootstrap.initialize();
    expect(bootstrap.phase.value).toBe(BootstrapPhase.LOADING_AGENT);

    const latestInitialize = bootstrap.updateConfig('/api/chat-v2/');
    expect(bootstrap.phase.value).toBe(BootstrapPhase.LOADING_AGENT);

    getAgentInfoResolvers[0]?.();
    await staleInitialize;

    expect(bootstrap.phase.value).toBe(BootstrapPhase.LOADING_AGENT);

    getAgentInfoResolvers[1]?.();
    await latestInitialize;

    expect(bootstrap.phase.value).toBe(BootstrapPhase.READY);
  });

  it('should reject concurrent callers when initialization fails', async () => {
    const { useChatHelper } = await import('@blueking/chat-helper');

    vi.mocked(useChatHelper).mockImplementationOnce(() => ({
      agent: {
        getAgentInfo: vi.fn().mockRejectedValue(new Error('init failed')),
        info: ref(null),
        isChatting: ref(false),
      },
      session: {
        getSessions: vi.fn().mockResolvedValue(undefined),
        list: ref([]),
        current: ref(null),
      },
      message: { list: ref([]) },
      http: {},
    }));

    const { initialize, phase, error } = useChatBootstrap({
      url: '/api/chat/',
      autoInit: false,
    });

    await expect(Promise.all([initialize(), initialize()])).rejects.toThrow('init failed');

    expect(phase.value).toBe(BootstrapPhase.ERROR);
    expect(error.value?.message).toBe('init failed');
  });
});
