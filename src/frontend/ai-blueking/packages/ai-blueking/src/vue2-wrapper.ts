/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { createApp, h } from 'vue';
import type { Component } from 'vue';

/**
 * Vue2 Prop 定义（与 Vue 2 Options API 的 props 字段一致）
 */
export type Vue2PropDefinition = Record<string, unknown>;

export interface Vue2WrapperConfig {
  /** 深度变化时卸载并重新 mount 内层 Vue3 app（与历史 AIBluekingV2 行为一致） */
  deepWatchProps?: string[];
  /** Vue3 组件 emit 名称（kebab-case），将桥接为 onXxx 监听 */
  emitNames: string[];
  /** 从 Vue3 子组件实例同步到 Vue2 this 的键（函数会 bind，其余直接赋值如 Ref） */
  exposeKeys: string[];
  /** Vue2 methods（例如 mounted 前的占位实现） */
  methods?: Record<string, (...args: unknown[]) => unknown>;
  name: string;
  /** Vue2 侧 props 定义 */
  props: Vue2PropDefinition;
  /** 需要从 Vue2 $scopedSlots 透传到 Vue3 的插槽名 */
  slots?: string[];
}

/**
 * 创建在 Vue2 环境中用 Vue3 createApp 渲染 Vue3 组件的桥接组件
 */
export function createVue2Wrapper(Vue3Component: Component, config: Vue2WrapperConfig): unknown {
  const { name, props: propsDefinition, emitNames, exposeKeys, slots = [], deepWatchProps = [], methods = {} } = config;

  const propKeys = Object.keys(propsDefinition);

  return {
    name,
    render(createElement: (tag: string, data?: unknown, children?: unknown) => unknown) {
      return createElement('div', {
        style: { width: '100%', height: '100%' },
      });
    },
    props: propsDefinition,
    data() {
      return {
        app: null as null | ReturnType<typeof createApp>,
        componentInstance: null as null | Record<string, unknown>,
        unWatchStack: [] as Array<() => void>,
      };
    },
    created(this: Record<string, unknown>) {
      const emit = (this.$emit as (event: string, ...args: unknown[]) => void).bind(this);
      const that = this as Record<string, unknown> & {
        $attrs: Record<string, unknown>;
        $el: HTMLElement;
        $scopedSlots?: Record<string, (props: unknown) => unknown>;
        app: null | ReturnType<typeof createApp>;
        componentInstance: null | Record<string, unknown>;
        unWatchStack: Array<() => void>;
      };

      that.app = createApp({
        setup() {
          return () => {
            const explicit: Record<string, unknown> = {};
            for (const key of propKeys) {
              explicit[key] = that[key];
            }

            const slotBuilders: Record<string, (slotProps: unknown) => unknown> = {};
            for (const slotName of slots) {
              const scoped = that.$scopedSlots?.[slotName];
              if (scoped !== undefined) {
                slotBuilders[slotName] = (slotProps: unknown) => scoped(slotProps);
              }
            }
            const slotArg = Object.keys(slotBuilders).length > 0 ? slotBuilders : undefined;

            return h(
              Vue3Component,
              {
                ...that.$attrs,
                ...explicit,
                ...buildEmitHandlers(emit, emitNames),
                ref: (el: unknown) => {
                  that.componentInstance = el as null | Record<string, unknown>;
                },
              },
              slotArg,
            );
          };
        },
      });

      for (const path of deepWatchProps) {
        that.unWatchStack.push(
          (that.$watch as (path: string, cb: () => void, opts?: { deep?: boolean }) => () => void)(
            path,
            () => {
              if (that.app) {
                that.app.unmount();
                that.app.mount(that.$el);
              }
            },
            { deep: true },
          ),
        );
      }
    },
    mounted(this: Record<string, unknown>) {
      const that = this as typeof this & {
        $el: HTMLElement;
        $nextTick: (fn: () => void) => void;
        app: null | ReturnType<typeof createApp>;
        componentInstance: null | Record<string, unknown>;
        unWatchStack: Array<() => void>;
      };
      that.app?.mount(that.$el);
      that.$nextTick(() => {
        const inst = that.componentInstance;
        if (!inst) return;
        for (const key of exposeKeys) {
          const val = inst[key];
          if (typeof val === 'function') {
            (that as Record<string, unknown>)[key] = (val as (...a: unknown[]) => unknown).bind(inst);
          } else {
            (that as Record<string, unknown>)[key] = val;
          }
        }
      });
    },
    beforeDestroy(this: Record<string, unknown>) {
      const that = this as typeof this & {
        app: null | ReturnType<typeof createApp>;
        componentInstance: null | Record<string, unknown>;
        unWatchStack: Array<() => void>;
      };
      that.unWatchStack.forEach(unWatch => unWatch?.());
      that.unWatchStack = [];
      if (that.app) {
        that.app.unmount();
        that.app = null;
      }
      that.componentInstance = null;
    },
    methods,
  } as unknown;
}

/**
 * 将 emit 名转为 Vue3 vnode 上的 onXxx 属性名，例如 send-message -> onSendMessage
 */
export function emitNameToListenerProp(emitName: string): string {
  return (
    'on' +
    emitName
      .split('-')
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join('')
  );
}

function buildEmitHandlers(
  emit: (event: string, ...args: unknown[]) => void,
  emitNames: string[],
): Record<string, (...args: unknown[]) => void> {
  const handlers: Record<string, (...args: unknown[]) => void> = {};
  for (const name of emitNames) {
    handlers[emitNameToListenerProp(name)] = (...args: unknown[]) => {
      emit(name, ...args);
    };
  }
  return handlers;
}
