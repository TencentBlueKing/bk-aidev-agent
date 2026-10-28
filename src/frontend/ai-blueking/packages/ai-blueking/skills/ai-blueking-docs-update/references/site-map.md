# 主站文档地图

根目录：`src/frontend/web/docs/`

## 顶层

| 文件 | 用途 |
| --- | --- |
| `changelog.md` | 版本更新记录，新版本插在文首 |
| `faq.md` | 常见问题，适合短问答与链到指南；含嵌入式 ChatBot 无侧栏开关 / `placement` 已移除；消息时间 `timezone`（≥ v2.2.3）；`enableChatSession` / `enablePopup` 与 info 联动（≥ v2.2.4）；`enableMessageCollapse` 关闭消息折叠与过程状态栏；`executionTabVisible` 在 chat-x 3.0.0 起无效 |

## 指南 `/guide/`

### 开始

| 链接 | 文件 |
| --- | --- |
| `/guide/introductions` | `guide/introductions.md` |
| `/guide/quick-start` | `guide/quick-start.md` |

### 集成模式

| 链接 | 文件 |
| --- | --- |
| `/guide/integration-modes/aiblueking-floating` | `aiblueking-floating.md`；浮窗侧栏固定右侧、`showAsideToggle`、两阶段扩宽、收起移回展开前位置（≥ v2.2.3）；`enablePopup` / `enableChatSession` 与 info 联动（≥ v2.2.4） |
| `/guide/integration-modes/chatbot-embedded` | `chatbot-embedded.md` | 嵌入式 ChatBot；**业务 Header**（会话名 + `v-model:asideCollapsed`，侧栏固定右侧） |
| `/guide/integration-modes/atomic-composition` | `atomic-composition.md` |
| `/guide/integration-modes/standalone-bundle` | `standalone-bundle.md` | 非 Vue 宿主、`/standalone`（≥ v2.1.4-beta.8） |

### 功能说明（core-features）

| 链接 | 文件 | 典型更新场景 |
| --- | --- | --- |
| `/guide/core-features/chat-interaction` | `chat-interaction.md` | 消息流、Markdown、停止生成（点击立即封口、思考已停止、无正文时补「用户已取消」）；消息折叠 `enableMessageCollapse`（默认折叠 + 过程状态栏，可关闭）；删除整轮；消息时间展示（≥ v2.2.3）；文件上传（附件按钮常驻、单文件 &lt; 20MB、`delete-file`、上限 9、`pv_files`）；`stream_mode` 续流 |
| `/guide/core-features/markdown-inline-style` | `markdown-inline-style.md` | 蓝鲸行内富文本 `::bk::`、LLM 提示词 |
| `/guide/core-features/content-referencing` | `content-referencing.md` | 划词、引用；`enablePopup` 与 info `enableWordSelectionPopup` 联动（≥ v2.2.4）；新建会话清引用 |
| `/guide/core-features/shortcuts` | `shortcuts.md` | 快捷指令 |
| `/guide/core-features/prompts` | `prompts.md` | 用户 `\` 提示词、`/` Skill·MCP·工具、`@` 资源；统一 `menuSources` 与 `property.docSchema`（≥ v2.4.0） |
| `/guide/core-features/session-management` | `session-management.md` | 会话 CRUD；`session.model` 跟随会话，切换/新建可写回 |
| `/guide/core-features/model-selection` | `model-selection.md` | 模型选择（≥ v2.2.2）：`enableModelSelect`、`models`、`ModelSelectionManager`、跟随 session、写回、`GET llms/`；上传入口常驻，不跟 `support_vision`；`description` hover 气泡（3.1.0-beta.1） |
| `/guide/core-features/sharing` | `sharing.md` | 分享；`confirm-share` 的 `source`、自定义 `triggerSelection` |
| `/guide/core-features/custom-message-rendering` | `custom-message-rendering.md` | `custom-component` 块 |
| `/guide/core-features/side-render-customization` | `side-render-customization.md` | 侧栏 Tab `getSideRenderComponent` 等（≥ v2.1.4-beta.7）；chat-x 3.0.0 起内建「执行情况」Tab 已下线，`executionTabVisible` 不再生效；常驻默认 Tab 为「文件产物」（`loadOnSelect: false` 不走业务渲染器）；侧栏固定右侧 + 嵌入模式须业务 Header。示例页按 3.1.0-beta.5，用 `enableMessageCollapse` |
| `/guide/core-features/ui-customization` | `ui-customization.md` | 主题、布局；`#welcome` 插槽、`#headerLeft` / `#headerActions`（≥ v2.2.4）、`messageTools`/`updateTools`；动态 placeholder（≥ v2.2.4）；`size` / `timezone`（≥ v2.2.3） |
| `/guide/core-features/skill-guide` | `skill-guide.md` | AIDev Skill 市场指引 |

### 高级用法

`guide/advanced-usage/` — 外部会话列表（须带业务 Header / 侧栏开关）、自定义请求、编程式控制、多 Agent。

### 架构与内部

`guide/architecture.md`、`guide/internals/*` — Manager、事件、bootstrap、message property。

### 迁移

`guide/migration-2.0.md` — v1 → v2；后续大版本可增新迁移页。

## API `/api/`

| 包 | 目录 |
| --- | --- |
| `@blueking/ai-blueking` | `api/ai-blueking/`（chatbot、aiblueking、standalone、managers、types） |
| `@blueking/chat-x` | `api/chat-x/`（components、types；含 ModelSelector / `IModelOption`） |
| `@blueking/chat-helper` | `api/chat-helper/`（sdk、types；含 `getLlms` / `ILlmItem` / `StreamMode`） |

组件行为变更时：更新对应 API 表 + 在指南中加交叉链接。

`setInputContent` 落点：API `api/ai-blueking/chatbot.md`、`aiblueking.md` 的 Expose 表。整篇替换输入框（`string | TagSchema`），不发送、不清引用，标签按芯片显示。挂载后给 `ChatInput` 的 `v-model` 赋带标签的文档同样保留芯片（chat-x `AiSlashInput` 按节点同步），如需说明落在 `api/chat-x/components.md` 的 `ChatInput`。

欢迎区 / 消息工具栏扩展落点：指南 `ui-customization.md`（`#welcome`、`messageTools`/`updateTools`）、`sharing.md`（`confirm-share` + `source`、`agent-action`）；API 同步 `api/ai-blueking/chatbot.md`、`aiblueking.md`、`types.md`。

Header 插槽 `#headerLeft` / `#headerActions` 落点：指南 `ui-customization.md`；API `api/ai-blueking/aiblueking.md` Slots 表（仅 AIBlueking）。

消息时间时区 `timezone` 落点（≥ v2.2.3）：指南 `chat-interaction.md`（四档格式 / `createdAt` 来源）+ `ui-customization.md`（`timezone` prop）；FAQ「如何让消息时间按指定时区显示」；API `api/ai-blueking/chatbot.md`、`aiblueking.md`、`types.md`，以及 `api/chat-x/components.md` `MessageTime`。未配置时按浏览器时区。

消息折叠 `enableMessageCollapse` 落点：指南 `chat-interaction.md`「消息折叠」、`chatbot-embedded.md` Props；FAQ「如何关闭消息折叠和过程状态栏」；API `api/ai-blueking/chatbot.md`、`aiblueking.md`、`types.md`，以及 `api/chat-x/components.md` `MessageContainer`。默认 `true`，与 chat-x 一致。

模型选择相关落点（≥ v2.2.2）：指南 `model-selection.md`；API 同步 `aiblueking` / `chatbot` / `managers`（含 `ModelSelectionManager`） / `types`、`chat-helper/sdk`、`chat-x/components`；FAQ「如何关闭或自定义模型选择」。

`stream_mode`（`start` / `attach`）落点：指南 `chat-interaction.md`「刷新 / 切会话续流」、`session-management.md` 切换会话；API `api/chat-helper/sdk.md` `#stream-mode`、`api/chat-helper/types.md` `StreamMode`。ChatBot / AIBlueking 无新 Props。

文件上传（≥ v2.2.4）落点：指南 `chat-interaction.md`「文件上传」；API `api/chat-x/components.md` `ChatInput`（`onUpload` / `accept`）、`api/chat-helper/sdk.md` `uploadFile` / `uploadFiles`。默认 `pv_files/upload`，旧 SDK 走逐个 `upload/{fileName}/`。

`enableChatSession` / `enablePopup` 与 info 联动（≥ v2.2.4）：指南 `aiblueking-floating.md`、`session-management.md`（历史会话开关，≥ v2.4.1 不阻断建会话）、`content-referencing.md`；FAQ「如何关闭多会话或划词弹窗」；API `aiblueking.md` / `types.md`。任一为 `false` 即关闭对应 UI。`enableChatSession` 不阻断 `createSession` / `loadRecentSession`。

## 示例 `/demos/`

侧栏与总览页 `demos/index.md`（`<DemoGallery />`）都由 **`docs/.vitepress/demos-catalog.ts`** 生成：新增示例页只在目录里登记（`group` / `modes` / `recipes` / `status`），`status: 'planned'` 的条目不出现在侧栏与总览。

| 分组 | 页面 | 内容 |
| --- | --- | --- |
| 示例 | `demos/index.md` | 总览画廊：按集成形态选 + 筛选 + 分组卡片 |
| 集成形态 | `demos/full-panel.md` | AIBlueking 浮窗：配置台（props 实时重挂载 + 生成模板）、面板初始位置与尺寸 |
| 集成形态 | `demos/basic-usage.md` | ChatBot 嵌入：最小嵌入（`whenReady`）、业务 Header + 会话列表（`EmbeddedWorkbench.vue`） |
| 集成形态 | `demos/atomic-assembly.md` | 原子组件组装（`AtomicAssemblyDemo.vue`）；接口清单 / 工具栏回调 / AG-UI 事件表在指南 `atomic-composition.md` |
| 业务联动 | `demos/programmatic-control.md` | 打开与就绪、带上下文提问、快捷指令三种触发 + 单次请求注入；同组配方嵌入 `guide/advanced-usage/programmatic-control.md` |
| 业务联动 | `demos/request-options.md` | 按租户切换 Header / 参数（computed requestOptions）、消息上下文 context |
| 业务联动 | `demos/session-events.md` | 首条消息后自动命名（@rename）、新建 / 改名 / 切换会话 |
| 业务联动 | `demos/error-handling.md` | 故障注入观察 @sdk-error（Mock 头 `x-mock-fault`）、切换智能体 url（Mock 档案 `~data/`） |

| 界面与渲染 | `demos/header-slots.md` | `#headerLeft` / `#headerActions` / `showHistoryIcon` 配置台（浮窗配置含插槽）、renderMode 三种模式 |
| 界面与渲染 | `demos/custom-message.md` | `#message` + `parseCustomBlocks` 渲染图表 / 表单 / iframe（`CustomMessageRenderer.vue`）、`#codeHeader` 插入编辑器（`CodeToEditor.vue`）；iframe 静态页 `public/demo-assets/mini-dashboard.html` |

| 界面与渲染 | `demos/side-render.md` | 流程智能体流程卡片、文件产物侧栏、节点详情 / 重试跳过、`enableMessageCollapse`、`getSideRenderComponent` / `getSideTabRenderComponent` / `onCustomTabChange`；Mock 档案 `~flow/`（`src/mock-flow.ts`） |

目录中已无 planned 条目；新增示例页时先在 `demos-catalog.ts` 登记。

**当前仍成立的限制（文档用 `::: warning 当前行为` 标注，修复后删除）**：`updatePosition` / `updateSize` / `updatePositionAndSize` 不带动面板；`show(…, { isTemporary })` 不生效；`requestOptions.context` 只解析值形态；`@sdk-error` 的 `code` 恒为 -1（HTTP 状态在 `data.response.status`）；RUN_ERROR 不经过 `@sdk-error`；`updateSessionName` 不触发 `@rename`。已发布 `3.1.0-beta.5` 的 `#message` 作用域仍不含用户消息工具回调。

`#message` 作用域已在组件源码补齐 `MessageSlotProps`（含用户消息工具回调）以及 ChatBot / AIBlueking 的 `renderDefault`。主站演示跑的是 npm 已发布版本，**等包含该修复的 @blueking/ai-blueking / chat-x 发版并升级 `web/package.json` 后**，再把下列 warning 改成新作用域（含 `renderDefault()` 示例）并删掉：`docs/demos/custom-message.md`、`docs/guide/core-features/custom-message-rendering.md`，以及 `docs/api/ai-blueking/chatbot.md`、`docs/api/ai-blueking/aiblueking.md` 里的 message 插槽表。

| 路径 | 职责 |
| --- | --- |
| `docs/.vitepress/demos-catalog.ts` | 示例目录（侧栏 + 总览的唯一来源） |
| `docs/.vitepress/theme/demo-kit/` | 配方基础设施：`DemoRecipe`、`DemoStage`、`DemoInspector`、`DemoEnvBar`、`DemoGallery`、`DemoRuntimeHost`（Layout 中唯一的浮窗 `AIBlueking`）、`use-demo-runtime.ts`、`use-embedded-instance.ts` |
| `docs/.vitepress/theme/recipes/<topic>/` | 配方组件 `Recipe*.vue` + `snippets/*.ts`（既执行也展示的代码）；整页组件型配方直接展示 `.vue` 全文 |
| `src/frontend/web/src/mock-*.ts` | 文档站 Mock 唯一实现（Koa `createMockAguiRouter` / connect `createMockAguiNodeMiddleware`），按 `x-mock-client` 隔离访客；路径前缀 `~<profile>/` 切换智能体档案；请求头 `x-mock-fault` 注入故障 |

## 配置入口

`docs/.vitepress/config.js`：

- `themeConfig.nav` — 顶栏
- `themeConfig.sidebar["/guide/"]` 等 — 侧栏（**新指南页必改**）
- 顶栏版本下拉读 `changelog.md` 首条 `## vX.Y.Z`（`utils/resolve-changelog-version.js`）

演示依赖：`src/frontend/web/package.json` 中 `@blueking/ai-blueking` / `chat-x` / `chat-helper` 对齐已发布的 `3.1.0-beta.5`。交互示例按这个版本描述。

## 源码对照（写文档前建议阅读）

| 变更区域 | 源码位置 |
| --- | --- |
| Markdown / 行内样式 | `packages/chat-x/src/plugins/`、`markdown-content/` |
| 业务组件 | `packages/ai-blueking/src/` |
| SDK / 流式 | `packages/chat-helper/src/` |
| 组件 Wiki | `packages/chat-x/wikis/` |
