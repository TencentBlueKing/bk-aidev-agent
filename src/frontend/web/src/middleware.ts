import fs from 'node:fs';
import path from 'node:path';
import type { Context, Middleware } from 'koa';
import send from 'koa-send';

const DOCS_BASE_PLACEHOLDER = '__DOCS_BASE__/';

/** Static file extensions — served directly, no rewriting */
const STATIC_EXTS = new Set([
  '.js', '.css', '.woff', '.woff2', '.ttf', '.eot',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
  '.mp4', '.webm', '.mp3', '.wav',
  '.json', '.map', '.txt', '.xml',
]);

export interface DocsMiddlewareOptions {
  /** 文档站的静态文件目录，默认为包内的 dist/static/ */
  staticDir?: string;
  /** 需要注入到 HTML <head> 的全局变量 */
  globals?: Record<string, string>;
}

// HTML file cache: filename → raw content (before replacement)
const htmlCache = new Map<string, string>();

/**
 * 预热 HTML 缓存，读取所有 .html 文件到内存。
 */
export function warmCache(staticDir: string): void {
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith('.html')) {
        htmlCache.set(full, fs.readFileSync(full, 'utf-8'));
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
 * 挂载到任意路由后，自动将 HTML 中的 __DOCS_BASE__/ 替换为实际路径。
 */
export function createDocsMiddleware(options: DocsMiddlewareOptions = {}): Middleware {
  const staticDir = options.staticDir || path.resolve(__dirname, 'static');
  const globals = options.globals || {};

  // Pre-warm cache on startup
  if (fs.existsSync(staticDir)) {
    warmCache(staticDir);
  }

  return async (ctx: Context) => {
    // Only handle GET/HEAD
    if (ctx.method !== 'GET' && ctx.method !== 'HEAD') return;

    const reqPath = ctx.path || '/';

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

    // HTML pages: read, replace, serve
    let htmlPath = reqPath === '/' ? '/index.html' : reqPath;
    if (!htmlPath.endsWith('.html')) {
      htmlPath += '.html';
    }

    const fullPath = path.join(staticDir, htmlPath);
    const basePath = resolveBasePath(ctx);

    // Try to serve the requested HTML file, fallback to index.html (SPA)
    let rawHtml = htmlCache.get(fullPath);
    if (rawHtml === undefined && fs.existsSync(fullPath)) {
      rawHtml = fs.readFileSync(fullPath, 'utf-8');
      htmlCache.set(fullPath, rawHtml);
    }
    if (rawHtml === undefined) {
      // SPA fallback
      const indexPath = path.join(staticDir, 'index.html');
      rawHtml = htmlCache.get(indexPath);
      if (rawHtml === undefined && fs.existsSync(indexPath)) {
        rawHtml = fs.readFileSync(indexPath, 'utf-8');
        htmlCache.set(indexPath, rawHtml);
      }
    }

    if (rawHtml === undefined) {
      ctx.status = 404;
      ctx.body = 'Not Found';
      return;
    }

    // Replace placeholder with actual base path
    let html = rawHtml.replaceAll(DOCS_BASE_PLACEHOLDER, basePath);

    // Inject global variables if configured
    if (Object.keys(globals).length > 0) {
      html = html.replace('</head>', `${buildGlobalsScript(globals)}\n</head>`);
    }

    ctx.set('Content-Type', 'text/html; charset=utf-8');
    ctx.set('Cache-Control', 'no-cache');
    ctx.body = html;
  };
}
