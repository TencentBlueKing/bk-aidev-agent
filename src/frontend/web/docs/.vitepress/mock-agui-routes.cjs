/**
 * 文档站专用 Mock：最小 REST + AG-UI SSE + 工具栏相关接口（批量删除、反馈）。
 */
const express = require('express');

function ok(data) {
  return { code: 0, data, message: 'success' };
}

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Length', Buffer.byteLength(body, 'utf8'));
  res.end(body);
}

/** @param {unknown} obj */
function sseLine(obj) {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

function pushSse(res, obj) {
  if (res.writableEnded) return false;
  res.write(sseLine(obj));
  return true;
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function disableNagleIfPossible(res) {
  const socket = res.socket;
  if (socket && typeof socket.setNoDelay === 'function') {
    socket.setNoDelay(true);
  }
}

const store = {
  lastUserText: Object.create(null),
  messageIdSeq: 1,
};

function createMockAguiRouter() {
  const router = express.Router();

  router.post('/session_content/', (req, res) => {
    const body = req.body || {};
    const sessionCode = body.session_code;
    if (!sessionCode) {
      sendJson(res, 400, { code: 1, data: null, message: 'session_code required' });
      return;
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
      store.lastUserText[sessionCode] = typeof c === 'string' ? c : JSON.stringify(c ?? '');
    }
    sendJson(res, 200, ok(saved));
  });

  /** SDK：message.deleteMessages → 仅传 user 消息的 id */
  router.post('/session_content/batch_delete/', (req, res) => {
    const ids = (req.body && req.body.ids) || [];
    sendJson(res, 200, ok(ids.length));
  });

  router.post('/session_content/stop/', (_req, res) => {
    sendJson(res, 200, ok(null));
  });

  /** SDK：getSessionFeedbackReasons */
  router.get('/session_feedback/reasons/', (req, res) => {
    void req.query.rate;
    sendJson(res, 200, ok(['准确有用', '解释清晰', '其他']));
  });

  /** SDK：postSessionFeedback */
  router.post('/session_feedback/', (_req, res) => {
    sendJson(res, 200, ok({ saved: true }));
  });

  router.post('/chat_completion/', async (req, res) => {
    const sessionCode = (req.body && req.body.session_code) || 'atomic-stream-demo';
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
        sendJson(res, 500, { code: 1, data: null, message: String(e && e.message ? e.message : e) });
        return;
      }
    } finally {
      if (!res.writableEnded) {
        try {
          res.end();
        } catch (_) {}
      }
    }
  });

  return router;
}

module.exports = { createMockAguiRouter };
