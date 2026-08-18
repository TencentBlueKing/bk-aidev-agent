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
    expandForSidePanel: vi.fn().mockResolvedValue(undefined),
    collapseSidePanel: vi.fn().mockResolvedValue(undefined),
    abortSidePanelSequence: vi.fn(),
  } as unknown as ComponentManager;
}

describe('usePanelContainer show', () => {
  let componentManager: ComponentManager;
  let ensureSessionReady: ReturnType<typeof vi.fn>;
  let readyResolve: (() => void) | undefined;
  let chatBotRef: ReturnType<typeof ref<undefined | { switchSession: ReturnType<typeof vi.fn> }>>;

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

describe('usePanelContainer aside orchestration', () => {
  function createParams(componentManager: ComponentManager) {
    return {
      componentManager,
      chatBotRef: ref(undefined) as never,
      forwarders: {} as never,
      forwardToManager: vi.fn(),
    };
  }

  it('handleExecutionPanelChange should only refresh extraWidth and not expand/collapse', async () => {
    const componentManager = createMockComponentManager();
    const { handleExecutionPanelChange, handleToggleAside } = usePanelContainer(createParams(componentManager));

    handleExecutionPanelChange(false, 600);

    expect(componentManager.expandForSidePanel).not.toHaveBeenCalled();
    expect(componentManager.collapseSidePanel).not.toHaveBeenCalled();

    await handleToggleAside();
    expect(componentManager.expandForSidePanel).toHaveBeenCalledWith(
      600,
      expect.objectContaining({ onBeforeSizeChange: expect.any(Function) }),
    );
  });

  it('handleToggleAside from collapsed should expand then set asideCollapsed false', async () => {
    const componentManager = createMockComponentManager();
    const { handleToggleAside, asideCollapsed } = usePanelContainer(createParams(componentManager));

    expect(asideCollapsed.value).toBe(true);
    await handleToggleAside();

    expect(componentManager.expandForSidePanel).toHaveBeenCalledWith(
      560,
      expect.objectContaining({ onBeforeSizeChange: expect.any(Function) }),
    );
    expect(asideCollapsed.value).toBe(false);
  });

  it('handleAsideCollapsedUpdate(true) should collapse after setting state', async () => {
    const componentManager = createMockComponentManager();
    const { handleToggleAside, handleAsideCollapsedUpdate, asideCollapsed } = usePanelContainer(
      createParams(componentManager),
    );

    await handleToggleAside();
    await handleAsideCollapsedUpdate(true);

    expect(asideCollapsed.value).toBe(true);
    expect(componentManager.collapseSidePanel).toHaveBeenCalledTimes(1);
  });

  it('hide should abort side panel sequence', () => {
    const componentManager = createMockComponentManager();
    const { hide, asideCollapsed } = usePanelContainer(createParams(componentManager));

    hide();

    expect(asideCollapsed.value).toBe(true);
    expect(componentManager.abortSidePanelSequence).toHaveBeenCalledTimes(1);
    expect(componentManager.hidePanel).toHaveBeenCalledTimes(1);
  });
});
