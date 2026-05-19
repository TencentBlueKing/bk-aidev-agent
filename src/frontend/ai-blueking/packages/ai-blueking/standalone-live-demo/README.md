# Standalone 本地 Live Server 验证

按 [Standalone 非 Vue 宿主集成](https://github.com/TencentBlueKing/bk-aidev-agent/blob/main/src/frontend/web/docs/guide/integration-modes/standalone-bundle.md) 文档，用 IIFE 直引本地 `dist/standalone` 产物。

## 前置

1. 已构建 standalone 包（在 `packages/ai-blueking` 目录）：

   ```bash
   pnpm build
   ```

   确认存在：

   - `../dist/standalone/index.iife.min.js`
   - `../dist/standalone/style.css`

2. 使用 **Live Server**（或任意静态 HTTP 服务）打开 `index.html`，不要用 `file://` 直接打开。

## 使用步骤

1. 在 VS Code 中右键 `index.html` → **Open with Live Server**。
2. 在页面顶部填写 **AIDev API URL**（需以 `/` 结尾或会自动补全），或地址栏带参数：

   ```
   http://127.0.0.1:5500/standalone-live-demo/index.html?url=https://your-aidev-url.com/api/
   ```

3. 点击 **挂载 ChatBot** 或 **挂载 AIBlueking**，右侧查看事件日志。
4. 可用 **expose.show()**、**expose.sendMessage()** 验证编程式 API。

## 说明

- 全局变量：`AIBluekingStandalone`（与 `vite.utils` 中 `lib.name` 一致）。
- 若接口跨域失败，需在网关配置 CORS，或通过本地代理转发 API。
- AIBlueking 使用 `enablePopup: true` 时，面板由浮球唤起，可先点 **expose.show()** 或页面右下角 Nimbus。
