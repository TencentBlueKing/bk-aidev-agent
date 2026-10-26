# 文档同步任务（feat/docs-interactive-demos rebase 后）

基线：文档分支原先在 `b8cf05ef`，rebase 到 `182bb03c`（`develop`）后再放回两条文档提交。源码包版本 `3.1.0-beta.1`。文档站交互示例仍依赖已发布的 `@blueking/ai-blueking@2.4.1`（chat-x / chat-helper `2.4.0`），示例页按 2.4.x 描述，并标明与源码的差异。

## 必须更新

- [x] 助手过程状态栏（`698bb763`）：`chat-interaction`、chat-x `MessageContainer` API、changelog、自定义消息折叠说明、site-map、`ai-blueking-dev`
- [x] 模型描述 hover 气泡（`a299b5ab`）：`model-selection`、ModelSelector API、changelog
- [x] 删除 AI 回复收集整轮（`7a171a8a`）：原子组装推荐实现、SDK `deleteMessages`、changelog
- [x] 停止封口补「思考已停止」与过程栏「失败 / 已停止」（`182bb03c`）：指南与 changelog 对齐源码
- [x] 上传说明与源码矛盾：附件按钮常驻；单文件 &lt; 20MB；取消附件删远端；`delete-file` 写入 ChatInput API
- [x] 侧栏内建「执行情况」Tab 已从 chat-x 移除（`8f572713`）：指南、API、类型、FAQ、示例页警告、Skill
- [x] `useMessageGroup` 的 `keyword` / `executionGroups` 已删除：Skill `chat-x-api`
- [x] `executionGroups` 为空就 `resetCustomTab` 的说明改为仅卸载时重置
- [x] ChatInput 快捷键表：`/` 为 Skill·MCP·工具，`\` 为 Prompt

## 后续待处理

文档说明已按当前源码改过。下面几项还没做完，下次从这里继续。

- [ ] **演示依赖仍是 2.4.x**。`src/frontend/web/package.json` 为 `@blueking/ai-blueking@2.4.1`、`chat-x` / `chat-helper` `2.4.0`，源码是 `3.1.0-beta.1`。交互示例里看不到过程状态栏和模型描述气泡；[侧栏示例](src/frontend/web/docs/demos/side-render.md) 仍有已下线的「执行情况」Tab。等对应 npm 发布后升级依赖，并删掉指南和示例里的「文档站示例仍是 2.4.x」警告。
- [ ] **`#message` 插槽作用域**。源码已补齐 `MessageSlotProps` 和 `renderDefault`，主站仍保留 2.4.x 警告。发版并升级演示依赖后，改 `docs/demos/custom-message.md`、`docs/guide/core-features/custom-message-rendering.md`、`docs/api/ai-blueking/chatbot.md`、`docs/api/ai-blueking/aiblueking.md`。
- [ ] **`executionTabVisible` 仍在组件上**。`ChatBot` / `AIBlueking` 继续声明并透传，`ChatContainer` 不读取。文档已写明无效。是否从类型和透传里删掉，留到下次决定。
- [ ] **changelog 版本标题**。导航读的是首条 `## vX.Y.Z`，现在仍是 `v2.4.1`，3.1 行为记在 `## Unreleased`。正式发 3.x 时把 Unreleased 收成版本块。

## 扫描后不改

- 企微图文召回、空产物事件、会话图片签发、知识库存储、MySQL E2E、证书校验、function 协议：后端，主站无对应错误描述
- 行首 `@` 回删、模型气泡 `onShow`：bugfix，chat-x wiki 已覆盖
- 不改 `dist/`
