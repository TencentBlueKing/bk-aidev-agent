# Changelog 写法

文件：`src/frontend/web/docs/changelog.md`

## 规则

1. **新版本块放在文件最上方**（紧接 `# 更新日志` 之后）。
2. 标题使用 `## v{version}`，与文档站当前发布版本一致（导航栏读 changelog 首条标题；发 npm 时再与 `packages/ai-blueking/package.json` 对齐）。
3. 用 `---` 与上一版本分隔。
4. 分类标题使用三级标题：`### 新功能` / `### 优化` / `### 修复` / `### 变更` / `### 文档` / `### 重大变更`。
5. 文档类条目用 Markdown 链接指向新页：`[页面标题](/guide/...)`.

## 模板

```markdown
## v2.1.4-beta.6

### 新功能

- **功能名**：一句话说明用户价值
- 子要点（可选）

### 变更

- 破坏性或不兼容说明；引导到迁移或新语法

### 文档

- 新增 [页面标题](/guide/core-features/xxx) 指南
- 更新 [聊天交互](/guide/core-features/chat-interaction) 中的 xxx 说明

---
```

## 示例（节选）

```markdown
## v2.2.3

### 新功能

- **消息时间展示**（≥ v2.2.3）：用户消息与 AI 回复在工具栏旁展示创建时间；`timezone` 为 IANA 名。详见 [聊天交互 · 消息时间展示](/guide/core-features/chat-interaction#消息时间展示)

---
```

```markdown
## v2.1.4-beta.6

### 新功能

- **蓝鲸行内富文本**：AI 消息支持 `::bk{属性}正文:/bk::` 语法，在安全白名单内渲染颜色、加粗、背景色、字号（1–72px）

### 变更

- Markdown 渲染不再解析任意 HTML 标签；行内样式请使用蓝鲸行内富文本，详见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)

### 文档

- 新增 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style) 指南，含 LLM / 系统提示词配置示例

---
```

## 何时只写「文档」节

仅改文档、未发 npm 时，仍可在 changelog 记一笔（若用户要求对外可见），或跳过版本块——**以用户指示为准**。默认与组件版本发布同步更新。
