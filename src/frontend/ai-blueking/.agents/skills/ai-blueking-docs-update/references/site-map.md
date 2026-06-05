# 主站文档地图

根目录：`src/frontend/web/docs/`

## 顶层

| 文件 | 用途 |
| --- | --- |
| `changelog.md` | 版本更新记录，新版本插在文首 |
| `faq.md` | 常见问题，适合短问答与链到指南 |

## 指南 `/guide/`

### 开始

| 链接 | 文件 |
| --- | --- |
| `/guide/introductions` | `guide/introductions.md` |
| `/guide/quick-start` | `guide/quick-start.md` |

### 集成模式

| 链接 | 文件 |
| --- | --- |
| `/guide/integration-modes/aiblueking-floating` | `aiblueking-floating.md` |
| `/guide/integration-modes/chatbot-embedded` | `chatbot-embedded.md` |
| `/guide/integration-modes/atomic-composition` | `atomic-composition.md` |
| `/guide/integration-modes/standalone-bundle` | `standalone-bundle.md` | 非 Vue 宿主、`/standalone`（≥ v2.1.4-beta.8） |

### 功能说明（core-features）

| 链接 | 文件 | 典型更新场景 |
| --- | --- | --- |
| `/guide/core-features/chat-interaction` | `chat-interaction.md` | 消息流、Markdown、停止生成 |
| `/guide/core-features/markdown-inline-style` | `markdown-inline-style.md` | 蓝鲸行内富文本 `::bk::`、LLM 提示词 |
| `/guide/core-features/content-referencing` | `content-referencing.md` | 划词、引用 |
| `/guide/core-features/shortcuts` | `shortcuts.md` | 快捷指令 |
| `/guide/core-features/prompts` | `prompts.md` | 用户 `/` 提示词、`@` 资源 |
| `/guide/core-features/session-management` | `session-management.md` | 会话 CRUD |
| `/guide/core-features/sharing` | `sharing.md` | 分享 |
| `/guide/core-features/custom-message-rendering` | `custom-message-rendering.md` | `custom-component` 块 |
| `/guide/core-features/side-render-customization` | `side-render-customization.md` | 侧栏 Tab `getSideRenderComponent` 等（≥ v2.1.4-beta.7） |
| `/guide/core-features/ui-customization` | `ui-customization.md` | 主题、布局 |
| `/guide/core-features/skill-guide` | `skill-guide.md` | AIDev Skill 市场指引 |

### 高级用法

`guide/advanced-usage/` — 外部会话列表、自定义请求、编程式控制、多 Agent。

### 架构与内部

`guide/architecture.md`、`guide/internals/*` — Manager、事件、bootstrap、message property。

### 迁移

`guide/migration-2.0.md` — v1 → v2；后续大版本可增新迁移页。

## API `/api/`

| 包 | 目录 |
| --- | --- |
| `@blueking/ai-blueking` | `api/ai-blueking/`（chatbot、aiblueking、standalone、managers、types） |
| `@blueking/chat-x` | `api/chat-x/`（components、types） |
| `@blueking/chat-helper` | `api/chat-helper/`（sdk、types） |

组件行为变更时：更新对应 API 表 + 在指南中加交叉链接。

## 示例 `/demos/`

`demos/full-panel.md`、`basic-usage.md`、`atomic-assembly.md` — 可运行示例，大改交互时同步。

## 配置入口

`docs/.vitepress/config.js`：

- `themeConfig.nav` — 顶栏
- `themeConfig.sidebar["/guide/"]` 等 — 侧栏（**新指南页必改**）
- `import { version } from "../../../ai-blueking/packages/ai-blueking/package.json"` — 顶栏版本下拉

## 源码对照（写文档前建议阅读）

| 变更区域 | 源码位置 |
| --- | --- |
| Markdown / 行内样式 | `packages/chat-x/src/plugins/`、`markdown-content/` |
| 业务组件 | `packages/ai-blueking/src/` |
| SDK / 流式 | `packages/chat-helper/src/` |
| 组件 Wiki | `packages/chat-x/wikis/` |
