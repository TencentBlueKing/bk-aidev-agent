import type { VNode } from 'vue';

export type BackendMode = 'mock' | 'real';

export type SessionPhase = 'none' | 'loading' | 'ready';

export type InspectorTab = 'code' | 'events' | 'requests';

export type TimelineKind = 'call' | 'event' | 'resolve' | 'stream' | 'error' | 'mount';

/** 配方使用的实例：页面共享的浮窗、舞台内嵌入的 ChatBot、或不使用小鲸实例 */
export type InstanceKind = 'floating' | 'embedded' | 'none';

/** 浮窗插槽渲染函数：参数为插槽作用域 */
export type FloatingSlotRender = (scope: Record<string, unknown>) => VNode | VNode[] | string | null;

/** 浮窗配方的专属配置；key 变化即重新挂载 */
export interface FloatingConfig {
  props: Record<string, unknown>;
  /** 透传给 AIBlueking 的插槽，如 headerLeft / headerActions / codeHeader */
  slots?: Record<string, FloatingSlotRender>;
  key: string;
}

export interface RecipeMeta {
  instance: InstanceKind;
  floatingConfig?: FloatingConfig;
}

export interface InstanceState {
  session: SessionPhase;
  sessionName: string;
  generating: boolean;
  /** 仅浮窗有意义 */
  panelOpen: boolean;
}

export interface TimelineEntry {
  id: number;
  time: string;
  kind: TimelineKind;
  text: string;
}

export interface RecordedRequest {
  id: number;
  time: string;
  method: string;
  /** 相对后端前缀的路径，如 `session_content/` */
  path: string;
  query: Record<string, string> | null;
  /** 去除标准头后的请求头 */
  headers: Record<string, string>;
  /** 本次请求中由 scoped.runWith 注入的 Header 键 */
  injectedKeys: string[];
  body: unknown;
  sse: boolean;
  status: number | null;
}

export interface RecipeRecords {
  events: TimelineEntry[];
  requests: RecordedRequest[];
}

export interface FeedbackState {
  kind: 'ok' | 'err' | 'info';
  text: string;
  /** 附带「去检查器看」的跳转 */
  goto?: InspectorTab;
  gotoLabel?: string;
}

export interface RunResult<T = unknown> {
  ok: boolean;
  value?: T;
  error?: string;
  /** 本次执行前按配方配置重新挂载了浮窗 */
  remounted?: boolean;
}
