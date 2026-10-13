import type { IncomingMessage, ServerResponse } from 'node:http';

import { MOCK_FAULT_HEADER, dispatchMockAguiRequest } from './mock-handlers';
import { MOCK_CLIENT_HEADER, resolveMockClientId } from './mock-store';

type NodeRequest = IncomingMessage & { body?: unknown };

const MAX_BODY_BYTES = 256 * 1024;

function sendJson(res: ServerResponse, status: number, payload: unknown) {
  const body = JSON.stringify(payload);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Length', Buffer.byteLength(body, 'utf8'));
  res.end(body);
}

function readJsonBody(req: NodeRequest): Promise<Record<string, unknown>> {
  if (req.body && typeof req.body === 'object') {
    return Promise.resolve(req.body as Record<string, unknown>);
  }
  if (req.method === 'GET' || req.method === 'HEAD') {
    return Promise.resolve({});
  }
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks: Buffer[] = [];
    req.on('data', (chunk: Buffer) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error('payload too large'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      if (!raw) {
        resolve({});
        return;
      }
      try {
        const parsed: unknown = JSON.parse(raw);
        resolve(parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {});
      } catch {
        resolve({});
      }
    });
    req.on('error', reject);
  });
}

/**
 * Mock AG-UI 的 connect 风格中间件，可直接用于 Vite dev server（server.middlewares）与 Express。
 * 需挂载在 Mock 前缀下（如 `/mock-agui/api`），req.url 为挂载点下的相对路径；未知路由直接返回 404 JSON。
 */
export function createMockAguiNodeMiddleware() {
  return (req: NodeRequest, res: ServerResponse): void => {
    const url = new URL(req.url || '/', 'http://mock.local');
    const query = Object.fromEntries(url.searchParams.entries());
    const clientId = resolveMockClientId(req.headers[MOCK_CLIENT_HEADER]);
    const faultHeader = req.headers[MOCK_FAULT_HEADER];
    const fault = Array.isArray(faultHeader) ? faultHeader[0] : faultHeader;

    readJsonBody(req)
      .then(body => dispatchMockAguiRequest(req.method || 'GET', url.pathname, body, res, { query, clientId, fault }))
      .then(result => {
        if (!result.handled) {
          console.warn(`[mock-agui] unhandled ${req.method} ${url.pathname}`);
          sendJson(res, 404, { code: 1, data: null, message: 'Not Found' });
          return;
        }
        if (result.json && !res.writableEnded) {
          sendJson(res, result.json.status, result.json.json);
        }
      })
      .catch((err: unknown) => {
        if (res.headersSent) {
          res.end();
          return;
        }
        sendJson(res, 400, { code: 1, data: null, message: err instanceof Error ? err.message : String(err) });
      });
  };
}
