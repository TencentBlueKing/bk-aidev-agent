# Wiki 部署说明（Vercel）

本目录的文档站使用 [VitePress](https://vitepress.dev) 构建，并通过 [Vercel](https://vercel.com) 自动部署。

## 1. 触发策略

- **部署分支**：仅 `feat/vercel`
- **触发方式**：每当 `feat/vercel` 分支有新的 commit 推送到 GitHub，Vercel 会自动触发一次构建并发布到生产环境
- 上述策略由仓库根目录 `src/frontend/ai-blueking/vercel.json` 中的 `git.deploymentEnabled` 字段控制，无需在 Vercel 后台再次开关分支

## 2. 构建产物

| 字段 | 值 |
| --- | --- |
| Root Directory | `src/frontend/ai-blueking` |
| Framework Preset | VitePress |
| Install Command | `pnpm install --no-frozen-lockfile` |
| Build Command | `pnpm --filter @blueking/chat-x wiki:build` |
| Output Directory | `packages/chat-x/wikis/.vitepress/dist` |
| Node.js Version | 22.x |

> 这些值已经写进 `vercel.json`，Vercel 默认会读取，但 **Root Directory 必须在 Vercel 后台手动设置**，因为 monorepo 根并不在仓库根。

## 3. 第一次接入 Vercel（一次性操作）

只需要做一次：

1. 登录 https://vercel.com，进入 **Add New… → Project**
2. 选择 GitHub 仓库 (你 fork 的仓库)
3. 关键配置：
   - **Root Directory** 选择 `src/frontend/ai-blueking`
   - Framework Preset 会自动识别为 VitePress
   - Install / Build / Output Directory 保持默认（vercel.json 已写好，无需覆盖）
   - **Production Branch** 设置为 `feat/vercel`（Settings → Git → Production Branch）
4. 点击 **Deploy**，第一次构建完成后即可获得线上地址 `https://<project>.vercel.app`

之后每次 `git push origin feat/vercel`，Vercel 都会自动构建并发布。

## 4. 本地预览构建

```bash
cd src/frontend/ai-blueking

pnpm install
pnpm --filter @blueking/chat-x wiki:build
pnpm --filter @blueking/chat-x exec vitepress preview wikis
```

或开发模式：

```bash
pnpm dev:wiki
```

## 5. SSR 兼容说明

`packages/chat-x/wikis/.vitepress/config.mts` 中通过自定义 Vite 插件，将 `bkui-vue` / `mermaid` / `vue-tippy` / `tippy.js` 在 SSR 阶段重定向到 `ssr-stub.ts`，并把每个 markdown 页面整体包在 `<ClientOnly>` 中。

原因：这些库在模块顶层就会访问 `document` / `window`，Node SSR 环境下会立即抛 `ReferenceError`，阻塞 `vitepress build`。浏览器水合阶段会重新加载真实模块，最终用户体验不受影响。

如果新增了类似"模块顶层访问 DOM"的依赖，需要把对应包名加入 `SSR_STUB_PACKAGES` 数组。
