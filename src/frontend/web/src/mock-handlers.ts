import type { ServerResponse } from 'node:http';

function ok(data: unknown) {
  return { code: 0, data, message: 'success' };
}

function sseLine(obj: unknown) {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

function pushSse(res: ServerResponse, obj: unknown) {
  if (res.writableEnded) return false;
  res.write(sseLine(obj));
  return true;
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function disableNagleIfPossible(res: ServerResponse) {
  const socket = res.socket;
  if (socket && typeof socket.setNoDelay === 'function') {
    socket.setNoDelay(true);
  }
}

const store = {
  lastUserText: Object.create(null) as Record<string, string>,
  messageIdSeq: 1,
};

export function mockSessionContent(body: Record<string, unknown>) {
  const sessionCode = body.session_code;
  if (!sessionCode) {
    return { status: 400, json: { code: 1, data: null, message: 'session_code required' } };
  }
  const id = String(store.messageIdSeq++);
  const saved = {
    ...body,
    id,
    message_id: id,
    session_code: sessionCode,
    status: body.status || 'complete',
  };
  if (body.role === 'user') {
    const c = body.content;
    store.lastUserText[String(sessionCode)] = typeof c === 'string' ? c : JSON.stringify(c ?? '');
  }
  return { status: 200, json: ok(saved) };
}

export function mockSessionContentBatchDelete(body: Record<string, unknown>) {
  const ids = (body.ids as unknown[]) || [];
  return { status: 200, json: ok(ids.length) };
}

export function mockSessionContentStop() {
  return { status: 200, json: ok(null) };
}

export function mockSessionFeedbackReasons() {
  return { status: 200, json: ok(['准确有用', '解释清晰', '其他']) };
}

export function mockSessionFeedback() {
  return { status: 200, json: ok({ saved: true }) };
}

export async function handleMockChatCompletion(
  body: Record<string, unknown>,
  res: ServerResponse,
): Promise<void> {
  const sessionCode = (body.session_code as string) || 'atomic-stream-demo';
  const runId = Date.now();
  const threadId = `thread-${sessionCode}-${runId}`;
  const userLine = store.lastUserText[sessionCode] || '';
  const messageId = `mock-asst-${runId}`;

  const reply = [
    '【Mock 流式】这里模拟较慢的 AG-UI 文本通道。',
    '',
    '推荐事件顺序：RUN_STARTED → TEXT_MESSAGE_START → 多条 TEXT_MESSAGE_CHUNK → TEXT_MESSAGE_END → RUN_FINISHED。',
    '',
    'DevTools 的 EventStream 面板会按**到达顺序**追加行；若仍像「一闪而过」，多半是整段响应在极短时间内收完，可拉大下方 delay 或看 Timing 里的 TTFB / Content Download 分布。',
    '',
    '接入真实 Agent 时，把同样格式的 SSE 挂到网关即可；chat-helper 的 FetchClient 按行解析 data: JSON。',
    '',
    userLine ? `你说：${userLine.slice(0, 200)}${userLine.length > 200 ? '…' : ''}` : '（当前无用户句柄，仅演示固定文案。）',
    '',
    '—— 以上为 Mock 生成的较长正文，用于多段 TEXT_MESSAGE_CHUNK。 ——',
  ].join('\n');

  const PAUSE_AFTER_RUN_STARTED = 160;
  const PAUSE_AFTER_TEXT_START = 130;
  const PAUSE_PER_CHUNK = 95;
  const PAUSE_AFTER_TEXT_END = 120;
  const PAUSE_BEFORE_FINISHED = 100;
  const chunkSize = 18;

  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  try {
    disableNagleIfPossible(res);

    pushSse(res, { type: 'RUN_STARTED', runId, threadId });
    await delay(PAUSE_AFTER_RUN_STARTED);

    pushSse(res, { type: 'TEXT_MESSAGE_START', messageId, role: 'assistant' });
    await delay(PAUSE_AFTER_TEXT_START);

    for (let i = 0; i < reply.length; i += chunkSize) {
      const delta = reply.slice(i, i + chunkSize);
      pushSse(res, { type: 'TEXT_MESSAGE_CHUNK', messageId, delta, role: 'assistant' });
      await delay(PAUSE_PER_CHUNK);
    }

    pushSse(res, { type: 'TEXT_MESSAGE_END', messageId });
    await delay(PAUSE_AFTER_TEXT_END);

    pushSse(res, { type: 'RUN_FINISHED', runId, threadId });
    await delay(PAUSE_BEFORE_FINISHED);
  } catch (e) {
    if (!res.headersSent) {
      const msg = e instanceof Error ? e.message : String(e);
      res.statusCode = 500;
      res.end(JSON.stringify({ code: 1, data: null, message: msg }));
      return;
    }
  } finally {
    if (!res.writableEnded) {
      try {
        res.end();
      } catch {
        /* ignore */
      }
    }
  }
}

export type MockJsonResult = { status: number; json: unknown };

/**
 * 根据 method + path 分发 Mock AG-UI 请求（path 为挂载点下的相对路径，如 /session_content/）。
 */
export async function dispatchMockAguiRequest(
  method: string,
  relativePath: string,
  body: Record<string, unknown>,
  res: ServerResponse,
): Promise<{ handled: boolean; json?: MockJsonResult }> {
  const normalizedPath = relativePath.endsWith('/') ? relativePath : `${relativePath}/`;
  const m = method.toUpperCase();

  if (m === 'POST' && normalizedPath === '/chat_completion/') {
    await handleMockChatCompletion(body, res);
    return { handled: true };
  }

  if (m === 'POST' && normalizedPath === '/session_content/') {
    const result = mockSessionContent(body);
    return { handled: true, json: result };
  }
  if (m === 'POST' && normalizedPath === '/session_content/batch_delete/') {
    return { handled: true, json: mockSessionContentBatchDelete(body) };
  }
  if (m === 'POST' && normalizedPath === '/session_content/stop/') {
    return { handled: true, json: mockSessionContentStop() };
  }
  if (m === 'GET' && normalizedPath === '/session_feedback/reasons/') {
    return { handled: true, json: mockSessionFeedbackReasons() };
  }
  if (m === 'POST' && normalizedPath === '/session_feedback/') {
    return { handled: true, json: mockSessionFeedback() };
  }

  return { handled: false };
}
