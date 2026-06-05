/**
 * 文档站生产/预览用静态服务 + Mock（/mock-agui/api）。
 * VitePress 自带的 `vitepress preview` 不会加载 Vite dev 中间件，原子组装演示会 404；请用 `pnpm preview` 或本脚本。
 *
 * 环境变量：
 * - PORT — 监听端口，默认 5000
 * - DOCS_STATIC_DIR — 静态根目录；默认自动检测 dist/static（pnpm build:npm）或 dist（pnpm build）
 * - DOCS_BASE — 替换 HTML/JS/CSS 中的 __DOCS_BASE__，独立部署根路径填 `/` 或留空，默认 `/`
 * - BK_AIDEV_API_URL、BK_AIDEV_URL 等 — 注入到 HTML <head>，供在线 Demo 使用（与 Koa 中间件 globals 一致）
 * - MOCK_AGUI — 设为 `0` 可关闭 mock API
 */
const express = require('express');
const fs = require('fs');
const path = require('path');
const RateLimit = require('express-rate-limit');

const DOCS_BASE_PLACEHOLDER = '__DOCS_BASE__';
const REPLACEABLE_EXTS = new Set(['.html', '.js', '.css']);
const GLOBAL_ENV_KEYS = [
  'BK_STATIC_URL',
  'BK_SITE_URL',
  'BK_AIDEV_API_URL',
  'BK_API_GATEWAY_NAME',
  'BK_AIDEV_URL',
];

const app = express();
const PORT = Number(process.env.PORT) || 5000;

function resolveStaticDir() {
  if (process.env.DOCS_STATIC_DIR) {
    return path.resolve(process.env.DOCS_STATIC_DIR);
  }
  const distRoot = path.resolve(__dirname, 'dist');
  const nested = path.join(distRoot, 'static');
  if (fs.existsSync(path.join(nested, 'index.html'))) {
    return nested;
  }
  return distRoot;
}

function resolveDocsBase() {
  const raw = process.env.DOCS_BASE;
  if (raw === undefined || raw === '') {
    return '';
  }
  const normalized = raw.endsWith('/') ? raw.slice(0, -1) : raw;
  return normalized === '/' ? '' : normalized;
}

function replaceDocsBase(content, docsBase) {
  const base = docsBase || '';
  return content
    .replaceAll(`/${DOCS_BASE_PLACEHOLDER}`, base ? `/${base.replace(/^\//, '')}` : '/')
    .replaceAll(DOCS_BASE_PLACEHOLDER, base);
}

function buildGlobalsScript() {
  const entries = GLOBAL_ENV_KEYS.filter(key => process.env[key]).map(
    key => `window.${key}=${JSON.stringify(process.env[key])};`,
  );
  if (entries.length === 0) {
    return '';
  }
  return `<script>${entries.join('')}</script>`;
}

function injectGlobals(html) {
  const script = buildGlobalsScript();
  if (!script) {
    return html;
  }
  return html.replace('</head>', `${script}\n</head>`);
}

const staticDir = resolveStaticDir();
const docsBase = resolveDocsBase();
const indexPath = path.join(staticDir, 'index.html');

if (!fs.existsSync(indexPath)) {
  console.error(
    `[ai-blueking-docs] 未找到 ${indexPath}。请先执行 pnpm build（独立部署）或 pnpm build:npm（npm 包结构），或设置 DOCS_STATIC_DIR。`,
  );
  process.exit(1);
}

// Mock AG-UI（可选）
if (process.env.MOCK_AGUI !== '0') {
  try {
    const { createMockAguiRouter } = require('./docs/.vitepress/mock-agui-routes.cjs');
    const mockAgui = express.Router();
    mockAgui.use(createMockAguiRouter());
    app.use('/mock-agui/api', mockAgui);
    console.log('[ai-blueking-docs] Mock AG-UI: /mock-agui/api');
  } catch (err) {
    console.warn('[ai-blueking-docs] Mock AG-UI 未启用:', err.message);
  }
}

app.use(express.json());

// 全局变量中间件（子路径部署时 x-script-name）
app.use((req, res, next) => {
  const scriptName = (req.headers['x-script-name'] || '').replace(/\//g, '');
  req.GLOBAL_VAR = {
    BK_STATIC_URL: scriptName ? `/${scriptName}` : '',
    SITE_URL: scriptName ? `/${scriptName}` : '',
  };
  next();
});

function sendReplaceableFile(req, res, filePath, contentType) {
  fs.readFile(filePath, 'utf-8', (err, raw) => {
    if (err) {
      console.error('[ai-blueking-docs] read failed:', filePath, err.message);
      res.status(404).send('Not Found');
      return;
    }
    let body = replaceDocsBase(raw, docsBase);
    if (contentType.startsWith('text/html')) {
      body = injectGlobals(body);
    }
    res.setHeader('Content-Type', contentType);
    if (contentType.startsWith('text/html')) {
      res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
      res.setHeader('Pragma', 'no-cache');
      res.setHeader('Expires', '0');
    } else {
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
    }
    res.send(body);
  });
}

// 需替换 __DOCS_BASE__ 的可读文件
app.use((req, res, next) => {
  const ext = path.extname(req.path).toLowerCase();
  if (!REPLACEABLE_EXTS.has(ext)) {
    return next();
  }

  let rel = req.path;
  if (ext === '.html' && (rel === '/' || rel === '')) {
    rel = '/index.html';
  }

  const filePath = path.join(staticDir, rel);
  const root = path.resolve(staticDir);
  if (!filePath.startsWith(root + path.sep) && filePath !== root) {
    res.status(403).send('Forbidden');
    return;
  }

  if (!fs.existsSync(filePath) && ext === '.html') {
    sendReplaceableFile(req, res, indexPath, 'text/html; charset=utf-8');
    return;
  }

  if (!fs.existsSync(filePath)) {
    return next();
  }

  const type =
    ext === '.html'
      ? 'text/html; charset=utf-8'
      : ext === '.css'
        ? 'text/css; charset=utf-8'
        : 'application/javascript; charset=utf-8';
  sendReplaceableFile(req, res, filePath, type);
});

// 其余静态资源
app.use(
  express.static(staticDir, {
    index: false,
    maxAge: '1h',
  }),
);

const spaRateLimiter = RateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
});

app.use(spaRateLimiter, (req, res, next) => {
  if (req.path.startsWith('/assets/')) {
    return next();
  }
  if (req.path.match(/\.[a-z0-9]+$/i)) {
    return next();
  }
  sendReplaceableFile(req, res, indexPath, 'text/html; charset=utf-8');
});

app.use((err, req, res, next) => {
  console.error('[ai-blueking-docs] request error:', req.method, req.url, err.stack || err);
  if (res.headersSent) {
    return next(err);
  }
  res.status(500).send('Something went wrong!');
});

const server = app.listen(PORT, () => {
  console.log(`[ai-blueking-docs] Server is running on http://0.0.0.0:${PORT}`);
  console.log(`[ai-blueking-docs] staticDir=${staticDir}`);
  console.log(`[ai-blueking-docs] docsBase=${docsBase === '' ? '(root /)' : docsBase}`);
  const globals = GLOBAL_ENV_KEYS.filter(key => process.env[key]);
  if (globals.length > 0) {
    console.log(`[ai-blueking-docs] injected globals: ${globals.join(', ')}`);
  } else {
    console.log('[ai-blueking-docs] tip: set BK_AIDEV_API_URL / BK_AIDEV_URL for live demos');
  }
});

server.on('error', err => {
  console.error('[ai-blueking-docs] failed to start:', err.message);
  process.exit(1);
});
