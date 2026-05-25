import fs from 'node:fs';
import path from 'node:path';
export const DOCS_BASE_PLACEHOLDER = '__DOCS_BASE__';

/** Static file extensions — served directly, no rewriting */
export const STATIC_EXTS = new Set([
  '.woff', '.woff2', '.ttf', '.eot',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
  '.mp4', '.webm', '.mp3', '.wav',
  '.json', '.map', '.txt', '.xml',
]);

/** File extensions that may contain __DOCS_BASE__/ placeholder and need rewriting */
export const REPLACEABLE_EXTS = new Set(['.html', '.js', '.css']);

export interface DocsAssetServiceOptions {
  /** 文档站静态文件目录，默认包内 dist/static/ */
  staticDir?: string;
  /** 运行时 base 路径，如 /docs 或 /prod--foo/docs（不含尾部斜杠） */
  basePath: string;
  /** 注入到 HTML <head> 的全局变量 */
  globals?: Record<string, string>;
  /** 可替换文件内容缓存，可在多实例间共享 */
  contentCache?: Map<string, string>;
}

export type DocsAssetResult =
  | {
      kind: 'text';
      status: number;
      contentType: string;
      body: string;
      cacheControl: string;
      extraHeaders?: Record<string, string>;
    }
  | {
      kind: 'file';
      status: number;
      filePath: string;
      cacheControl: string;
    }
  | { kind: 'not_found'; status: 404 }
  | { kind: 'forbidden'; status: 403 };

/**
 * 默认静态目录：与 npm 包 dist/index.* 同级的 dist/static/
 */
export function getDefaultStaticDir(): string {
  const candidates = [
    path.resolve(__dirname, 'static'),
    path.resolve(process.cwd(), 'node_modules/ai-blueking-docs/dist/static'),
    path.resolve(process.cwd(), '../node_modules/ai-blueking-docs/dist/static'),
    path.resolve(process.cwd(), '../../node_modules/ai-blueking-docs/dist/static'),
  ];

  return candidates.find(candidate => fs.existsSync(path.join(candidate, 'index.html')))
    ?? candidates[0];
}

/**
 * 将 SITE_URL 与 /docs 拼接为文档站 base（无尾部斜杠）。
 * @example resolveDocsBasePath('') => '/docs'
 * @example resolveDocsBasePath('/prod--foo') => '/prod--foo/docs'
 */
export function resolveDocsBasePath(siteUrl: string): string {
  const normalized = (siteUrl || '').replace(/\/$/, '');
  return normalized ? `${normalized}/docs` : '/docs';
}

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
  return STATIC_EXTS.has(path.extname(p).toLowerCase());
}

function buildGlobalsScript(globals: Record<string, string>): string {
  const entries = Object.entries(globals)
    .map(([k, v]) => `window.${k}=${JSON.stringify(v)};`)
    .join('');
  return `<script>${entries}</script>`;
}

function replaceDocsBase(rawContent: string, basePath: string): string {
  const basePathNoSlash = basePath.replace(/^\//, '');
  return rawContent
    .replaceAll('/' + DOCS_BASE_PLACEHOLDER, '/' + basePathNoSlash)
    .replaceAll(DOCS_BASE_PLACEHOLDER, basePath);
}

function injectGlobals(html: string, globals: Record<string, string>): string {
  if (Object.keys(globals).length === 0) {
    return html;
  }
  return html.replace('</head>', `${buildGlobalsScript(globals)}\n</head>`);
}

function resolveSafePath(staticDir: string, reqPath: string): string | null {
  const staticRoot = path.resolve(staticDir);
  const fullPath = path.resolve(staticRoot, reqPath.startsWith('/') ? reqPath.slice(1) : reqPath);
  if (!fullPath.startsWith(staticRoot + path.sep) && fullPath !== staticRoot) {
    return null;
  }
  return fullPath;
}

export class DocsAssetService {
  readonly staticDir: string;
  readonly basePath: string;
  readonly globals: Record<string, string>;
  private readonly contentCache: Map<string, string>;

  constructor(options: DocsAssetServiceOptions) {
    this.staticDir = options.staticDir || getDefaultStaticDir();
    this.basePath = options.basePath.replace(/\/$/, '') || '/docs';
    this.globals = options.globals || {};
    this.contentCache = options.contentCache ?? new Map<string, string>();
    if (fs.existsSync(this.staticDir) && this.contentCache.size === 0) {
      warmCache(this.staticDir, this.contentCache);
    }
  }

  /**
   * 处理文档站 GET 请求（路径相对于 /docs 挂载点，如 /guide/foo.html）。
   */
  handleGet(requestPath: string): DocsAssetResult {
    let reqPath = requestPath || '/';
    if (!reqPath.startsWith('/')) {
      reqPath = `/${reqPath}`;
    }

    const ext = path.extname(reqPath).toLowerCase();

    if (REPLACEABLE_EXTS.has(ext)) {
      return this.serveReplaceable(reqPath, ext);
    }

    if (isStaticFile(reqPath)) {
      return this.serveBinary(reqPath);
    }

    return this.serveSpaFallback();
  }

  private readCached(fullPath: string): string | undefined {
    let raw = this.contentCache.get(fullPath);
    if (raw === undefined && fs.existsSync(fullPath)) {
      raw = fs.readFileSync(fullPath, 'utf-8');
      this.contentCache.set(fullPath, raw);
    }
    return raw;
  }

  private serveReplaceable(reqPath: string, ext: string): DocsAssetResult {
    let filePath = reqPath;
    if (ext === '.html') {
      filePath = reqPath === '/' ? '/index.html' : reqPath;
    }

    const fullPath = resolveSafePath(this.staticDir, filePath);
    if (fullPath === null) {
      return { kind: 'forbidden', status: 403 };
    }

    let rawContent = this.readCached(fullPath);

    if (rawContent === undefined && ext === '.html') {
      const indexPath = path.join(this.staticDir, 'index.html');
      rawContent = this.readCached(indexPath);
    }

    if (rawContent === undefined) {
      return { kind: 'not_found', status: 404 };
    }

    const content = replaceDocsBase(rawContent, this.basePath);

    if (ext === '.html') {
      return {
        kind: 'text',
        status: 200,
        contentType: 'text/html; charset=utf-8',
        body: injectGlobals(content, this.globals),
        cacheControl: 'no-cache',
      };
    }

    if (ext === '.css') {
      return {
        kind: 'text',
        status: 200,
        contentType: 'text/css; charset=utf-8',
        body: content,
        cacheControl: 'public, max-age=31536000, immutable',
      };
    }

    return {
      kind: 'text',
      status: 200,
      contentType: 'application/javascript; charset=utf-8',
      body: content,
      cacheControl: 'public, max-age=31536000, immutable',
      extraHeaders: { 'X-Content-Type-Options': 'nosniff' },
    };
  }

  private serveBinary(reqPath: string): DocsAssetResult {
    const fullPath = resolveSafePath(this.staticDir, reqPath);
    if (fullPath === null) {
      return { kind: 'forbidden', status: 403 };
    }
    if (!fs.existsSync(fullPath)) {
      return { kind: 'not_found', status: 404 };
    }
    return {
      kind: 'file',
      status: 200,
      filePath: fullPath,
      cacheControl: 'public, max-age=31536000, immutable',
    };
  }

  private serveSpaFallback(): DocsAssetResult {
    const indexPath = path.join(this.staticDir, 'index.html');
    let rawHtml = this.readCached(indexPath);
    if (rawHtml === undefined) {
      return { kind: 'not_found', status: 404 };
    }

    let html = replaceDocsBase(rawHtml, this.basePath);
    html = injectGlobals(html, this.globals);

    return {
      kind: 'text',
      status: 200,
      contentType: 'text/html; charset=utf-8',
      body: html,
      cacheControl: 'no-cache',
    };
  }
}

export function createDocsAssetService(options: DocsAssetServiceOptions): DocsAssetService {
  return new DocsAssetService(options);
}
