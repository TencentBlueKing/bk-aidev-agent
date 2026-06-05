import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';

import { usePanelContainer } from '../use-panel-container';

import type { ComponentManager } from '../../manager/component-manager';

function createMockComponentManager() {
  return {
    showPanel: vi.fn(),
    hidePanel: vi.fn(),
    handleNimbusClick: vi.fn(),
    emit: vi.fn(),
    container: {
      updatePosition: vi.fn(),
      updateSize: vi.fn(),
      updatePositionAndSize: vi.fn(),
      toggleCompression: vi.fn(),
    },
    setCompressed: vi.fn(),
    handleDragging: vi.fn(),
    handleResizing: vi.fn(),
    handleDragStop: vi.fn(),
    handleResizeStop: vi.fn(),
    expandForSidePanel: vi.fn(),
    collapseSidePanel: vi.fn(),
  } as unknown as ComponentManager;
}

describe('usePanelContainer show', () => {
  let componentManager: ComponentManager;
  let ensureSessionReady: ReturnType<typeof vi.fn>;
  let readyResolve: (() => void) | undefined;
  let chatBotRef: ReturnType<typeof ref<{ switchSession: ReturnType<typeof vi.fn> } | undefined>>;

  beforeEach(() => {
    componentManager = createMockComponentManager();
    readyResolve = undefined;
    ensureSessionReady = vi.fn().mockImplementation(
      () =>
        new Promise<void>(resolve => {
          readyResolve = resolve;
        }),
    );
    chatBotRef = ref({
      switchSession: vi.fn().mockResolvedValue(undefined),
    });
  });

  it('should show panel immediately but resolve after ensureSessionReady', async () => {
    const { show } = usePanelContainer({
      componentManager,
      chatBotRef: chatBotRef as never,
      ensureSessionReady,
      forwarders: {} as never,
      forwardToManager: vi.fn(),
    });

    const showPromise = show();

    expect(componentManager.showPanel).toHaveBeenCalledTimes(1);
    expect(ensureSessionReady).toHaveBeenCalledTimes(1);

    let settled = false;
    showPromise.then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);

    readyResolve?.();
    await showPromise;
    expect(settled).toBe(true);
  });

  it('should switch session only after ensureSessionReady when sessionCode is provided', async () => {
    const { show } = usePanelContainer({
      componentManager,
      chatBotRef: chatBotRef as never,
      ensureSessionReady,
      forwarders: {} as never,
      forwardToManager: vi.fn(),
    });

    const showPromise = show('session-abc');
    await Promise.resolve();

    expect(ensureSessionReady).toHaveBeenCalled();
    expect(chatBotRef.value!.switchSession).not.toHaveBeenCalled();

    readyResolve?.();
    await showPromise;

    expect(chatBotRef.value!.switchSession).toHaveBeenCalledWith('session-abc');
  });

  it('should reject when ensureSessionReady rejects', async () => {
    const initError = new Error('session init failed');
    ensureSessionReady.mockRejectedValue(initError);

    const { show } = usePanelContainer({
      componentManager,
      chatBotRef: chatBotRef as never,
      ensureSessionReady,
      forwarders: {} as never,
      forwardToManager: vi.fn(),
    });

    await expect(show()).rejects.toThrow('session init failed');
    expect(componentManager.showPanel).toHaveBeenCalledTimes(1);
    expect(chatBotRef.value!.switchSession).not.toHaveBeenCalled();
  });
});
