import type { Context } from 'koa';
import Router from '@koa/router';

import { dispatchMockAguiRequest } from './mock-handlers';

/**
 * 创建 Mock AG-UI API Koa 路由（薄适配层）。
 */
export function createMockAguiRouter(): Router.Middleware {
  const router = new Router();

  const handle = async (ctx: Context) => {
    const body = ((ctx.request as { body?: Record<string, unknown> }).body) || {};
    const relativePath = ctx.path || '/';
    const dispatched = await dispatchMockAguiRequest(ctx.method, relativePath, body, ctx.res);

    if (!dispatched.handled) {
      ctx.status = 404;
      ctx.body = { code: 1, data: null, message: 'Not Found' };
      return;
    }

    if (dispatched.json) {
      ctx.status = dispatched.json.status;
      ctx.body = dispatched.json.json;
    }
  };

  router.post('/session_content/', handle);
  router.post('/session_content/batch_delete/', handle);
  router.post('/session_content/stop/', handle);
  router.get('/session_feedback/reasons/', handle);
  router.post('/session_feedback/', handle);
  router.post('/chat_completion/', handle);

  return router.routes();
}
