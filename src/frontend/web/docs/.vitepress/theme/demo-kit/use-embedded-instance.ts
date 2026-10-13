import { camelize, computed, onMounted, toHandlerKey, toValue, type ComputedRef, type MaybeRefOrGetter } from 'vue';
import type { ChatBotExpose, IRequestOptions } from '@blueking/ai-blueking';

import { mergeRequestOptions, type ResolvedRequestOptions } from './request-options';

import { useDemoRuntime, type DemoComponentEvent } from './use-demo-runtime';

const CHATBOT_EVENTS: DemoComponentEvent[] = [
  'agent-info-loaded',
  'send-message',
  'receive-start',
  'receive-end',
  'stop',
  'rename',
  'session-switched',
  'shortcut-click',
  'update:asideCollapsed',
  'error',
];

export type EventHandlers = Record<string, (payload?: unknown) => void>;

/**
 * 事件名 → 组件 props 形式的监听器（onAgentInfoLoaded）。
 * 必须用 v-bind 绑定：与组件内同名 @事件 合并为数组，二者都会触发；
 * 用 v-on 绑定 kebab 名会得到 onAgent-info-loaded，emit 时会遮蔽组件内的监听。
 */
export function toListenerProps(handlers: EventHandlers): EventHandlers {
  return Object.fromEntries(Object.entries(handlers).map(([name, fn]) => [toHandlerKey(camelize(name)), fn]));
}

export interface EmbeddedInstance {
  /** 绑定到 <ChatBot :ref="bindRef"> */
  bindRef: (expose: unknown) => void;
  /** 事件名 → 处理函数：写入本配方的时间线 */
  handlers: EventHandlers;
  /** <ChatBot v-bind="listeners">（props 形式，见 toListenerProps） */
  listeners: EventHandlers;
  url: ComputedRef<string>;
  requestOptions: ResolvedRequestOptions;
  /** ChatBot 的 :key，重置演示 / 切换后端时重建 */
  key: ComputedRef<number>;
}

export interface EmbeddedInstanceOptions {
  /** 配方自己的 requestOptions，叠加在运行时的 Mock 头之上 */
  requestOptions?: MaybeRefOrGetter<IRequestOptions | undefined>;
  /** 覆盖实例的 url（如切换智能体）；默认跟随演示环境 */
  url?: MaybeRefOrGetter<string>;
}

/** 舞台内嵌入的 ChatBot：与浮窗共用同一套打点、请求记录与后端切换 */
export function useEmbeddedInstance(recipeId: string, options: EmbeddedInstanceOptions = {}): EmbeddedInstance {
  const runtime = useDemoRuntime();
  const instanceId = `embedded:${recipeId}`;

  onMounted(() => {
    void runtime.ensureComponentStyles();
  });

  const handlers: EventHandlers = Object.fromEntries(
    CHATBOT_EVENTS.map(name => [name, (payload?: unknown) => runtime.handleComponentEvent(instanceId, name, payload)]),
  );

  return {
    bindRef: expose => runtime.attach(instanceId, (expose as ChatBotExpose | null) ?? undefined),
    handlers,
    listeners: toListenerProps(handlers),
    url: computed(() => (options.url ? toValue(options.url) : runtime.apiUrl.value)),
    requestOptions: mergeRequestOptions(runtime.requestOptionsFor(instanceId), options.requestOptions),
    key: computed(() => runtime.state.instanceKey),
  };
}
