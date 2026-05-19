# ai-blueking-docs

AI 小鲸智能对话组件文档站 npm 包。将 VitePress 文档站打包为可插拔的 Koa 中间件，支持在主站任意路由下挂载。

## 安装

```bash
npm install ai-blueking-docs
```

Peer dependencies（需要主站自行安装）：

```bash
npm install koa koa-mount @koa/router koa-send
```

## 使用

### 基本挂载

```js
const mount = require('koa-mount');
const { createDocsMiddleware } = require('ai-blueking-docs');

// 挂载文档站到 /docs 路由
app.use(mount('/docs', createDocsMiddleware()));
```

### 含 Mock API（支持在线 Demo）

```js
const mount = require('koa-mount');
const { createDocsMiddleware, createMockAguiRouter } = require('ai-blueking-docs');

// 挂载文档站
app.use(mount('/docs', createDocsMiddleware({
  globals: {
    BK_API_URL_TMPL: process.env.BK_API_URL_TMPL || '',
  }
})));

// 挂载 mock API（让文档中的在线 Demo 可用）
app.use(mount('/docs/mock-agui/api', createMockAguiRouter()));
```

### 全局变量注入

```js
app.use(mount('/docs', createDocsMiddleware({
  globals: {
    BK_API_URL_TMPL: 'https://api.example.com/prod/bk_plugin/plugin_api/',
    BK_AIDEV_URL: 'https://bkaidev.example.com',
  }
})));
```

注入的变量会作为 `window.BK_API_URL_TMPL` 等全局变量出现在 HTML 的 `<head>` 中。

### 卸载

```bash
npm uninstall ai-blueking-docs
```

移除 Koa 服务中的挂载代码即可，主站无任何其他改动。

## API

### `createDocsMiddleware(options?)`

创建文档站 Koa 中间件。

**Options:**
- `staticDir?: string` — 静态文件目录，默认为包内的 `dist/static/`
- `globals?: Record<string, string>` — 注入到 HTML 的全局变量

### `createMockAguiRouter()`

创建 Mock AG-UI API Koa 路由。提供 REST + SSE 流式对话模拟，用于文档中的在线 Demo。

### `warmCache(staticDir: string)`

预热 HTML 缓存。可选，在生产环境启动时调用以避免首次请求的文件读取延迟。

## 开发

```bash
# 本地开发（VitePress 原有体验不变）
pnpm dev

# 构建独立站点（base = /，用于 Express 服务直接部署）
pnpm build

# 预览独立站点（pnpm build + Express，含 mock API）
pnpm preview

# 预览 npm 包构建产物（pnpm build:npm 后 dist/static/，含 __DOCS_BASE__ 替换）
pnpm preview:npm

# 生产静态服务（自动识别 dist/ 或 dist/static/）
pnpm server
# 或指定目录 / 注入 Demo 环境变量：
# DOCS_STATIC_DIR=./dist/static DOCS_BASE=/ BK_API_URL_TMPL=https://... pnpm server

# 构建 npm 包（base = __DOCS_BASE__/，用于中间件运行时替换）
pnpm build:npm
```

### 两种构建模式的区别

本项目有两种构建模式，产出不同的 `dist/`，适用于不同场景：

| | 独立构建 (`pnpm build`) | npm 包构建 (`pnpm build:npm`) |
|---|---|---|
| **base 路径** | `/` | `__DOCS_BASE__/`（占位符） |
| **用途** | 直接部署到站点根路径，由 Express 服务 (`server.cjs`) 提供服务 | 打包为 npm 包，由主站 Koa 中间件在任意路由下挂载 |
| **HTML 中的路径** | `/assets/style.css` | `__DOCS_BASE__/assets/style.css` |
| **运行时** | 路径已确定，无需替换 | 中间件将 `__DOCS_BASE__/` 替换为实际挂载路径（如 `/docs/`） |
| **命令** | `pnpm build` / `pnpm preview` | `pnpm build:npm` |

**为什么要区分？** VitePress 构建时必须确定 base 路径（用于路由和资源引用）。独立部署时 base 固定为 `/`；npm 包需要支持任意路由挂载，所以构建时使用占位符，运行时由中间件替换。

## 工作原理

构建时 VitePress 使用 `__DOCS_BASE__/` 作为 base 路径占位符。运行时 Koa 中间件读取 HTML 文件并将占位符替换为实际的挂载路径。静态资源（JS/CSS/图片）直接提供服务，不做替换。
