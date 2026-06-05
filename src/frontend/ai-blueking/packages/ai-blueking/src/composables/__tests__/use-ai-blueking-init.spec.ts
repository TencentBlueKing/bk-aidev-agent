import { describe, expect, it, vi } from 'vitest';
import { computed, reactive, ref, toValue } from 'vue';

import { useAiBluekingInit } from '../use-ai-blueking-init';

import type { ChatBootstrapOptions } from '../use-chat-bootstrap';
import type { AIBluekingProps } from '../../types';

let capturedBootstrapOptions: ChatBootstrapOptions | undefined;

vi.mock('../../manager', () => ({
  createComponentManager: vi.fn(() => ({
    panelVisible: ref(false),
    nimbusMinimized: ref(false),
    isCompressed: ref(false),
    destroy: vi.fn(),
    emitInternal: vi.fn(),
    hidePanel: vi.fn(),
    setContainerRef: vi.fn(),
    showPanel: vi.fn(),
  })),
}));

vi.mock('../../manager/business/session-business-manager', () => ({
  SessionBusinessManager: vi.fn().mockImplementation(function MockSessionBusinessManager() {
    return {
      loadRecentSession: vi.fn().mockResolvedValue(undefined),
    };
  }),
}));

vi.mock('../../manager/business/share-business-manager', () => ({
  ShareBusinessManager: vi.fn().mockImplementation(function MockShareBusinessManager() {
    return {};
  }),
}));

vi.mock('../../manager/business/shortcut-manager', () => ({
  ShortcutManager: vi.fn().mockImplementation(function MockShortcutManager() {
    return {
      setAgentShortcuts: vi.fn(),
      setShortcuts: vi.fn(),
    };
  }),
}));

vi.mock('../use-event-bridge', () => ({
  createEventForwarders: vi.fn(() => ({
    receiveDone: vi.fn(),
    receiveEnd: vi.fn(),
    receiveStart: vi.fn(),
    receiveText: vi.fn(),
  })),
  useEventBridge: vi.fn(() => ({
    forwardToManager: vi.fn(),
  })),
}));

vi.mock('../use-chat-bootstrap', () => ({
  useChatBootstrap: vi.fn((options: ChatBootstrapOptions) => {
    capturedBootstrapOptions = options;
    return {
      agentInfo: ref(null),
      agentName: ref(''),
      chatHelper: {
        agent: {},
        message: { list: ref([]) },
        session: {},
      },
      currentSession: ref(null),
      error: ref(null),
      initialize: vi.fn().mockResolvedValue(undefined),
      isReady: ref(false),
    };
  }),
}));

describe('useAiBluekingInit requestOptions', () => {
  it('passes requestOptions as a getter so bootstrap reads latest prop value', () => {
    const props = reactive({
      defaultMinimize: false,
      draggable: true,
      enablePopup: true,
      hideNimbus: false,
      requestOptions: computed(() => ({
        data: { app_id: 'app-1' },
        headers: { Authorization: 'Bearer token-1' },
      })),
      url: '/api/chat/',
    }) as AIBluekingProps;

    useAiBluekingInit({
      props,
      emit: vi.fn(),
    });

    expect(typeof capturedBootstrapOptions?.requestOptions).toBe('function');
    expect(toValue(capturedBootstrapOptions?.requestOptions)).toEqual({
      data: { app_id: 'app-1' },
      headers: { Authorization: 'Bearer token-1' },
    });

    props.requestOptions = computed(() => ({
      data: { app_id: 'app-2' },
      headers: { Authorization: 'Bearer token-2' },
    }));

    expect(toValue(capturedBootstrapOptions?.requestOptions)).toEqual({
      data: { app_id: 'app-2' },
      headers: { Authorization: 'Bearer token-2' },
    });
  });
});
