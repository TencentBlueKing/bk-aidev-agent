import type { ServerResponse } from 'node:http';

import { MOCK_AGENT_PROFILES, MOCK_LLMS, pickMockReply, type MockMessageRecord } from './mock-fixtures';
import { FLOW_PROFILE, buildNodeInfo, planFlowFrames, recordFlowOperation, taskStateOf, toActivityMessage, toTaskValue } from './mock-flow';
import {
  DEFAULT_MOCK_CLIENT_ID,
  appendMessage,
  clearStreamStopped,
  consumeStreamStopped,
  deleteMessages,
  deleteSession,
  getSession,
  lastUserMessage,
  listMessages,
  listSessions,
  markStreamStopped,
  nextMockId,
  updateMessage,
  upsertSession,
} from './mock-store';

export type MockJsonResult = { status: number; json: unknown };

export interface MockRequestContext {
  query?: Record<string, string>;
  /** 访客隔离标识，来自 x-mock-client 请求头；缺省为 anonymous */
  clientId?: string;
  /** 故障注入，来自 x-mock-fault 请求头，格式 `<target>:<kind>` */
  fault?: string;
  /** 智能体档案，由路径前缀 `~<profile>/` 解析；dispatch 内部填充 */
  profile?: string;
}

export const MOCK_FAULT_HEADER = 'x-mock-fault';

export type MockFault = 'agent_info:500' | 'session_content:500' | 'stream:run_error' | 'all:401';

const KNOWN_FAULTS: ReadonlySet<string> = new Set<MockFault>([
  'agent_info:500',
  'session_content:500',
  'stream:run_error',
  'all:401',
]);

/** 流中途报错前先推送的 chunk 数 */
const RUN_ERROR_AFTER_CHUNKS = 8;

/** 流式节奏（毫秒），测试中可置零 */
export const MOCK_STREAM_TIMING = {
  afterRunStarted: 160,
  afterTextStart: 130,
  perChunk: 60,
  afterTextEnd: 80,
  beforeFinished: 60,
  chunkSize: 6,
  /** 流程智能体节点推进间隔 */
  flowStep: 900,
};

function ok(data: unknown): MockJsonResult {
  return { status: 200, json: { code: 0, data, message: 'success' } };
}

function fail(status: number, message: string): MockJsonResult {
  return { status, json: { code: 1, data: null, message } };
}

function sseLine(obj: unknown) {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

function pushSse(res: ServerResponse, obj: unknown) {
  if (res.writableEnded || res.destroyed) return false;
  res.write(sseLine(obj));
  return true;
}

function delay(ms: number) {
  return ms > 0 ? new Promise(resolve => setTimeout(resolve, ms)) : Promise.resolve();
}

function disableNagleIfPossible(res: ServerResponse) {
  const socket = res.socket;
  if (socket && typeof socket.setNoDelay === 'function') {
    socket.setNoDelay(true);
  }
}

/** 存储隔离键：访客 + 智能体档案（默认档案保持原访客键，兼容既有数据） */
function clientOf(ctx?: MockRequestContext): string {
  const client = ctx?.clientId || DEFAULT_MOCK_CLIENT_ID;
  return ctx?.profile && ctx.profile !== 'default' ? `${client}@${ctx.profile}` : client;
}

function faultOf(ctx?: MockRequestContext): MockFault | undefined {
  return ctx?.fault && KNOWN_FAULTS.has(ctx.fault) ? (ctx.fault as MockFault) : undefined;
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : value === undefined || value === null ? '' : String(value);
}

function protocolReply(userLine: string): string {
  return [
    '【Mock 流式】这里模拟较慢的 AG-UI 文本通道。',
    '',
    '推荐事件顺序：RUN_STARTED → TEXT_MESSAGE_START → 多条 TEXT_MESSAGE_CHUNK → TEXT_MESSAGE_END → RUN_FINISHED。',
    '',
    'DevTools 的 EventStream 面板会按**到达顺序**追加行；若仍像「一闪而过」，多半是整段响应在极短时间内收完，可拉大 delay 或看 Timing 里的 TTFB / Content Download 分布。',
    '',
    '接入真实 Agent 时，把同样格式的 SSE 挂到网关即可；chat-helper 的 FetchClient 按行解析 data: JSON。',
    '',
    userLine ? `你说：${userLine.slice(0, 200)}${userLine.length > 200 ? '…' : ''}` : '（当前无用户句柄，仅演示固定文案。）',
  ].join('\n');
}

export function mockSessionContent(body: Record<string, unknown>, ctx?: MockRequestContext): MockJsonResult {
  const sessionCode = str(body.session_code);
  if (!sessionCode) {
    return fail(400, 'session_code required');
  }
  const id = nextMockId();
  const saved: MockMessageRecord = {
    ...body,
    id,
    message_id: id,
    session_code: sessionCode,
    role: str(body.role) || 'user',
    content: body.content ?? '',
    status: str(body.status) || 'complete',
    created_at: new Date().toISOString(),
  };
  appendMessage(clientOf(ctx), saved);
  return ok(saved);
}

export function mockSessionContentBatchDelete(body: Record<string, unknown>, ctx?: MockRequestContext): MockJsonResult {
  const ids = Array.isArray(body.ids) ? body.ids.map(String) : [];
  deleteMessages(clientOf(ctx), ids);
  return ok(ids.length);
}

export function mockSessionContentStop(body: Record<string, unknown> = {}, ctx?: MockRequestContext): MockJsonResult {
  const sessionCode = str(body.session_code);
  if (sessionCode) markStreamStopped(clientOf(ctx), sessionCode);
  return ok(null);
}

export function mockSessionFeedbackReasons(): MockJsonResult {
  return ok(['准确有用', '解释清晰', '其他']);
}

export function mockSessionFeedback(): MockJsonResult {
  return ok({ saved: true });
}

function startSse(res: ServerResponse) {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  disableNagleIfPossible(res);
}

/** 流程智能体：按 planFlowFrames 的帧推送，结束后把活动消息与输出写入会话 */
async function handleFlowCompletion(body: Record<string, unknown>, res: ServerResponse, ctx?: MockRequestContext): Promise<void> {
  const clientId = clientOf(ctx);
  const sessionCode = str(body.session_code) || 'flow-demo';
  const { frames, run } = planFlowFrames(clientId, sessionCode, MOCK_STREAM_TIMING.flowStep);
  let clientClosed = false;
  if (typeof res.on === 'function') {
    res.on('close', () => {
      clientClosed = true;
    });
  }
  clearStreamStopped(clientId, sessionCode);
  startSse(res);
  let outputs: string[] = [];
  try {
    for (const frame of frames) {
      await delay(frame.wait);
      if (clientClosed || consumeStreamStopped(clientId, sessionCode)) break;
      pushSse(res, frame.event);
      if (frame.event.name === 'flow_agent_end') {
        const value = frame.event.value as { task_outputs?: string[] }[];
        outputs = value.flatMap(v => v.task_outputs ?? []);
      }
    }
  } finally {
    const state = taskStateOf(run);
    const existing = listMessages(clientId, sessionCode).find(m => {
      const content = m.content as { task_id?: number }[] | undefined;
      return m.role === 'activity' && Array.isArray(content) && content[0]?.task_id === run.taskId;
    });
    if (existing) {
      updateMessage(clientId, existing.id, { content: toTaskValue(run, state) });
    } else {
      appendMessage(clientId, toActivityMessage(run, sessionCode, nextMockId(), state));
    }
    const text = outputs.join('\n');
    if (text) {
      const id = nextMockId();
      appendMessage(clientId, {
        id,
        message_id: id,
        session_code: sessionCode,
        role: 'assistant',
        content: text,
        status: 'complete',
        created_at: new Date().toISOString(),
      });
    }
    if (!res.writableEnded) {
      try {
        res.end();
      } catch {
        /* ignore */
      }
    }
  }
}

export async function handleMockChatCompletion(
  body: Record<string, unknown>,
  res: ServerResponse,
  ctx?: MockRequestContext,
): Promise<void> {
  if (ctx?.profile === FLOW_PROFILE) {
    await handleFlowCompletion(body, res, ctx);
    return;
  }
  const clientId = clientOf(ctx);
  const runError = faultOf(ctx) === 'stream:run_error';
  const sessionCode = str(body.session_code) || 'atomic-stream-demo';
  const runId = Date.now();
  const threadId = `thread-${sessionCode}-${runId}`;
  const messageId = `mock-asst-${runId}`;
  const lastUser = lastUserMessage(clientId, sessionCode);
  const reply =
    clientId === DEFAULT_MOCK_CLIENT_ID
      ? protocolReply(typeof lastUser?.content === 'string' ? lastUser.content : '')
      : pickMockReply(lastUser);
  const t = MOCK_STREAM_TIMING;

  clearStreamStopped(clientId, sessionCode);
  let clientClosed = false;
  if (typeof res.on === 'function') {
    res.on('close', () => {
      clientClosed = true;
    });
  }
  const interrupted = () => clientClosed || consumeStreamStopped(clientId, sessionCode);

  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  let sent = '';
  let stopped = false;
  try {
    disableNagleIfPossible(res);

    pushSse(res, { type: 'RUN_STARTED', runId, threadId });
    await delay(t.afterRunStarted);

    pushSse(res, { type: 'TEXT_MESSAGE_START', messageId, role: 'assistant' });
    await delay(t.afterTextStart);

    for (let i = 0, n = 0; i < reply.length; i += t.chunkSize, n += 1) {
      if (interrupted()) {
        stopped = true;
        break;
      }
      if (runError && n === RUN_ERROR_AFTER_CHUNKS) {
        pushSse(res, { type: 'RUN_ERROR', message: 'Mock：模型服务异常（x-mock-fault: stream:run_error）', code: 'MOCK_RUN_ERROR' });
        stopped = true;
        break;
      }
      const delta = reply.slice(i, i + t.chunkSize);
      sent += delta;
      pushSse(res, { type: 'TEXT_MESSAGE_CHUNK', messageId, delta, role: 'assistant' });
      await delay(t.perChunk);
    }

    if (!stopped) {
      pushSse(res, { type: 'TEXT_MESSAGE_END', messageId });
      await delay(t.afterTextEnd);
      pushSse(res, { type: 'RUN_FINISHED', runId, threadId });
      await delay(t.beforeFinished);
    }
  } catch (e) {
    if (!res.headersSent) {
      const msg = e instanceof Error ? e.message : String(e);
      res.statusCode = 500;
      res.end(JSON.stringify({ code: 1, data: null, message: msg }));
      return;
    }
  } finally {
    if (sent) {
      const id = nextMockId();
      appendMessage(clientId, {
        id,
        message_id: messageId,
        session_code: sessionCode,
        role: 'assistant',
        content: sent,
        status: stopped ? 'stop' : 'complete',
        created_at: new Date().toISOString(),
      });
    }
    if (!res.writableEnded) {
      try {
        res.end();
      } catch {
        /* ignore */
      }
    }
  }
}

type RouteHandler = (
  params: Record<string, string>,
  body: Record<string, unknown>,
  ctx: MockRequestContext,
) => MockJsonResult;

interface Route {
  method: string;
  pattern: RegExp;
  keys: string[];
  handler: RouteHandler;
}

function route(method: string, path: string, handler: RouteHandler): Route {
  const keys: string[] = [];
  const source = path.replace(/:([a-zA-Z]+)/g, (_m, key: string) => {
    keys.push(key);
    return '([^/]+)';
  });
  return { method, pattern: new RegExp(`^${source}$`), keys, handler };
}

const ROUTES: Route[] = [
  route('GET', '/agent/info/', (_p, _b, ctx) => ok(MOCK_AGENT_PROFILES[ctx.profile ?? 'default'] ?? MOCK_AGENT_PROFILES.default)),
  route('GET', '/llms/', () => ok(MOCK_LLMS)),

  route('GET', '/session/', (_p, _b, ctx) => {
    const results = listSessions(clientOf(ctx));
    return ok({ page: 1, num_pages: 1, count: results.length, results });
  }),
  route('POST', '/session/', (_p, body, ctx) =>
    ok(
      upsertSession(clientOf(ctx), {
        session_code: str(body.session_code) || undefined,
        session_name: str(body.session_name) || undefined,
        is_temporary: body.is_temporary === true,
        model: str(body.model) || undefined,
      }),
    ),
  ),
  route('POST', '/session/batch_delete/', (_p, body, ctx) => {
    const codes = Array.isArray(body.session_codes) ? body.session_codes.map(String) : [];
    return ok(codes.filter(code => deleteSession(clientOf(ctx), code)).length);
  }),
  route('GET', '/session/:code/', (p, _b, ctx) => {
    const session = getSession(clientOf(ctx), p.code);
    return session ? ok(session) : fail(404, 'session not found');
  }),
  route('PUT', '/session/:code/', (p, body, ctx) =>
    ok(
      upsertSession(clientOf(ctx), {
        session_code: p.code,
        session_name: str(body.session_name) || undefined,
        model: str(body.model) || undefined,
      }),
    ),
  ),
  route('DELETE', '/session/:code/', (p, _b, ctx) => {
    deleteSession(clientOf(ctx), p.code);
    return ok(null);
  }),
  route('POST', '/session/:code/ai_rename/', (p, _b, ctx) => {
    const first = listMessages(clientOf(ctx), p.code).find(m => m.role === 'user');
    const name = typeof first?.content === 'string' && first.content.trim() ? first.content.trim().slice(0, 12) : '新会话';
    return ok(upsertSession(clientOf(ctx), { session_code: p.code, session_name: name }));
  }),
  route('GET', '/session/:code/is_resume/', () => ok(false)),
  route('POST', '/chat_completion/:code/clear/', () => ok(null)),

  route('GET', '/session_content/content/', (_p, _b, ctx) =>
    ok(listMessages(clientOf(ctx), str(ctx.query?.session_code))),
  ),
  route('POST', '/session_content/', (_p, body, ctx) => mockSessionContent(body, ctx)),
  route('POST', '/session_content/batch_delete/', (_p, body, ctx) => mockSessionContentBatchDelete(body, ctx)),
  route('POST', '/session_content/stop/', (_p, body, ctx) => mockSessionContentStop(body, ctx)),
  route('PUT', '/session_content/:id/', (p, body, ctx) => {
    const updated = updateMessage(clientOf(ctx), p.id, body);
    return updated ? ok(updated) : fail(404, 'message not found');
  }),
  route('DELETE', '/session_content/:id/', (p, _b, ctx) => {
    deleteMessages(clientOf(ctx), [p.id]);
    return ok(null);
  }),

  route('GET', '/session_feedback/reasons/', () => mockSessionFeedbackReasons()),
  route('POST', '/session_feedback/', () => mockSessionFeedback()),
  route('POST', '/user_operation/', (_p, body, ctx) => {
    const payload = (body.payload ?? {}) as { node_id?: unknown };
    recordFlowOperation(clientOf(ctx), str(body.session_code), str(body.operation), str(payload.node_id));
    return ok(null);
  }),
  route('GET', '/flow_agent/:taskId/task_node_info/:nodeId/', p => {
    const info = buildNodeInfo(Number(p.taskId), p.nodeId);
    return info ? ok(info) : fail(404, 'node not found');
  }),
];

/**
 * 根据 method + path 分发 Mock AG-UI 请求（path 为挂载点下的相对路径，如 /session_content/）。
 */
export async function dispatchMockAguiRequest(
  method: string,
  relativePath: string,
  body: Record<string, unknown>,
  res: ServerResponse,
  ctx: MockRequestContext = {},
): Promise<{ handled: boolean; json?: MockJsonResult }> {
  const pathOnly = relativePath.split('?')[0] || '/';
  const withLeading = pathOnly.startsWith('/') ? pathOnly : `/${pathOnly}`;
  const withTrailing = withLeading.endsWith('/') ? withLeading : `${withLeading}/`;
  const profileMatch = /^\/~([a-z0-9-]+)(\/.*)$/.exec(withTrailing);
  const profile = profileMatch && MOCK_AGENT_PROFILES[profileMatch[1]] ? profileMatch[1] : 'default';
  const normalizedPath = profileMatch ? profileMatch[2] : withTrailing;
  const m = method.toUpperCase();
  ctx = { ...ctx, profile };

  const fault = faultOf(ctx);
  if (fault === 'all:401') {
    return { handled: true, json: fail(401, 'Mock：登录态失效（x-mock-fault: all:401）') };
  }
  if (fault === 'agent_info:500' && m === 'GET' && normalizedPath === '/agent/info/') {
    return { handled: true, json: fail(500, 'Mock：智能体信息服务异常（x-mock-fault: agent_info:500）') };
  }
  if (fault === 'session_content:500' && m === 'POST' && normalizedPath === '/session_content/') {
    return { handled: true, json: fail(500, 'Mock：消息写入失败（x-mock-fault: session_content:500）') };
  }

  if (m === 'POST' && normalizedPath === '/chat_completion/') {
    await handleMockChatCompletion(body, res, ctx);
    return { handled: true };
  }

  for (const r of ROUTES) {
    if (r.method !== m) continue;
    const match = r.pattern.exec(normalizedPath);
    if (!match) continue;
    const params: Record<string, string> = {};
    r.keys.forEach((key, i) => {
      params[key] = decodeURIComponent(match[i + 1]);
    });
    return { handled: true, json: r.handler(params, body, ctx) };
  }

  return { handled: false };
}
