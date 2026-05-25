import fs from 'node:fs';
import type { Context, Middleware } from 'koa';
import send from 'koa-send';

import {
  createDocsAssetService,
  getDefaultStaticDir,
  warmCache,
  type DocsAssetServiceOptions,
} from './docs-asset-service';

export type DocsMiddlewareOptions = Omit<DocsAssetServiceOptions, 'basePath'> & {
  /** 运行时 base 路径；未指定时从 koa-mount 的 ctx.mountPath 推导 */
  basePath?: string;
};

function resolveBasePathFromCtx(ctx: Context): string {
  const mountPath = (ctx as Context & { mountPath?: string }).mountPath;
  if (mountPath) {
    return mountPath.endsWith('/') ? mountPath.slice(0, -1) : mountPath;
  }
  return '/';
}

function applyResultToCtx(ctx: Context, result: ReturnType<ReturnType<typeof createDocsAssetService>['handleGet']>): boolean {
  if (result.kind === 'forbidden') {
    ctx.status = 403;
    ctx.body = 'Forbidden';
    return true;
  }
  if (result.kind === 'not_found') {
    ctx.status = 404;
    ctx.body = 'Not Found';
    return true;
  }
  if (result.kind === 'file') {
    return false;
  }
  ctx.status = result.status;
  ctx.set('Content-Type', result.contentType);
  ctx.set('Cache-Control', result.cacheControl);
  if (result.extraHeaders) {
    for (const [k, v] of Object.entries(result.extraHeaders)) {
      ctx.set(k, v);
    }
  }
  ctx.body = result.body;
  return true;
}

/**
 * 创建文档站 Koa 中间件（薄适配层，内部使用 DocsAssetService）。
 */
export function createDocsMiddleware(options: DocsMiddlewareOptions = {}): Middleware {
  const staticDir = options.staticDir || getDefaultStaticDir();
  const globals = options.globals || {};
  const contentCache = new Map<string, string>();
  if (fs.existsSync(staticDir)) {
    warmCache(staticDir, contentCache);
  }

  return async (ctx: Context) => {
    if (ctx.method !== 'GET' && ctx.method !== 'HEAD') {
      return;
    }

    const basePath = (options.basePath ?? resolveBasePathFromCtx(ctx)).replace(/\/$/, '') || '/';
    const service = createDocsAssetService({ staticDir, basePath, globals, contentCache });
    const result = service.handleGet(ctx.path || '/');

    if (result.kind === 'file') {
      try {
        await send(ctx, ctx.path || '/', {
          root: staticDir,
          maxAge: 365 * 24 * 60 * 60 * 1000,
          immutable: true,
          gzip: true,
        });
      } catch {
        /* fall through */
      }
      return;
    }

    applyResultToCtx(ctx, result);
  };
}

export { warmCache } from './docs-asset-service';
