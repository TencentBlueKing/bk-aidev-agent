---
name: ai-blueking-docs-update
description: 更新 AI 小鲸 VitePress 主站文档（src/frontend/web/docs）。在发布新功能、修改 chat-x/ai-blueking 行为、补充 changelog、撰写 LLM/系统提示词说明、同步 API 与指南交叉链接时使用。触发词：文档更新、changelog、主站文档、VitePress、蓝鲸行内富文本、模型选择、提示词文档、web/docs、欢迎插槽、headerLeft、headerActions、消息工具栏、嵌入模式 Header、asideCollapsed、消息时间、timezone、MessageTime、stream_mode、续流、attach。
metadata:
  author: blueking
  version: '1.13'
compatibility: 需能读写仓库内 src/frontend/web/docs；本地预览需 Node 20+ 与 pnpm。
---

# AI 小鲸主站文档更新

## 何时激活

- 用户要求更新小鲸**主站文档**、`src/frontend/web`、changelog、指南或 API 页
- 组件功能已合入（如 chat-x、ai-blueking），需对外说明用法或迁移注意点
- 新能力依赖 **LLM / AIDev 系统提示词** 约定输出格式（非仅前端 prop）
- 与 `ai-blueking-dev` 并行：本 Skill 只改**文档**，不改组件实现（除非用户明确要求）

## 文档站点位置

| 路径 | 说明 |
| --- | --- |
| `src/frontend/web/docs/` | **唯一源码目录**（Markdown 页面） |
| `src/frontend/web/docs/.vitepress/config.js` | 导航、侧边栏、版本号（读 `changelog.md` 首条 `## vX.Y.Z`） |
| `src/frontend/web/dist/` | 构建产物，**不要手改** |
| `packages/chat-x/wikis/` | chat-x 组件级 Wiki（与主站互补，重大 API 变更时考虑同步） |

版本号来源：`src/frontend/web/docs/changelog.md` 首条 `## vX.Y.Z`（导航栏与 changelog 标题应对齐；发布 2.2.3 时该标题即为 `## v2.2.3`）。

本地预览（在 `src/frontend/web` 下）：

```bash
pnpm dev    # vitepress dev docs
pnpm build  # 生产构建
```

## 更新流程（按顺序）

1. **弄清变更来源**：读相关 commit、`packages/chat-x` / `ai-blueking` 源码注释或 wikis，确认用户可见行为与版本号。
2. **选定文档落点**：按 [站点地图](references/site-map.md) 决定新建页面还是改现有页；大功能独立成篇，小改动在相关章节加段落并交叉链接。
3. **写 changelog**：在 `docs/changelog.md` **顶部**插入新版本块，格式见 [changelog 模板](references/changelog-template.md)。
4. **改指南 / API / FAQ**：保持中文、与现有 VitePress 风格一致（`::: info` / `::: warning` 等）。
5. **注册侧边栏**：新页面必须在 `docs/.vitepress/config.js` 的 `themeConfig.sidebar` 中增加链接。
6. **交叉链接**：从 `chat-interaction`、`prompts`、`faq`、`api/*` 等关联页链到新文档，避免孤岛页。
7. **勿改 dist**、勿主动跑 format/lint 修样式（由用户或 CI 处理）。

## 文档类型与写法

### 用户功能（指南）

- 路径：`docs/guide/core-features/*.md` 或 `integration-modes/`、`advanced-usage/`
- 结构：场景说明 → 配置步骤 → 代码示例 → 限制与注意事项
- 集成模式类改动优先改对应 integration 页 + `chat-interaction` 摘要

### API 参考

- 路径：`docs/api/ai-blueking/`、`docs/api/chat-x/`、`docs/api/chat-helper/`
- Props / Events / Slots 与源码类型保持一致；新增 prop 需补表格行与一行示例

### LLM / 系统提示词（重要）

当功能依赖模型输出特定格式（如蓝鲸行内富文本 `::bk::`）时：

- **系统提示词**（AIDev Agent 指令）：写清语法、禁止项（如 HTML）、完整可复制模板
- **前端 `prompts` prop**：仅用户提问模板，在 `prompts.md` 中说明与系统提示词的分工
- 参考范例：[LLM 提示词文档模式](references/llm-prompt-patterns.md)；已落地示例见 `src/frontend/web/docs/guide/core-features/markdown-inline-style.md`

### 破坏性变更

- changelog 使用 `### 变更` 或 `### 重大变更`
- 若有迁移步骤，更新 `docs/guide/migration-2.0.md` 或新增版本迁移小节
- FAQ 增加一条「为什么以前的做法不生效」

## 命名与文件约定

- 新指南 URL 使用 kebab-case：`markdown-inline-style.md` → `/guide/core-features/markdown-inline-style`
- 标题用中文，与侧边栏 `text` 一致
- 代码块标明语言；Vue 示例需含必要 import（`@blueking/ai-blueking`、`style.css`）

## 与 ai-blueking-dev 的分工

| Skill | 职责 |
| --- | --- |
| `ai-blueking-dev` | 组件实现、集成代码、chat-x wikis 组件文档 |
| `ai-blueking-docs-update`（本 Skill） | 主站 VitePress、changelog、面向集成方与 LLM 配置者的说明 |

功能开发完成后，用本 Skill 更新主站；若 chat-x 公开 API 变更，评估是否同时更新 `packages/chat-x/wikis/`。

## 检查清单（完成前自检）

- [ ] `changelog.md` 已添加对应版本条目（标题与文档站当前发布版本一致；npm 发布后对齐 `web/package.json` 演示依赖）
- [ ] 新页面已加入 `.vitepress/config.js` sidebar
- [ ] 至少一处相关旧文档已链到新内容
- [ ] 未编辑 `src/frontend/web/dist/`
- [ ] LLM 相关能力已区分「系统提示词」与「前端 prompts」
- [ ] 示例代码可在文档语境下理解（不依赖未说明的环境变量）

## 参考资源

- [站点地图与文件职责](references/site-map.md)
- [Changelog 模板](references/changelog-template.md)
- [LLM / 系统提示词文档模式](references/llm-prompt-patterns.md)

规范依据：[Agent Skills Specification](https://agentskills.io/specification)
