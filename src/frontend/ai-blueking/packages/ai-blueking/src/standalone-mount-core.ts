/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { ConfigProvider } from 'bkui-vue';
import { type App, type Component, createApp, h, shallowReactive } from 'vue';

import { emitNameToListenerProp } from './vue2-wrapper';

declare const BKUI_PREFIX: string | undefined;

interface GlobalBkuiPrefix {
  BKUI_PREFIX?: string;
}

/** 非 Vue 宿主的事件监听映射（emit 名 -> handler） */
export type StandaloneEventHandlers = Record<string, (...args: unknown[]) => void>;

export interface StandaloneMountOptions<TProps extends object = Record<string, unknown>> {
  /** 组件 props */
  props?: TProps;
  /** 事件监听，键为 kebab-case emit 名（如 send-message）或已转换的 onXxx */
  on?: StandaloneEventHandlers;
}

export interface StandaloneMountHandle<TExpose, TProps extends object = Record<string, unknown>> {
  /** 内部 Vue 应用实例 */
  app: App;
  /** 当前组件 expose（挂载后 nextTick 可用） */
  getExpose: () => TExpose | null;
  /** 与 getExpose() 同步的只读访问 */
  readonly expose: TExpose | null;
  /** 合并更新 props，不重建应用 */
  updateProps: (partial: Partial<TProps>) => void;
  /** 卸载并清理 */
  unmount: () => void;
}

function getRuntimeBkuiPrefix(): string {
  if (typeof BKUI_PREFIX === 'string' && BKUI_PREFIX.length > 0) {
    return BKUI_PREFIX;
  }

  const globalPrefix = (globalThis as GlobalBkuiPrefix).BKUI_PREFIX;
  return typeof globalPrefix === 'string' && globalPrefix.length > 0 ? globalPrefix : 'bk';
}

/**
 * 解析挂载容器
 */
export function resolveMountContainer(container: string | Element): Element {
  if (typeof container !== 'string') {
    return container;
  }

  const el = document.querySelector(container);
  if (!el) {
    throw new Error(`[ai-blueking] mount container not found: ${container}`);
  }

  return el;
}

/**
 * 将 on 配置转为 Vue3 vnode listener props
 */
export function buildStandaloneListeners(on?: StandaloneEventHandlers): Record<string, (...args: unknown[]) => void> {
  if (!on) {
    return {};
  }

  const handlers: Record<string, (...args: unknown[]) => void> = {};
  for (const [eventName, handler] of Object.entries(on)) {
    if (!handler) {
      continue;
    }

    const listenerKey =
      eventName.startsWith('on') && eventName.length > 2 ? eventName : emitNameToListenerProp(eventName);
    handlers[listenerKey] = handler;
  }

  return handlers;
}

/**
 * 挂载任意 Vue 组件（使用 standalone bundle 内联的 Vue runtime）
 */
export function mountStandaloneComponent<TProps extends object, TExpose>(
  container: string | Element,
  component: Component,
  options?: StandaloneMountOptions<TProps>,
): StandaloneMountHandle<TExpose, TProps> {
  const mountEl = resolveMountContainer(container);
  const propsState = shallowReactive({ ...(options?.props ?? {}) }) as TProps;
  let componentInstance: TExpose | null = null;

  const app = createApp({
    setup() {
      return () =>
        h(
          ConfigProvider,
          { prefix: getRuntimeBkuiPrefix() },
          {
            default: () =>
              h(component, {
                ...propsState,
                ...buildStandaloneListeners(options?.on),
                ref: (instance: unknown) => {
                  componentInstance = instance as TExpose | null;
                },
              }),
          },
        );
    },
  });

  app.mount(mountEl);

  return {
    app,
    getExpose: () => componentInstance,
    get expose() {
      return componentInstance;
    },
    updateProps(partial: Partial<TProps>) {
      Object.assign(propsState, partial);
    },
    unmount() {
      app.unmount();
      componentInstance = null;
    },
  };
}
