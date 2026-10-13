import type { Context } from 'koa';
import Router from '@koa/router';

import { MOCK_FAULT_HEADER, dispatchMockAguiRequest } from './mock-handlers';
import { MOCK_CLIENT_HEADER, resolveMockClientId } from './mock-store';

/**
 * 创建 Mock AG-UI API Koa 路由（薄适配层）。
 */
export function createMockAguiRouter(): Router.Middleware {
  const router = new Router();

  router.all('/(.*)', async (ctx: Context) => {
    const body = (ctx.request as { body?: Record<string, unknown> }).body || {};
    const query = Object.fromEntries(
      Object.entries(ctx.query).map(([key, value]) => [key, Array.isArray(value) ? value[0] ?? '' : value ?? '']),
    );
    const dispatched = await dispatchMockAguiRequest(ctx.method, ctx.path || '/', body, ctx.res, {
      query,
      clientId: resolveMockClientId(ctx.get(MOCK_CLIENT_HEADER)),
      fault: ctx.get(MOCK_FAULT_HEADER) || undefined,
    });

    if (!dispatched.handled) {
      ctx.status = 404;
      ctx.body = { code: 1, data: null, message: 'Not Found' };
      return;
    }

    if (dispatched.json) {
      ctx.status = dispatched.json.status;
      ctx.body = dispatched.json.json;
      return;
    }

    // SSE 已直接写入 ctx.res
    ctx.respond = false;
  });

  return router.routes();
}
