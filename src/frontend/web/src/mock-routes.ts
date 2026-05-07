import type { Context } from 'koa';
import Router from '@koa/router';

function ok(data: unknown) {
  return { code: 0, data, message: 'success' };
}

function sseLine(obj: unknown) {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

function pushSse(res: Context['res'], obj: unknown) {
  if (res.writableEnded) return false;
  res.write(sseLine(obj));
  return true;
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function disableNagleIfPossible(res: Context['res']) {
  const socket = res.socket;
  if (socket && typeof socket.setNoDelay === 'function') {
    socket.setNoDelay(true);
  }
}

const store = {
  lastUserText: Object.create(null) as Record<string, string>,
  messageIdSeq: 1,
};

/**
 * 创建 Mock AG-UI API Koa 路由。
 * 用于文档中的在线 Demo，提供 REST + SSE 流式对话模拟。
 */
export function createMockAguiRouter(): Router.Middleware {
  const router = new Router();

  router.post('/session_content/', (ctx: Context) => {
    const body = (ctx.request as any).body || {};
    const sessionCode = (body as Record<string, unknown>).session_code;
    if (!sessionCode) {
      ctx.status = 400;
      ctx.body = { code: 1, data: null, message: 'session_code required' };
      return;
    }
    const id = String(store.messageIdSeq++);
    const saved = {
      ...body,
      id,
      message_id: id,
      session_code: sessionCode,
      status: (body as Record<string, unknown>).status || 'complete',
    };
    if ((body as Record<string, unknown>).role === 'user') {
      const c = (body as Record<string, unknown>).content;
      store.lastUserText[sessionCode as string] = typeof c === 'string' ? c : JSON.stringify(c ?? '');
    }
    ctx.body = ok(saved);
  });

  router.post('/session_content/batch_delete/', (ctx: Context) => {
    const body = (ctx.request as any).body || {};
    const ids = (body.ids as unknown[]) || [];
    ctx.body = ok(ids.length);
  });

  router.post('/session_content/stop/', (ctx: Context) => {
    ctx.body = ok(null);
  });

  router.get('/session_feedback/reasons/', (ctx: Context) => {
    ctx.body = ok(['准确有用', '解释清晰', '其他']);
  });

  router.post('/session_feedback/', (ctx: Context) => {
    ctx.body = ok({ saved: true });
  });

  router.post('/chat_completion/', async (ctx: Context) => {
    const body = (ctx.request as any).body || {};
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

    const res = ctx.res;
    ctx.set('Content-Type', 'text/event-stream; charset=utf-8');
    ctx.set('Cache-Control', 'no-cache, no-transform');
    ctx.set('Connection', 'keep-alive');
    ctx.set('X-Accel-Buffering', 'no');
    ctx.respond = false; // bypass Koa's response handling for SSE

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
        try { res.end(); } catch (_) {}
      }
    }
  });

  return router.routes();
}
