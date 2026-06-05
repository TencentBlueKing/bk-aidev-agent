# AI 小鲸文档站 npm 包化设计

**日期:** 2026-05-07
**状态:** 待审批
**目标:** 将 VitePress 文档站打包为 npm 包，支持主站任意路由挂载，实现插拔式集成。

---

## 1. 背景与约束

### 当前架构

- 文档站位于 `src/frontend/web/`，基于 VitePress 构建，输出静态 HTML/JS/CSS 到 `dist/`
- 通过自定义 Express 服务 (`server.cjs`) 提供静态文件 + Mock AG-UI API
- 环境变量 (`BK_STATIC_URL`, `BK_SITE_URL` 等) 通过 VitePress 的 `define` 注入，生产环境使用 `{{ }}` 占位符由 PaaS 平台替换
- 文档中的在线 Demo 依赖 `/mock-agui/api` 的 mock 接口（SSE 流式对话）

### 主站架构

- 主站 (`bk-aidev`) 前端由 **Koa 服务** 独立部署（非 Django 直接提供）
- Koa 服务使用 `koa-mount` 挂载静态资源、API 代理、SPA fallback
- 已有 `/code-review/` 使用独立 HTML 模板的先例
- 反向代理通过 `x-script-name` 头注入路径信息

### 核心挑战

VitePress 构建时需要确定 `base` 路径（用于路由和资源引用），但用户希望安装 npm 包后挂载到任意路由，不需要重新构建。这是"构建时 vs 运行时"的矛盾。

---

## 2. 方案概述：运行时路径重写

构建时使用占位符 `__DOCS_BASE__/` 作为 VitePress 的 `base`，运行时中间件将 HTML 中的占位符替换为实际挂载路径。

```js
// 主站 Koa 代码
const mount = require('koa-mount');
const { createDocsMiddleware, createMockAguiRouter } = require('ai-blueking-docs');

// 挂载文档站（任意路由）
app.use(mount('/docs', createDocsMiddleware()));

// 可选：开发环境挂载 mock API
if (process.env.NODE_ENV !== 'production') {
  app.use(mount('/docs/mock-agui/api', createMockAguiRouter()));
}
```

---

## 3. npm 包结构

```
ai-blueking-docs/
├── package.json           # name: "ai-blueking-docs", main: "dist/index.cjs", module: "dist/index.mjs"
├── README.md              # 使用文档
├── dist/
│   ├── index.cjs          # CommonJS 入口
│   ├── index.mjs          # ESM 入口
│   └── static/            # VitePress 构建产物（HTML/JS/CSS/图片）
│       ├── index.html
│       ├── assets/
│       │   ├── *.js       # JS chunks（含 __DOCS_BASE__/ 占位符）
│       │   ├── *.css      # 样式文件
│       │   └── *.woff2    # 字体文件
│       ├── guide/
│       ├── api/
│       ├── demos/
│       └── images/
├── src/
│   ├── index.ts           # 统一导出入口
│   ├── middleware.ts       # Koa 中间件：静态文件服务 + HTML 路径重写
│   └── mock-routes.ts     # Koa 版 mock AG-UI API 路由
└── docs/                  # VitePress 源文件（不发布到 npm）
```

### package.json 关键字段

```json
{
  "name": "ai-blueking-docs",
  "version": "2.0.0",
  "main": "dist/index.cjs",
  "module": "dist/index.mjs",
  "types": "dist/index.d.ts",
  "files": ["dist/", "README.md"],
  "peerDependencies": {
    "koa": ">=2.0.0",
    "@koa/router": ">=10.0.0"
  }
}
```

---

## 4. 构建流水线

### 4.1 VitePress 构建

修改 `docs/.vitepress/config.js`：

```js
export default defineConfig({
  base: process.env.VITEPRESS_BASE || '__DOCS_BASE__/',
  // ... 其他配置不变
});
```

构建命令：

```bash
VITEPRESS_BASE='__DOCS_BASE__/' vitepress build docs
```

构建产物中所有资源路径和路由引用都会使用 `__DOCS_BASE__/` 作为前缀：
- `<link href="/__DOCS_BASE__/assets/style.xxx.css">`
- `<script src="/__DOCS_BASE__/assets/chunks/xxx.js">`
- VitePress 路由：`/__DOCS_BASE__/guide/`

### 4.2 中间件编译

使用 esbuild 将 `src/` 编译为 `dist/index.cjs` + `dist/index.mjs`：

```bash
esbuild src/index.ts --bundle --platform=node --format=cjs --outfile=dist/index.cjs --external:koa --external:@koa/router --external:koa-send
esbuild src/index.ts --bundle --platform=node --format=esm --outfile=dist/index.mjs --external:koa --external:@koa/router --external:koa-send
```

### 4.3 发布

```json
{
  "scripts": {
    "build:docs": "VITEPRESS_BASE='__DOCS_BASE__/' vitepress build docs",
    "build:middleware": "esbuild src/index.ts --bundle --platform=node --format=cjs --outfile=dist/index.cjs && esbuild src/index.ts --bundle --platform=node --format=esm --outfile=dist/index.mjs",
    "build": "npm run build:docs && npm run build:middleware",
    "prepublishOnly": "npm run build"
  }
}
```

---

## 5. Koa 中间件实现

### 5.1 API 定义

```ts
interface DocsMiddlewareOptions {
  /** 文档站的静态文件目录，默认为包内的 dist/static/ */
  staticDir?: string;
}

/**
 * 创建文档站 Koa 中间件。
 * 挂载到任意路由后，自动将 HTML 中的 __DOCS_BASE__/ 替换为实际路径。
 */
export function createDocsMiddleware(options?: DocsMiddlewareOptions): Koa.Middleware;

/**
 * 创建 Mock AG-UI API Koa 路由。
 * 用于文档中的在线 Demo，开发环境使用。
 */
export function createMockAguiRouter(): Koa.Middleware;

/**
 * 预热 HTML 缓存（可选，生产环境启动时调用）。
 */
export function warmCache(): void;
```

### 5.2 中间件工作流程

```
请求进入
  │
  ├─ 是静态资源？（.js / .css / .woff2 / .png / .svg / .jpg）
  │   └─ 使用 koa-send 直接发送文件，设置长期缓存头
  │      Cache-Control: public, max-age=31536000, immutable
  │
  ├─ 是 HTML 请求？（其他所有 GET 请求）
  │   ├─ 读取对应的 .html 文件
  │   ├─ 替换 __DOCS_BASE__/ 为实际挂载路径
  │   ├─ 设置 Cache-Control: no-cache
  │   └─ 返回替换后的 HTML
  │
  └─ 文件不存在？
      └─ 返回 index.html（SPA fallback）
```

### 5.3 路径推导逻辑

中间件被 `koa-mount` 挂载时，`ctx.path` 是去掉挂载前缀的相对路径。通过比较 `ctx.req.url` 和 `ctx.path` 可以推导出实际的挂载前缀：

```ts
function resolveBasePath(ctx: Context): string {
  // koa-mount 会将 ctx.path 设为去掉前缀后的路径
  // ctx.req.url 保留原始完整路径
  const fullUrl = ctx.req.url || '/';
  const relativePath = ctx.path;
  const prefix = fullUrl.slice(0, fullUrl.indexOf(relativePath));
  return prefix.endsWith('/') ? prefix : prefix + '/';
}
```

### 5.4 HTML 缓存策略

- 首次请求时读取文件并缓存原始内容（替换前）
- 后续请求直接从缓存读取并做字符串替换
- 字符串替换本身是微秒级操作，不会成为瓶颈
- 提供 `warmCache()` 方法在启动时预热

---

## 6. Mock API 路由

将现有 `mock-agui-routes.cjs`（Express）重写为 Koa 版本。

### 路由表

| 方法 | 路径 | 行为 |
|---|---|---|
| POST | /session_content/ | 消息 CRUD |
| POST | /session_content/batch_delete/ | 批量删除 |
| POST | /session_content/stop/ | 停止生成 |
| GET | /session_feedback/reasons/ | 反馈原因列表 |
| POST | /session_feedback/ | 提交反馈 |
| POST | /chat_completion/ | SSE 流式对话 |

### SSE 流式对话实现

保持现有行为：`RUN_STARTED` → `TEXT_MESSAGE_START` → 多个 `TEXT_MESSAGE_CHUNK` → `TEXT_MESSAGE_END` → `RUN_FINISHED`，使用 `ctx.res` 直接写入 SSE 格式数据。

---

## 7. 环境变量处理

| 变量 | 处理方式 | 说明 |
|---|---|---|
| `BK_STATIC_URL` | 运行时重写 | 由 `__DOCS_BASE__/` 替换自动处理 |
| `BK_SITE_URL` | 运行时重写 | 同上 |
| `BK_API_URL_TMPL` | 构建时固定 | 写入 JS bundle，不可运行时修改 |
| `BK_AIDEV_URL` | 构建时固定 | 写入 JS bundle，不可运行时修改 |
| `BK_API_GATEWAY_NAME` | 构建时固定 | 写入 JS bundle，不可运行时修改 |

对于 `BK_API_URL_TMPL` 等需要按环境变化的变量，中间件支持在 HTML 的 `<head>` 中注入 `<script>` 标签设置 `window` 全局变量：

```ts
interface DocsMiddlewareOptions {
  staticDir?: string;
  /** 需要注入到 HTML 的全局变量 */
  globals?: Record<string, string>;
}

// 使用
app.use(mount('/docs', createDocsMiddleware({
  globals: {
    BK_API_URL_TMPL: 'https://api.example.com/prod/bk_plugin/plugin_api/',
  }
})));
```

---

## 8. 主站集成指南

### Step 1: 安装

```bash
cd src/frontend/website
npm install ai-blueking-docs
```

### Step 2: 挂载中间件

编辑 `lib/server/app.browser.js`：

```js
const mount = require('koa-mount');
const { createDocsMiddleware, createMockAguiRouter } = require('ai-blueking-docs');

// 在 API 路由之前、静态资源之后挂载
app.use(mount('/docs', createDocsMiddleware({
  globals: {
    BK_API_URL_TMPL: process.env.BK_API_URL_TMPL || '',
  }
})));

// 开发环境：挂载 mock API 以支持文档中的在线 Demo
if (process.env.NODE_ENV !== 'production') {
  app.use(mount('/docs/mock-agui/api', createMockAguiRouter()));
}
```

### Step 3: 添加导航入口（可选）

在主站导航栏中添加"文档"链接，指向 `/docs/`。

### 卸载

```bash
npm uninstall ai-blueking-docs
```

移除 `app.browser.js` 中的挂载代码即可。主站无任何其他改动。

---

## 9. 开发工作流

### 本地开发（文档站独立）

```bash
cd src/frontend/web
pnpm dev          # VitePress dev server，端口 5173
pnpm preview      # 构建 + 自定义 Express 服务，端口 4173
```

开发时不受 npm 包化影响，VitePress 原有的开发体验完全保留。

### 本地开发（联调主站）

```bash
# 文档站
cd src/frontend/web
pnpm build:npm    # 使用占位符构建

# 主站
cd /path/to/bk-aidev/src/frontend/website
npm link /path/to/bk-aidev-agent/src/frontend/web  # 本地链接
npm run dev
# 访问 http://localhost:xxxx/docs/
```

---

## 10. 设计决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| 集成方式 | 静态子站 | 不侵入主站 Vue SPA，与 /code-review/ 模式一致 |
| 路径方案 | 运行时占位符替换 | 真正的任意路由挂载，不需要重新构建 |
| Mock API | 包含在 npm 包中 | 文档中的在线 Demo 依赖 mock 接口 |
| 包管理器 | npm（非 pnpm） | 主站使用 npm，保持一致 |
| 模块格式 | CJS + ESM 双格式 | 兼容主站的 CommonJS 和未来的 ESM |
