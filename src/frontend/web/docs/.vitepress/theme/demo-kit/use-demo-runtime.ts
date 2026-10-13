import { computed, effectScope, markRaw, reactive, shallowReactive, watchEffect, type ComputedRef, type EffectScope } from 'vue';
import type { AIBluekingExpose, ChatBotExpose } from '@blueking/ai-blueking';

import { getRuntimeGlobal } from '../utils/runtime-globals';
import { describeArg, describeCall } from './describe-call';
import { DEMO_INSTANCE_HEADER, installFetchRecorder, type FetchRecordHooks } from './fetch-recorder';
import { createDemoRecorder, type DemoRecorder } from './recorder';
import type {
  BackendMode,
  FloatingConfig,
  FloatingSlotRender,
  InspectorTab,
  InstanceKind,
  InstanceState,
  RecipeMeta,
  RunResult,
  TimelineKind,
} from './types';

export const PANEL_WIDTH = 400;
export const MOCK_CLIENT_HEADER = 'x-mock-client';
export const FLOATING_INSTANCE = 'floating';
export const DEFAULT_FLOATING_KEY = 'default';
const EMBEDDED_PREFIX = 'embedded:';
const MOCK_API_PATH = 'mock-agui/api/';
const CLIENT_ID_STORAGE_KEY = 'ai-blueking-docs:mock-client';
const ATTACH_TIMEOUT_MS = 10_000;

export type InstanceExpose = AIBluekingExpose | ChatBotExpose;

/** 配方可注册的请求作用域（如 scoped-request-options 片段）；宿主的 requestOptions 委托给它 */
export interface RequestScope {
  requestOptions: { headers: () => Record<string, string>; data: () => Record<string, unknown> };
  getActive(): { headers?: () => Record<string, string> } | undefined;
}

export type DemoComponentEvent =
  | 'show'
  | 'close'
  | 'send-message'
  | 'receive-start'
  | 'receive-end'
  | 'stop'
  | 'shortcut-click'
  | 'session-initialized'
  | 'new-chat-created'
  | 'sdk-error'
  | 'agent-info-loaded'
  | 'rename'
  | 'session-switched'
  | 'error'
  | 'update:asideCollapsed';

export interface DemoRuntimeState {
  backendMode: BackendMode;
  /** 最近一次运行或交互的配方；请求与面板内操作归入它 */
  activeRecipe: string;
  activeStep: Record<string, string | null>;
  inspectorTab: Record<string, InspectorTab>;
  /** 全局重建计数：重置演示 / 切换后端时所有实例重建 */
  instanceKey: number;
  registered: string[];
  recipeKinds: Record<string, InstanceKind>;
  fetchHooked: boolean;
  instances: Record<string, InstanceState>;
  /** 当前持有浮窗配置的配方 */
  floatingOwner: string;
  floatingConfigKey: string;
  floatingKey: number;
  floatingProps: Record<string, unknown>;
  floatingSlots: Record<string, FloatingSlotRender>;
  floatingDock: 'left' | 'right';
  floatingWidth: number;
  /** 停靠左侧时面板左上角 x */
  floatingLeft: number;
}

export interface FloatingLayout {
  dock?: 'left' | 'right';
  width?: number;
  left?: number;
}

export interface DemoRuntime {
  state: DemoRuntimeState;
  recorder: DemoRecorder;
  canUseReal: boolean;
  apiUrl: ComputedRef<string>;
  hasFloating: ComputedRef<boolean>;
  requestOptions: { headers: () => Record<string, string>; data: () => Record<string, unknown> };
  /** 某个实例专用的 requestOptions：Mock 模式下附带实例标识，便于请求归属 */
  requestOptionsFor(instanceId: string): { headers: () => Record<string, string>; data: () => Record<string, unknown> };
  /** 实例级附加请求头（如故障注入 x-mock-fault）；传空对象清除 */
  setInstanceHeaders(instanceId: string, headers: Record<string, string>): void;
  register(id: string, meta: RecipeMeta): void;
  unregister(id: string): void;
  instanceIdOf(recipeId: string): string;
  instanceState(instanceId: string): InstanceState;
  getInstance<E extends InstanceExpose = AIBluekingExpose>(instanceId: string): E | undefined;
  attach(instanceId: string, expose: InstanceExpose | undefined): void;
  useRequestScope(scope: RequestScope): void;
  run<T, E extends InstanceExpose = AIBluekingExpose>(
    id: string,
    step: string,
    fn: (ai: E) => Promise<T> | T,
  ): Promise<RunResult<T>>;
  updateFloatingConfig(id: string, config: FloatingConfig): void;
  setFloatingLayout(layout: FloatingLayout): void;
  markActive(id: string): void;
  selectStep(id: string, step: string | null): void;
  openTab(id: string, tab: InspectorTab): void;
  setBackendMode(mode: BackendMode): void;
  reset(): void;
  logEvent(kind: TimelineKind, text: string, recipeId?: string): void;
  handleComponentEvent(instanceId: string, name: DemoComponentEvent, payload?: unknown): void;
  /** 订阅组件事件（如配方需要 sdk-error 负载渲染业务提示）；返回取消订阅函数 */
  onComponentEvent(listener: ComponentEventListener): () => void;
  ensureComponentStyles(): Promise<void>;
}

export type ComponentEventListener = (instanceId: string, name: DemoComponentEvent, payload: unknown) => void;

const errorText = (e: unknown): string => (e instanceof Error ? e.message : String(e));

const withTrailingSlash = (url: string): string => (url.endsWith('/') ? url : `${url}/`);

const createClientId = (): string => `c${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36)}`;

const emptyInstanceState = (): InstanceState => ({ session: 'none', sessionName: '', generating: false, panelOpen: false });

function createRuntime(): DemoRuntime {
  const realUrl = getRuntimeGlobal('BK_AIDEV_API_URL');
  const state = reactive<DemoRuntimeState>({
    backendMode: 'mock',
    activeRecipe: '',
    activeStep: {},
    inspectorTab: {},
    instanceKey: 0,
    registered: [],
    recipeKinds: {},
    fetchHooked: false,
    instances: {},
    floatingOwner: '',
    floatingConfigKey: DEFAULT_FLOATING_KEY,
    floatingKey: 0,
    floatingProps: {},
    floatingSlots: markRaw({}),
    floatingDock: 'right',
    floatingWidth: PANEL_WIDTH,
    floatingLeft: 0,
  });
  const recorder = createDemoRecorder();
  const exposes = shallowReactive(new Map<string, InstanceExpose>());
  const pendingShows = reactive<Record<string, number>>({});
  const scopes = new Map<string, EffectScope>();
  const waiters = new Map<string, (() => void)[]>();
  const floatingConfigs = new Map<string, FloatingConfig>();
  const requestRecipe = new Map<number, string>();
  const loggedErrors = new WeakSet<object>();
  const eventListeners = new Set<ComponentEventListener>();
  let scope: RequestScope | undefined;
  let clientId = '';
  let uninstallFetch: (() => void) | undefined;
  let stylesPromise: Promise<void> | undefined;

  const getClientId = (): string => {
    if (clientId) return clientId;
    try {
      clientId = sessionStorage.getItem(CLIENT_ID_STORAGE_KEY) || createClientId();
      sessionStorage.setItem(CLIENT_ID_STORAGE_KEY, clientId);
    } catch {
      clientId = createClientId();
    }
    return clientId;
  };

  const rotateClientId = () => {
    clientId = createClientId();
    try {
      sessionStorage.setItem(CLIENT_ID_STORAGE_KEY, clientId);
    } catch {
      /* sessionStorage 不可用时仅保留内存值 */
    }
  };

  const apiUrl = computed(() =>
    state.backendMode === 'real' && realUrl ? withTrailingSlash(realUrl) : `${import.meta.env.BASE_URL}${MOCK_API_PATH}`,
  );

  const hasFloating = computed(() => state.registered.some(id => state.recipeKinds[id] === 'floating'));

  const instanceIdOf = (recipeId: string): string => {
    const kind = state.recipeKinds[recipeId];
    if (kind === 'floating') return FLOATING_INSTANCE;
    if (kind === 'embedded') return `${EMBEDDED_PREFIX}${recipeId}`;
    return '';
  };

  const instanceState = (instanceId: string): InstanceState => {
    if (!state.instances[instanceId]) state.instances[instanceId] = emptyInstanceState();
    return state.instances[instanceId];
  };

  /** 浮窗事件归给持有浮窗的配方，没有则归给页面第一个浮窗配方 */
  const floatingTarget = (): string =>
    state.floatingOwner || state.registered.find(id => state.recipeKinds[id] === 'floating') || '';

  const recipeOfInstance = (instanceId: string): string =>
    instanceId === FLOATING_INSTANCE ? floatingTarget() : instanceId.slice(EMBEDDED_PREFIX.length);

  const logEvent = (kind: TimelineKind, text: string, recipeId?: string) => {
    const id = recipeId || state.activeRecipe || state.registered[0] || '';
    if (id) recorder.addEvent(id, kind, text);
  };

  const watchInstance = (instanceId: string, expose: InstanceExpose) => {
    const s = instanceState(instanceId);
    const effect = effectScope();
    effect.run(() => {
      watchEffect(() => {
        const helper = expose.getChatHelper();
        const current = helper?.session.current.value;
        s.sessionName = current?.sessionName ?? '';
        s.session = (pendingShows[instanceId] ?? 0) > 0 ? 'loading' : current?.sessionCode ? 'ready' : 'none';
        s.generating = !!helper?.agent.isChatting.value;
      });
    });
    scopes.set(instanceId, effect);
  };

  const attach = (instanceId: string, expose: InstanceExpose | undefined) => {
    if (exposes.get(instanceId) === expose) return;
    scopes.get(instanceId)?.stop();
    scopes.delete(instanceId);
    if (!expose) {
      exposes.delete(instanceId);
      Object.assign(instanceState(instanceId), emptyInstanceState());
      return;
    }
    exposes.set(instanceId, expose);
    watchInstance(instanceId, expose);
    const pending = waiters.get(instanceId) ?? [];
    waiters.delete(instanceId);
    pending.forEach(resolve => resolve());
  };

  const waitForAttach = (instanceId: string): Promise<boolean> => {
    if (exposes.has(instanceId)) return Promise.resolve(true);
    return new Promise(resolve => {
      const timer = setTimeout(() => resolve(false), ATTACH_TIMEOUT_MS);
      const list = waiters.get(instanceId) ?? [];
      list.push(() => {
        clearTimeout(timer);
        resolve(true);
      });
      waiters.set(instanceId, list);
    });
  };

  /** 记录片段对 expose 的调用，片段本身保持干净 */
  const instrument = <E extends InstanceExpose>(ai: E, instanceId: string, recipeId: string): E =>
    new Proxy(ai, {
      get(target, prop, receiver) {
        const value: unknown = Reflect.get(target, prop, receiver);
        if (typeof value !== 'function' || typeof prop !== 'string' || prop === 'getChatHelper') return value;
        return (...args: unknown[]) => {
          recorder.addEvent(recipeId, 'call', describeCall(prop, args));
          const isShow = prop === 'show' || prop === 'switchSession';
          if (isShow) pendingShows[instanceId] = (pendingShows[instanceId] ?? 0) + 1;
          const settle = () => {
            if (isShow) pendingShows[instanceId] = Math.max(0, (pendingShows[instanceId] ?? 1) - 1);
          };
          let result: unknown;
          try {
            result = (value as (...a: unknown[]) => unknown).apply(target, args);
          } catch (e) {
            settle();
            recorder.addEvent(recipeId, 'error', `${prop}() 抛出：${errorText(e)}`);
            if (e && typeof e === 'object') loggedErrors.add(e);
            throw e;
          }
          if (result instanceof Promise) {
            return result.then(
              resolved => {
                settle();
                recorder.addEvent(
                  recipeId,
                  'resolve',
                  prop === 'show' ? 'show() resolved · 会话已就绪，可安全调用其他方法' : `${prop}() resolved`,
                );
                return resolved;
              },
              (e: unknown) => {
                settle();
                recorder.addEvent(recipeId, 'error', `${prop}() rejected：${errorText(e)}`);
                if (e && typeof e === 'object') loggedErrors.add(e);
                throw e;
              },
            );
          }
          settle();
          return result;
        };
      },
    });

  const resetFloating = () => {
    state.floatingOwner = '';
    state.floatingConfigKey = DEFAULT_FLOATING_KEY;
    state.floatingProps = {};
    state.floatingSlots = markRaw({});
    state.floatingDock = 'right';
    state.floatingWidth = PANEL_WIDTH;
    state.floatingLeft = 0;
  };

  interface EnsureResult {
    ok: boolean;
    remounted: boolean;
    error?: string;
  }

  let floatingQueue: Promise<unknown> = Promise.resolve();

  /** 串行执行，避免配置台推送与配方运行同时触发两次重新挂载 */
  const ensureFloating = (id: string): Promise<EnsureResult> => {
    const next = floatingQueue.then(() => doEnsureFloating(id));
    floatingQueue = next.catch(() => undefined);
    return next;
  };

  /** 让浮窗使用该配方的配置；配置不同则重新挂载并等待新实例就绪 */
  const doEnsureFloating = async (id: string): Promise<EnsureResult> => {
    const config = floatingConfigs.get(id);
    const targetKey = config?.key ?? DEFAULT_FLOATING_KEY;
    state.floatingOwner = id;
    if (targetKey === state.floatingConfigKey) {
      const ready = await waitForAttach(FLOATING_INSTANCE);
      return ready ? { ok: true, remounted: false } : { ok: false, remounted: false, error: '小鲸实例加载超时，请刷新页面重试' };
    }
    const wasOpen = instanceState(FLOATING_INSTANCE).panelOpen;
    state.floatingConfigKey = targetKey;
    state.floatingProps = { ...(config?.props ?? {}) };
    state.floatingSlots = markRaw({ ...(config?.slots ?? {}) });
    state.floatingDock = 'right';
    state.floatingWidth = typeof config?.props.defaultWidth === 'number' ? config.props.defaultWidth : PANEL_WIDTH;
    attach(FLOATING_INSTANCE, undefined);
    state.floatingKey += 1;
    recorder.addEvent(id, 'mount', targetKey === DEFAULT_FLOATING_KEY ? '按默认配置重新挂载小鲸' : '按本配方配置重新挂载小鲸');
    if (!(await waitForAttach(FLOATING_INSTANCE))) {
      return { ok: false, remounted: true, error: '小鲸重新挂载超时，请点击「重置演示」' };
    }
    const ai = exposes.get(FLOATING_INSTANCE) as AIBluekingExpose | undefined;
    if (wasOpen && ai) await instrument(ai, FLOATING_INSTANCE, id).show();
    return { ok: true, remounted: true };
  };

  const requestOptions = {
    headers: (): Record<string, string> => ({
      ...(state.backendMode === 'mock' ? { [MOCK_CLIENT_HEADER]: getClientId() } : {}),
      ...(scope?.requestOptions.headers() ?? {}),
    }),
    data: (): Record<string, unknown> => scope?.requestOptions.data() ?? {},
  };

  const instanceHeaders = reactive<Record<string, Record<string, string>>>({});

  const requestOptionsFor = (instanceId: string) => ({
    headers: (): Record<string, string> => ({
      ...requestOptions.headers(),
      ...(state.backendMode === 'mock' ? { [DEMO_INSTANCE_HEADER]: instanceId } : {}),
      ...(instanceHeaders[instanceId] ?? {}),
    }),
    data: requestOptions.data,
  });

  const fetchHooks = (): FetchRecordHooks => ({
    getBase: () => new URL(apiUrl.value, window.location.href).href,
    onRequest: info => {
      const fromHeader = info.instance ? recipeOfInstance(info.instance) : '';
      const recipeId = (fromHeader && state.registered.includes(fromHeader) ? fromHeader : '') || state.activeRecipe || floatingTarget() || state.registered[0];
      if (!recipeId) return undefined;
      const active = Object.keys(scope?.getActive()?.headers?.() ?? {}).map(k => k.toLowerCase());
      const injectedKeys = Object.keys(info.headers).filter(k => active.includes(k.toLowerCase()));
      const id = recorder.addRequest(recipeId, { ...info, injectedKeys, sse: false, status: null });
      requestRecipe.set(id, recipeId);
      return id;
    },
    onResponse: (handle, info) => {
      const recipeId = requestRecipe.get(handle);
      if (recipeId) recorder.updateRequest(recipeId, handle, info);
      requestRecipe.delete(handle);
    },
  });

  const reset = () => {
    recorder.clear();
    state.activeRecipe = '';
    state.activeStep = {};
    for (const id of state.registered) state.inspectorTab[id] = 'code';
    for (const key of Object.keys(pendingShows)) pendingShows[key] = 0;
    requestRecipe.clear();
    for (const key of Object.keys(instanceHeaders)) delete instanceHeaders[key];
    for (const instanceId of [...exposes.keys()]) attach(instanceId, undefined);
    resetFloating();
    if (state.backendMode === 'mock') rotateClientId();
    state.instanceKey += 1;
  };

  const eventText = (name: DemoComponentEvent, payload: unknown): { kind: TimelineKind; text: string } => {
    switch (name) {
      case 'show':
        return { kind: 'event', text: '@show' };
      case 'close':
        return { kind: 'event', text: '@close' };
      case 'send-message':
        return { kind: 'event', text: `@send-message ${describeArg(payload)}` };
      case 'receive-start':
        return { kind: 'stream', text: '@receive-start · 开始接收流式回复' };
      case 'receive-end':
        return { kind: 'stream', text: '@receive-end · 回复完成' };
      case 'stop':
        return { kind: 'stream', text: '@stop · 已停止生成' };
      case 'shortcut-click':
        return { kind: 'event', text: `@shortcut-click ${describeArg((payload as { shortcut?: unknown } | undefined)?.shortcut)}` };
      case 'session-initialized':
        return { kind: 'event', text: '@session-initialized' };
      case 'agent-info-loaded':
        return { kind: 'event', text: '@agent-info-loaded' };
      case 'new-chat-created': {
        const session = payload as { sessionName?: string; sessionCode?: string } | undefined;
        return { kind: 'event', text: `@new-chat-created「${session?.sessionName || session?.sessionCode || ''}」` };
      }
      case 'session-switched': {
        const session = payload as { sessionName?: string } | null | undefined;
        return { kind: 'event', text: `@session-switched「${session?.sessionName ?? ''}」` };
      }
      case 'rename':
        return { kind: 'event', text: `@rename ${describeArg(payload)}` };
      case 'update:asideCollapsed':
        return { kind: 'event', text: `update:asideCollapsed → ${String(payload)}` };
      case 'error':
        return { kind: 'error', text: `@error ${errorText(payload)}` };
      case 'sdk-error': {
        const p = payload as { apiName?: string; error?: unknown; message?: string } | undefined;
        return { kind: 'error', text: `@sdk-error ${p?.apiName ?? ''}：${p?.message ?? errorText(p?.error)}` };
      }
    }
  };

  return {
    state,
    recorder,
    canUseReal: !!realUrl,
    apiUrl,
    hasFloating,
    requestOptions,
    requestOptionsFor,
    setInstanceHeaders(instanceId, headers) {
      instanceHeaders[instanceId] = { ...headers };
    },
    register(id, meta) {
      if (!state.registered.includes(id)) state.registered.push(id);
      state.recipeKinds[id] = meta.instance;
      if (meta.floatingConfig) floatingConfigs.set(id, meta.floatingConfig);
      if (!state.inspectorTab[id]) state.inspectorTab[id] = 'code';
      recorder.get(id);
      const instanceId = instanceIdOf(id);
      if (instanceId) instanceState(instanceId);
      if (!uninstallFetch && typeof window !== 'undefined') {
        uninstallFetch = installFetchRecorder(fetchHooks());
        state.fetchHooked = true;
      }
    },
    unregister(id) {
      const instanceId = instanceIdOf(id);
      state.registered = state.registered.filter(r => r !== id);
      delete state.recipeKinds[id];
      floatingConfigs.delete(id);
      if (state.activeRecipe === id) state.activeRecipe = '';
      if (instanceId.startsWith(EMBEDDED_PREFIX)) attach(instanceId, undefined);
      if (!hasFloating.value) resetFloating();
      else if (state.floatingOwner === id) state.floatingOwner = '';
      if (state.registered.length === 0) {
        uninstallFetch?.();
        uninstallFetch = undefined;
        state.fetchHooked = false;
      }
    },
    instanceIdOf,
    instanceState,
    getInstance<E extends InstanceExpose = AIBluekingExpose>(instanceId: string) {
      return exposes.get(instanceId) as E | undefined;
    },
    attach,
    useRequestScope(next) {
      scope = next;
    },
    async run<T, E extends InstanceExpose = AIBluekingExpose>(
      id: string,
      step: string,
      fn: (ai: E) => Promise<T> | T,
    ): Promise<RunResult<T>> {
      state.activeRecipe = id;
      state.activeStep[id] = step;
      let remounted = false;
      if (state.recipeKinds[id] === 'floating') {
        const ensured = await ensureFloating(id);
        remounted = ensured.remounted;
        if (!ensured.ok) {
          recorder.addEvent(id, 'error', ensured.error ?? '小鲸实例不可用');
          return { ok: false, error: ensured.error, remounted };
        }
      }
      const instanceId = instanceIdOf(id);
      const ai = instanceId ? (exposes.get(instanceId) as E | undefined) : undefined;
      if (!ai) {
        const error = '小鲸实例尚未就绪，请稍候再试';
        recorder.addEvent(id, 'error', error);
        return { ok: false, error, remounted };
      }
      try {
        return { ok: true, value: await fn(instrument(ai, instanceId, id)), remounted };
      } catch (e) {
        if (!(e && typeof e === 'object' && loggedErrors.has(e))) recorder.addEvent(id, 'error', errorText(e));
        return { ok: false, error: errorText(e), remounted };
      }
    },
    updateFloatingConfig(id, config) {
      floatingConfigs.set(id, config);
      if (state.floatingOwner === id && config.key !== state.floatingConfigKey) void ensureFloating(id);
    },
    setFloatingLayout(layout) {
        if (layout.dock) state.floatingDock = layout.dock;
      if (layout.width) state.floatingWidth = layout.width;
      if (layout.left !== undefined) state.floatingLeft = layout.left;
    },
    markActive(id) {
      if (id) state.activeRecipe = id;
    },
    selectStep(id, step) {
      state.activeStep[id] = step;
    },
    openTab(id, tab) {
      state.inspectorTab[id] = tab;
    },
    setBackendMode(mode) {
      if (mode === state.backendMode || (mode === 'real' && !realUrl)) return;
      state.backendMode = mode;
      reset();
    },
    reset,
    logEvent,
    handleComponentEvent(instanceId, name, payload) {
      if (instanceId === FLOATING_INSTANCE && (name === 'show' || name === 'close')) {
        instanceState(FLOATING_INSTANCE).panelOpen = name === 'show';
      }
      const { kind, text } = eventText(name, payload);
      logEvent(kind, text, recipeOfInstance(instanceId));
      eventListeners.forEach(listener => listener(instanceId, name, payload));
    },
    onComponentEvent(listener) {
      eventListeners.add(listener);
      return () => eventListeners.delete(listener);
    },
    ensureComponentStyles() {
      if (!stylesPromise) {
        stylesPromise = import('@blueking/ai-blueking/dist/vue3/style.css').then(() => undefined);
      }
      return stylesPromise;
    },
  };
}

let runtime: DemoRuntime | undefined;

/** 模块级单例：同一页面的所有配方与宿主共享 */
export function useDemoRuntime(): DemoRuntime {
  if (!runtime) runtime = createRuntime();
  return runtime;
}
