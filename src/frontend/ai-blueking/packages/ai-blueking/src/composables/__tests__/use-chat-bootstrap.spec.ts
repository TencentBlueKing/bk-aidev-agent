import { ref } from 'vue';

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
      } as any,
      session: {
        getSessions: vi.fn().mockResolvedValue(undefined),
        list: ref([]),
        current: ref(null),
      } as any,
      message: { list: ref([]) } as any,
      http: {
        reset: vi.fn(),
        onError: vi.fn(),
        agent: {},
        session: {},
        message: {},
        fetchClient: {},
      } as any,
      reset: vi.fn(),
      onError: vi.fn(),
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
