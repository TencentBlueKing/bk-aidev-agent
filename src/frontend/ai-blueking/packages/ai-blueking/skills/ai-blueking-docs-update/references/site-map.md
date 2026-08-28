# 主站文档地图

根目录：`src/frontend/web/docs/`

## 顶层

| 文件 | 用途 |
| --- | --- |
| `changelog.md` | 版本更新记录，新版本插在文首 |
| `faq.md` | 常见问题，适合短问答与链到指南；含嵌入式 ChatBot 无侧栏开关 / `placement` 已移除；消息时间 `timezone`（≥ v2.2.3） |

## 指南 `/guide/`

### 开始

| 链接 | 文件 |
| --- | --- |
| `/guide/introductions` | `guide/introductions.md` |
| `/guide/quick-start` | `guide/quick-start.md` |

### 集成模式

| 链接 | 文件 |
| --- | --- |
| `/guide/integration-modes/aiblueking-floating` | `aiblueking-floating.md`；浮窗侧栏固定右侧、`showAsideToggle`、两阶段扩宽（≥ v2.2.3） |
| `/guide/integration-modes/chatbot-embedded` | `chatbot-embedded.md` | 嵌入式 ChatBot；**业务 Header**（会话名 + `v-model:asideCollapsed`，侧栏固定右侧） |
| `/guide/integration-modes/atomic-composition` | `atomic-composition.md` |
| `/guide/integration-modes/standalone-bundle` | `standalone-bundle.md` | 非 Vue 宿主、`/standalone`（≥ v2.1.4-beta.8） |

### 功能说明（core-features）

| 链接 | 文件 | 典型更新场景 |
| --- | --- | --- |
| `/guide/core-features/chat-interaction` | `chat-interaction.md` | 消息流、Markdown、停止生成；消息时间展示（≥ v2.2.3）：四档格式、`timezone`、`createdAt` 来源 |
| `/guide/core-features/markdown-inline-style` | `markdown-inline-style.md` | 蓝鲸行内富文本 `::bk::`、LLM 提示词 |
| `/guide/core-features/content-referencing` | `content-referencing.md` | 划词、引用 |
| `/guide/core-features/shortcuts` | `shortcuts.md` | 快捷指令 |
| `/guide/core-features/prompts` | `prompts.md` | 用户 `/` 提示词、`@` 资源 |
| `/guide/core-features/session-management` | `session-management.md` | 会话 CRUD；`session.model` 跟随会话，切换/新建可写回 |
| `/guide/core-features/model-selection` | `model-selection.md` | 模型选择（≥ v2.2.2）：`enableModelSelect`、`models`、`ModelSelectionManager`、跟随 session、写回、`GET llms/`、upload=`support_vision` |
| `/guide/core-features/sharing` | `sharing.md` | 分享；`confirm-share` 的 `source`、自定义 `triggerSelection` |
| `/guide/core-features/custom-message-rendering` | `custom-message-rendering.md` | `custom-component` 块 |
| `/guide/core-features/side-render-customization` | `side-render-customization.md` | 侧栏 Tab `getSideRenderComponent` 等（≥ v2.1.4-beta.7）；`executionTabVisible`（≥ v2.2.0）；文件产物 Tab（≥ v2.2.2）；空态也可打开侧栏 / 产物空态（≥ v2.2.3）；侧栏固定右侧 + 嵌入模式须业务 Header |
| `/guide/core-features/ui-customization` | `ui-customization.md` | 主题、布局；`#welcome` 插槽、`messageTools`/`updateTools`；`size` / `timezone`（≥ v2.2.3） |
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

欢迎区 / 消息工具栏扩展落点：指南 `ui-customization.md`（`#welcome`、`messageTools`/`updateTools`）、`sharing.md`（`confirm-share` + `source`、`agent-action`）；API 同步 `api/ai-blueking/chatbot.md`、`aiblueking.md`、`types.md`。

消息时间时区 `timezone` 落点（≥ v2.2.3）：指南 `chat-interaction.md`（四档格式 / `createdAt` 来源）+ `ui-customization.md`（`timezone` prop）；FAQ「如何让消息时间按指定时区显示」；API `api/ai-blueking/chatbot.md`、`aiblueking.md`、`types.md`，以及 `api/chat-x/components.md` `MessageTime`。未配置时按浏览器时区。

模型选择相关落点（≥ v2.2.2）：指南 `model-selection.md`；API 同步 `aiblueking` / `chatbot` / `managers`（含 `ModelSelectionManager`） / `types`、`chat-helper/sdk`、`chat-x/components`；FAQ「如何关闭或自定义模型选择」。

`stream_mode`（`start` / `attach`）落点：指南 `chat-interaction.md`「刷新 / 切会话续流」、`session-management.md` 切换会话；API `api/chat-helper/sdk.md` `#stream-mode`、`api/chat-helper/types.md` `StreamMode`。ChatBot / AIBlueking 无新 Props。

## 示例 `/demos/`

`demos/full-panel.md`、`basic-usage.md`、`atomic-assembly.md` — 可运行示例，大改交互时同步。

## 配置入口

`docs/.vitepress/config.js`：

- `themeConfig.nav` — 顶栏
- `themeConfig.sidebar["/guide/"]` 等 — 侧栏（**新指南页必改**）
- 顶栏版本下拉读 `changelog.md` 首条 `## vX.Y.Z`（`utils/resolve-changelog-version.js`）

演示依赖（npm 已发布后再改）：`src/frontend/web/package.json` 中 `@blueking/ai-blueking` / `chat-x` / `chat-helper` 应对齐该正式版及其配套子包（当前 2.2.3 / 0.0.49-beta.12 / 0.0.12-beta.24）。

## 源码对照（写文档前建议阅读）

| 变更区域 | 源码位置 |
| --- | --- |
| Markdown / 行内样式 | `packages/chat-x/src/plugins/`、`markdown-content/` |
| 业务组件 | `packages/ai-blueking/src/` |
| SDK / 流式 | `packages/chat-helper/src/` |
| 组件 Wiki | `packages/chat-x/wikis/` |
