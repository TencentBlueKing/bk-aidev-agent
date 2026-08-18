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
import { defineComponent, nextTick, watch } from 'vue';

import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useDraggable } from '../use-draggable';

import type { UseDraggableOptions, UseDraggableReturn } from '../types';

function mountDraggable(options: UseDraggableOptions = {}) {
  let api!: UseDraggableReturn;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useDraggable(options);
        return () => null;
      },
    }),
  );
  return { api, wrapper };
}

describe('useDraggable side panel geometry', () => {
  const originalInnerWidth = window.innerWidth;
  const originalInnerHeight = window.innerHeight;

  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1920 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 1080 });
  });

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalInnerWidth });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: originalInnerHeight });
  });

  it('docked-right expand writes x before width so VDR can grow', async () => {
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 1520,
      maxWidthPercent: 80,
    });

    const promise = api.expandForSidePanel(560);
    expect(api.left.value).toBe(960);
    expect(api.width.value).toBe(400);

    await promise;
    expect(api.left.value).toBe(960);
    expect(api.width.value).toBe(960);
    expect(api.isSidePanelExpanded.value).toBe(true);

    wrapper.unmount();
  });

  it('notifies aside open together with widening after the x write', async () => {
    const events: string[] = [];
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 1520,
      maxWidthPercent: 80,
    });

    watch(
      () => api.left.value,
      () => events.push('left'),
    );
    watch(
      () => api.width.value,
      () => events.push('width'),
    );

    await api.expandForSidePanel(560, {
      onBeforeSizeChange: () => events.push('aside'),
    });

    expect(events).toEqual(['left', 'aside', 'width']);

    wrapper.unmount();
  });

  it('skips geometry when the window is already wide enough for the aside', async () => {
    const onBeforeSizeChange = vi.fn();
    const { api, wrapper } = mountDraggable({
      initWidth: 1000,
      defaultLeft: 920,
      minWidth: 400,
      maxWidthPercent: 80,
    });

    await api.expandForSidePanel(560, { onBeforeSizeChange });
    expect(api.left.value).toBe(920);
    expect(api.width.value).toBe(1000);
    expect(onBeforeSizeChange).toHaveBeenCalledTimes(1);

    const collapsePromise = api.collapseSidePanel();
    await collapsePromise;
    expect(api.left.value).toBe(920);
    expect(api.width.value).toBe(1000);

    wrapper.unmount();
  });

  it('skips shift when there is enough room on the right', async () => {
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 100,
      maxWidthPercent: 80,
    });

    const promise = api.expandForSidePanel(560);
    expect(api.left.value).toBe(100);

    await promise;
    expect(api.left.value).toBe(100);
    expect(api.width.value).toBe(960);

    wrapper.unmount();
  });

  it('collapse keeps left edge and shrinks width from the right', async () => {
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 1520,
      maxWidthPercent: 80,
    });

    await api.expandForSidePanel(560);
    expect(api.left.value).toBe(960);
    expect(api.width.value).toBe(960);

    const promise = api.collapseSidePanel();
    expect(api.width.value).toBe(400);
    expect(api.left.value).toBe(960);

    await promise;
    expect(api.left.value).toBe(960);
    expect(api.width.value).toBe(400);
    expect(api.isSidePanelExpanded.value).toBe(false);

    wrapper.unmount();
  });

  it('clamps expand when viewport cannot fit extra width', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 800 });
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 400,
      maxWidthPercent: 100,
    });

    await api.expandForSidePanel(560);
    expect(api.left.value).toBe(0);
    expect(api.width.value).toBe(800);

    wrapper.unmount();
  });

  it('ignores a second expand while already expanded', async () => {
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 1520,
      maxWidthPercent: 80,
    });

    const first = api.expandForSidePanel(560);
    await api.expandForSidePanel(560);
    await first;

    expect(api.left.value).toBe(960);
    expect(api.width.value).toBe(960);

    wrapper.unmount();
  });

  it('abortSidePanelSequence restores the start layout', async () => {
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 1520,
      maxWidthPercent: 80,
    });

    const promise = api.expandForSidePanel(560);
    expect(api.left.value).toBe(960);
    api.abortSidePanelSequence();
    await promise;
    await nextTick();

    expect(api.left.value).toBe(1520);
    expect(api.width.value).toBe(400);
    expect(api.isSidePanelExpanded.value).toBe(false);

    wrapper.unmount();
  });

  it('drag while collapsed discards expanded snapshot so next expand uses current geometry', async () => {
    const { api, wrapper } = mountDraggable({
      initWidth: 400,
      defaultLeft: 1520,
      maxWidthPercent: 80,
    });

    await api.expandForSidePanel(560);
    await api.collapseSidePanel();
    api.handleDragStop(100, 0);
    await api.expandForSidePanel(560);

    expect(api.left.value).toBe(100);
    expect(api.width.value).toBe(960);

    wrapper.unmount();
  });
});
