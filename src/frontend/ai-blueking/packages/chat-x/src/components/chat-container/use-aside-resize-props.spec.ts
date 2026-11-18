/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { effectScope, nextTick, shallowRef } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { resolveAsideMaxWidth, useAsideResizeProps } from './use-aside-resize-props';

type ResizeCallback = (entries: Array<{ contentRect: { width: number } }>) => void;

const stubResizeObserver = () => {
  const instances: Array<{ callback: ResizeCallback; disconnect: ReturnType<typeof vi.fn> }> = [];
  class ResizeObserverStub {
    disconnect = vi.fn();
    constructor(callback: ResizeCallback) {
      instances.push({ callback, disconnect: this.disconnect });
    }
    observe() {}
  }
  vi.stubGlobal('ResizeObserver', ResizeObserverStub);
  return instances;
};

describe('resolveAsideMaxWidth', () => {
  it('容器宽度未知时沿用调用方 max', () => {
    expect(resolveAsideMaxWidth({ asideMin: 400, containerWidth: 0, mainMin: 400, userMax: 1000 })).toBe(1000);
  });

  it('容器宽度未知且未传 max 时不设上限', () => {
    expect(resolveAsideMaxWidth({ asideMin: 400, containerWidth: 0, mainMin: 400 })).toBeUndefined();
  });

  it('给主聊天区留出最小宽度，并与调用方 max 取更小值', () => {
    expect(resolveAsideMaxWidth({ asideMin: 400, containerWidth: 1000, mainMin: 400 })).toBe(600);
    expect(resolveAsideMaxWidth({ asideMin: 400, containerWidth: 1000, mainMin: 400, userMax: 500 })).toBe(500);
  });

  it('放不下主栏下限时，侧栏 max 不低于侧栏 min', () => {
    expect(resolveAsideMaxWidth({ asideMin: 400, containerWidth: 500, mainMin: 400 })).toBe(400);
  });
});

describe('useAsideResizeProps', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('按容器宽度收紧侧栏 max，且不把 mainMin 交给 ResizeLayout', async () => {
    const observers = stubResizeObserver();
    const scope = effectScope();
    const element = shallowRef<HTMLElement | null>(document.createElement('div'));
    const layoutProps = scope.run(() =>
      useAsideResizeProps(element, () => ({ mainMin: 400, max: 1000, min: 300 })),
    );
    await nextTick();

    expect(layoutProps?.value).toEqual({ collapsible: false, immediate: true, max: 1000, min: 300, placement: 'right' });

    observers.at(-1)?.callback([{ contentRect: { width: 900 } }]);
    expect(layoutProps?.value.max).toBe(500);
    expect(layoutProps?.value).not.toHaveProperty('mainMin');

    scope.stop();
  });

  it('元素替换或作用域销毁时断开旧的监听', async () => {
    const observers = stubResizeObserver();
    const scope = effectScope();
    const element = shallowRef<HTMLElement | null>(document.createElement('div'));
    scope.run(() => useAsideResizeProps(element, () => undefined));
    await nextTick();

    element.value = document.createElement('div');
    await nextTick();
    expect(observers).toHaveLength(2);
    expect(observers[0]?.disconnect).toHaveBeenCalledTimes(1);

    scope.stop();
    expect(observers[1]?.disconnect).toHaveBeenCalledTimes(1);
  });
});
