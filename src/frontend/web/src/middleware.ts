import fs from 'node:fs';
import path from 'node:path';
import type { Context, Middleware } from 'koa';
import send from 'koa-send';

const DOCS_BASE_PLACEHOLDER = '__DOCS_BASE__';

/** Static file extensions — served directly, no rewriting */
const STATIC_EXTS = new Set([
  '.woff', '.woff2', '.ttf', '.eot',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
  '.mp4', '.webm', '.mp3', '.wav',
  '.json', '.map', '.txt', '.xml',
]);

/** File extensions that may contain __DOCS_BASE__/ placeholder and need rewriting */
const REPLACEABLE_EXTS = new Set(['.html', '.js', '.css']);

export interface DocsMiddlewareOptions {
  /** 文档站的静态文件目录，默认为包内的 dist/static/ */
  staticDir?: string;
  /** 需要注入到 HTML <head> 的全局变量 */
  globals?: Record<string, string>;
}

/**
 * 预热缓存，读取所有可替换文件（.html / .js / .css）到内存。
 * @param staticDir - 静态文件目录
 * @param cache - 实例级缓存 Map
 */
export function warmCache(staticDir: string, cache: Map<string, string>): void {
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (REPLACEABLE_EXTS.has(path.extname(entry.name).toLowerCase())) {
        cache.set(full, fs.readFileSync(full, 'utf-8'));
      }
    }
  };
  walk(staticDir);
}

function isStaticFile(p: string): boolean {
  const ext = path.extname(p).toLowerCase();
  return STATIC_EXTS.has(ext);
}

/**
 * 从请求上下文推导 koa-mount 的挂载前缀。
 * koa-mount 设置 ctx.mountPath 为挂载路径。
 */
function resolveBasePath(ctx: Context): string {
  // koa-mount sets ctx.mountPath
  const mountPath = (ctx as any).mountPath;
  if (mountPath) {
    return mountPath.endsWith('/') ? mountPath : mountPath + '/';
  }
  // Fallback: no mount, use root
  return '/';
}

function buildGlobalsScript(globals: Record<string, string>): string {
  const entries = Object.entries(globals)
    .map(([k, v]) => `window.${k}=${JSON.stringify(v)};`)
    .join('');
  return `<script>${entries}</script>`;
}

/**
 * 创建文档站 Koa 中间件。
 * 挂载到任意路由后，自动将 HTML 和 JS 文件中的 __DOCS_BASE__/ 替换为实际路径。
 */
export function createDocsMiddleware(options: DocsMiddlewareOptions = {}): Middleware {
  const staticDir = options.staticDir || path.resolve(__dirname, 'static');
  const globals = options.globals || {};
  const contentCache = new Map<string, string>();

  // Pre-warm cache on startup
  if (fs.existsSync(staticDir)) {
    warmCache(staticDir, contentCache);
  }

  return async (ctx: Context) => {
    // Only handle GET/HEAD
    if (ctx.method !== 'GET' && ctx.method !== 'HEAD') return;

    const reqPath = ctx.path || '/';
    const ext = path.extname(reqPath).toLowerCase();

    // Replaceable files (.js, .html): read, replace placeholder, serve
    if (REPLACEABLE_EXTS.has(ext)) {
      let filePath = reqPath;
      if (ext === '.html') {
        filePath = reqPath === '/' ? '/index.html' : reqPath;
      }

      const fullPath = path.join(staticDir, filePath);
      const staticRoot = path.resolve(staticDir);
      if (!fullPath.startsWith(staticRoot + path.sep) && fullPath !== staticRoot) {
        ctx.status = 403;
        ctx.body = 'Forbidden';
        return;
      }

      const basePath = resolveBasePath(ctx).replace(/\/$/, '');

      let rawContent = contentCache.get(fullPath);
      if (rawContent === undefined && fs.existsSync(fullPath)) {
        rawContent = fs.readFileSync(fullPath, 'utf-8');
        contentCache.set(fullPath, rawContent);
      }

      // SPA fallback for HTML
      if (rawContent === undefined && ext === '.html') {
        const indexPath = path.join(staticDir, 'index.html');
        rawContent = contentCache.get(indexPath);
        if (rawContent === undefined && fs.existsSync(indexPath)) {
          rawContent = fs.readFileSync(indexPath, 'utf-8');
          contentCache.set(indexPath, rawContent);
        }
      }

      if (rawContent === undefined) {
        ctx.status = 404;
        ctx.body = 'Not Found';
        return;
      }

      const basePathNoSlash = basePath.replace(/^\//, '');
      const content = rawContent
        .replaceAll('/' + DOCS_BASE_PLACEHOLDER, '/' + basePathNoSlash)
        .replaceAll(DOCS_BASE_PLACEHOLDER, basePath);

      if (ext === '.html') {
        // Inject global variables if configured
        let html = content;
        if (Object.keys(globals).length > 0) {
          html = html.replace('</head>', `${buildGlobalsScript(globals)}\n</head>`);
        }
        ctx.set('Content-Type', 'text/html; charset=utf-8');
        ctx.set('Cache-Control', 'no-cache');
        ctx.body = html;
      } else if (ext === '.css') {
        ctx.set('Content-Type', 'text/css; charset=utf-8');
        ctx.set('Cache-Control', 'public, max-age=31536000, immutable');
        ctx.body = content;
      } else {
        ctx.set('Content-Type', 'application/javascript; charset=utf-8');
        ctx.set('Cache-Control', 'public, max-age=31536000, immutable');
        ctx.set('X-Content-Type-Options', 'nosniff');
        ctx.body = content;
      }
      return;
    }

    // Static assets: serve directly with long cache
    if (isStaticFile(reqPath)) {
      try {
        await send(ctx, reqPath, {
          root: staticDir,
          maxAge: 365 * 24 * 60 * 60 * 1000, // 1 year
          immutable: true,
          gzip: true,
        });
      } catch {
        // File not found, fall through
      }
      return;
    }

    // SPA fallback for paths without extension
    const indexPath = path.join(staticDir, 'index.html');
    let rawHtml = contentCache.get(indexPath);
    if (rawHtml === undefined && fs.existsSync(indexPath)) {
      rawHtml = fs.readFileSync(indexPath, 'utf-8');
      contentCache.set(indexPath, rawHtml);
    }

    if (rawHtml === undefined) {
      ctx.status = 404;
      ctx.body = 'Not Found';
      return;
    }

    const basePath = resolveBasePath(ctx).replace(/\/$/, '');
    let html = rawHtml.replaceAll(DOCS_BASE_PLACEHOLDER, basePath);

    if (Object.keys(globals).length > 0) {
      html = html.replace('</head>', `${buildGlobalsScript(globals)}\n</head>`);
    }

    ctx.set('Content-Type', 'text/html; charset=utf-8');
    ctx.set('Cache-Control', 'no-cache');
    ctx.body = html;
  };
}
