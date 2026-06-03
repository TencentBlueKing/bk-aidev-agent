# 简介

## 什么是 @blueking/chat-x

`@blueking/chat-x` 是蓝鲸智云推出的 **AI 优先**对话组件库。它不仅面向人类开发者提供开箱即用的 AI Chat 组件，更将 **AI Agent 作为第一优先级消费者**——通过结构化元数据、AI 专用摘要和内置 MCP 服务，让 AI 在极少的工具调用内即可理解并正确使用组件。

> 深入了解：[架构总览](./architecture.md) · [设计理念](./design-philosophy.md) · [用例食谱](./recipes.md) · [MCP 服务](./ai/mcp.md)

## AI 优先

这不只是一个「有文档的组件库」，而是一个「AI 可直接消费的组件库」。

### 对 AI Agent

- **结构化 Frontmatter**：每个组件页面顶部包含 `name`、`slug`、`domain`、`aiSummary`、`relatedComponents` 等机器可读元数据
- **AI 专用摘要**：`aiSummary` 用 2-4 句话精确描述组件职责、必填 props、关键行为和常见搭配，AI 无需阅读全文
- **MCP 服务**：内置 `list_components`（支持 domain/category 过滤）、`get_component_doc`（返回清洗后的文档 + AI 摘要）、`search_docs`（关键词搜索）三个工具
- **文档清洗**：MCP 返回的文档自动剥离 `<script setup>`、`<div class="demo">` 等 VitePress 运行时代码，只保留对 AI 有用的内容

### 对人类开发者

- **渐进式组合**：`ChatContainer` 一行代码完整对话页面，或 `ChatInput + MessageContainer` 自由组合
- **类型安全**：完整的 TypeScript 类型定义，`declare global` 零侵入扩展自定义消息类型
- **6 功能域导航**：按使用场景（消息展示、输入交互、内容渲染、文件与图片、工具与反馈、辅助组件）检索组件

## 核心能力

### 消息系统

支持 20+ 种消息角色，按 `role` 区分的判别联合类型：

| 类别     | 角色                                 | 说明                                                 |
| -------- | ------------------------------------ | ---------------------------------------------------- |
| 核心对话 | `User`、`Assistant`                  | 用户消息和 AI 回复                                   |
| AI 能力  | `Tool`、`Reasoning`、`Activity`      | 工具调用结果、推理过程、活动（知识库/流程/引用文档） |
| 系统     | `System`、`Info`、`Guide`、`Loading` | 系统消息、信息提示、引导、加载                       |
| 控制     | `Pause`、`Placeholder`、`Hidden*`    | 暂停、占位、隐藏系列                                 |
| 模板     | `Template*`                          | 预设对话模板系列                                     |

通过 `declare global { interface AIBluekingMessageMap }` 注册自定义消息角色，类型自动合并到 `Message` 联合中。

### 流式渲染

通过 `MessageStatus` 管理消息生命周期：

```
Pending → Streaming → Complete / Error / Stop
```

业务层在流式阶段逐步追加 `content` 字符，`MarkdownContent` 实时解析并渲染，自动补全未闭合的 Markdown 语法。

### 多级内容渲染管线

```
AssistantMessage
  → ContentRender（按内容类型分发）
    → MarkdownContent（MarkdownIt 解析）
      → CodeContent（代码高亮，180+ 语言）
      → LatexContent（KaTeX 公式）
      → MermaidContent（图表）
      → VNodeRenderer（HTML + DOMPurify）
```

### 快捷指令

- **按钮引导**：空对话时展示 `ShortcutBtns`，引导用户发起对话
- **输入触发**：`/` 唤出 Prompt 列表，`@` 唤出资源（工具/MCP/文档）列表
- **表单交互**：`ShortcutRender` 支持文本、数字、下拉、复选、单选、开关等表单组件
- **表单填回**：`fillBack` 字段控制表单值自动回填到输入框

### 工具调用

`AssistantMessage` 可包含 `toolCalls` 数组，每个 `ToolCall` 含 `function`（名称、参数、描述）和可选的 `toolMessage`（执行结果）。`useMessageGroup` 自动将 `ToolMessage` 注入到对应的 `toolCall.toolMessage`。

### 划词选择

`AiSelection` 监听 `document` 级选中事件，在选中文本上方弹出操作浮窗。页面建议只挂载一个实例。

### 图片与文件

- `AiImage`：图片展示（加载状态、错误重试）
- `ImagePreview`：全屏预览（缩放、旋转、下载）
- `ImagePreviewGroup`：通过 `provide/inject` + `Map<symbol>` 管理多图
- `FileContent`：文件类型展示
- `FileUploadBtn`：上传按钮（`ChatInput` 内置，也可独立使用）

## 技术栈

| 依赖                          | 用途                                         |
| ----------------------------- | -------------------------------------------- |
| **Vue 3**                     | Composition API + `<script setup>`           |
| **TypeScript**                | 完整类型定义，泛型 + 全局类型扩展            |
| **bkui-vue**                  | 蓝鲸 UI 组件库（表单、弹窗、Tab 等基础组件） |
| **highlight.js**              | 代码高亮（180+ 语言）                        |
| **KaTeX**                     | LaTeX 公式渲染                               |
| **Mermaid**                   | 图表渲染                                     |
| **DOMPurify**                 | HTML 安全过滤                                |
| **@modelcontextprotocol/sdk** | MCP 服务端                                   |

## 兼容性

- Vue 3.5+
- 现代浏览器（Chrome、Firefox、Safari、Edge 最新版）
- 不支持 IE

## 下一步

- [快速上手](./getting-started.md) — 安装、最小示例、完整示例
- [架构总览](./architecture.md) — 组件层级、数据流、渲染管线
- [设计理念](./design-philosophy.md) — AI 优先策略、能力域架构、API 原则
- [用例食谱](./recipes.md) — 11 个常见场景的最小代码
- [自定义消息类型](./ai/custom-message.md) — 类型扩展完整流程
- [MCP 服务](./ai/mcp.md) — AI IDE 集成指南

## 开源协议

本项目基于 MIT 协议开源。
