---
name: 组件总览
slug: components
kind: guide
description: '@blueking/chat-x 组件能力地图，按对话搭建、消息系统、内容渲染、输入交互、Agent 能力等场景组织。'
aiSummary: >
  @blueking/chat-x 组件文档以 src/components 为真相源，按能力域组织。
  推荐先从 ChatContainer、MessageContainer、ChatInput、MessageRender、ContentRender 五个入口理解组件链路。
---

# 组件总览

`@blueking/chat-x` 的组件现在按 **能力域** 组织，而不是按实现层级组织。开发时请先判断“我要完成什么能力”，再进入对应文档。

> 本轮文档以 `packages/chat-x/src/components` 为真相源校准。完整覆盖关系见 [组件源码审计清单](./inventory.md)。

## 快速选择

| 场景 | 推荐入口 |
| ---- | -------- |
| 接入完整聊天界面 | [ChatContainer](./setup/chat-container.md) |
| 自定义聊天布局 | [MessageContainer](./setup/message-container.md) + [ChatInput](./input/chat-input.md) |
| 渲染一条消息 | [MessageRender](./message/message-render.md) |
| 渲染消息正文内容 | [ContentRender](./rendering/content-render.md) |
| 渲染 Markdown / 代码 / 公式 / 图表 | [MarkdownContent](./rendering/markdown-content.md) |
| 构建快捷指令与命令输入 | [ChatInput](./input/chat-input.md)、[AiSlashInput](./input/ai-slash-input.md)、[ShortcutRender](./input/shortcut-render.md) |
| 处理 ToolCall / HITL 中断 | [ToolcallRender](./agent/toolcall-render.md)、[InterruptMessage](./agent/interrupt-message.md) |
| 展示 FlowAgent / 知识召回活动 | [FlowAgentContent](./agent/flow-agent-content.md)、[KnowledgeRagContent](./agent/knowledge-rag-content.md) |
| 图片预览与文件展示 | [AiImage](./medias/ai-image.md)、[ImagePreviewGroup](./medias/image-preview-group.md)、[FileContent](./medias/file-content.md) |

## 能力域

### 搭建对话

| 组件 | 说明 |
| ---- | ---- |
| [ChatContainer](./setup/chat-container.md) | 完整对话容器，组合消息列表、输入区、快捷指令、执行摘要、选择分享与自定义 Tab。 |
| [MessageContainer](./setup/message-container.md) | 消息列表容器，负责消息分组、滚动、工具栏与消息插槽透传。 |

### 消息系统

| 组件 | 说明 |
| ---- | ---- |
| [MessageRender](./message/message-render.md) | 按 `message.role` 分发到具体消息组件。 |
| [AssistantMessage](./message/assistant-message.md) | 渲染 AI 回复主体、工具调用与文件内容。 |
| [UserMessage](./message/user-message.md) | 渲染用户消息，包含编辑态、引用、文件与快捷指令确认。 |
| [ReasoningMessage](./message/reasoning-message.md) | 渲染推理过程。 |
| [ToolMessage](./message/tool-message.md) | 渲染工具返回内容。 |
| [ActivityMessage](./message/activity-message.md) | 按活动类型分发 FlowAgent、知识召回、引用文档等内容。 |
| [InfoMessage](./message/info-message.md) | 渲染系统信息提示。 |
| [LoadingMessage](./message/loading-message.md) | 渲染消息列表中的加载占位。 |

### 内容渲染

| 组件 | 说明 |
| ---- | ---- |
| [ContentRender](./rendering/content-render.md) | 按 `MessageContentType` 分发正文内容。 |
| [MarkdownContent](./rendering/markdown-content.md) | Markdown 主渲染器，集成代码、公式、错误降级和 `codeHeader` 插槽。 |
| [CodeContent](./rendering/code-content.md) | 代码块高亮与复制。 |
| [LatexContent](./rendering/latex-content.md) | LaTeX 公式渲染。 |
| [MermaidContent](./rendering/mermaid-content.md) | Mermaid 图表渲染。 |
| [AnimationText](./rendering/animation-text.md) | 流式文本动画。 |
| [TextContent](./rendering/text-content.md) | 纯文本渲染。 |
| [CiteContent](./rendering/cite-content.md) | 引用片段渲染。 |
| [ReferenceContent](./rendering/reference-content.md) | 引用来源列表渲染。 |
| [KeyValueContent](./rendering/key-value-content.md) | 键值结构展示。 |
| [DescPanel](./rendering/desc-panel.md) | 文本或 JSON 描述面板。 |
| [CommonErrorContent](./rendering/common-error-content.md) | 通用错误内容。 |

### 媒体文件

| 组件 | 说明 |
| ---- | ---- |
| [AiImage](./medias/ai-image.md) | 图片展示与预览入口。 |
| [ImagePreview](./medias/image-preview.md) | 图片预览容器。 |
| [ImagePreviewGroup](./medias/image-preview-group.md) | 多图预览上下文。 |
| [PreviewToolbar](./medias/preview-toolbar.md) | 图片预览工具栏。 |
| [FileContent](./medias/file-content.md) | 文件附件展示。 |
| [ImageContent](./medias/image-content.md) | Markdown 图片 token 渲染。 |

### 输入交互

| 组件 | 说明 |
| ---- | ---- |
| [ChatInput](./input/chat-input.md) | 聊天主输入区。 |
| [AiSlashInput](./input/ai-slash-input.md) | 富文本命令输入，支持 `/` Prompt 与 `@` 资源标签。 |
| [AiSlashEditor](./input/ai-slash-editor.md) | 富文本编辑器实现。 |
| [AiSlashMenu](./input/ai-slash-menu.md) | 资源选择菜单。 |
| [AiPromptList](./input/ai-prompt-list.md) | Prompt 列表。 |
| [InputAttachment](./input/input-attachment.md) | 输入附件区布局。 |
| [InputInfoAlert](./input/input-info-alert.md) | 输入提示条。 |
| [FileUploadBtn](./input/file-upload-btn.md) | 文件选择按钮。 |
| [ShortcutRender](./input/shortcut-render.md) | 快捷指令表单渲染。 |
| [ShortcutBtn](./input/shortcut-btn.md) | 单个快捷指令按钮。 |
| [ShortcutBtns](./input/shortcut-btns.md) | 快捷指令按钮组。 |
| [AiSelection](./input/ai-selection.md) | 划词选择浮窗。 |
| [SelectionFooter](./input/selection-footer.md) | 多选操作栏。 |

### Agent 能力

| 组件 | 说明 |
| ---- | ---- |
| [ToolcallRender](./agent/toolcall-render.md) | 工具调用渲染器。 |
| [ToolApprovalCard](./agent/tool-approval-card.md) | 工具审批卡片。 |
| [InterruptMessage](./agent/interrupt-message.md) | 中断消息渲染器。 |
| [UserQuestionCard](./agent/user-question-card.md) | 用户问题中断交互面板。 |
| [UserQuestionChoice](./agent/user-question-choice.md) | 用户问题默认选择题渲染。 |
| [UserQuestionAnsweredCard](./agent/user-question-answered-card.md) | 用户问题回答回显。 |
| [UserQuestionOption](./agent/user-question-option.md) | 用户问题选项行。 |
| [ExecutionSummary](./agent/execution-summary.md) | 执行摘要面板。 |
| [FlowAgentContent](./agent/flow-agent-content.md) | FlowAgent 执行内容。 |
| [FlowAgentNodeDetail](./agent/flow-agent-node-detail.md) | FlowAgent 节点详情。 |
| [KnowledgeRagContent](./agent/knowledge-rag-content.md) | 知识召回内容。 |
| [ReferenceDocContent](./agent/reference-doc-content.md) | 引用文档活动内容。 |
| [DetailSection](./agent/detail-section.md) | 详情分段容器。 |
| [SimpleTable](./agent/simple-table.md) | 简易表格。 |

### 工具与反馈

| 组件 | 说明 |
| ---- | ---- |
| [MessageTools](./feedback/message-tools.md) | 消息工具栏。 |
| [ToolBtn](./feedback/tool-btn.md) | 工具栏图标按钮。 |
| [DeleteTool](./feedback/delete-tool.md) | 删除确认按钮。 |
| [UserFeedback](./feedback/user-feedback.md) | 用户反馈弹层。 |
| [ScrollBtn](./feedback/scroll-btn.md) | 停止生成 / 返回底部按钮。 |

### 辅助能力

| 组件 | 说明 |
| ---- | ---- |
| [ActivityLayout](./helper/activity-layout.md) | 活动消息折叠布局。 |
| [AiLoading](./helper/ai-loading.md) | 三点加载动画。 |
| [MessageLoading](./helper/message-loading.md) | 品牌加载动画。 |
| [HighlightKeyword](./helper/highlight-keyword.md) | 关键词高亮。 |
| [VNodeRenderer](./helper/vnode-renderer.md) | Markdown token 到 VNode 的内部渲染桥。 |
| [QuestionsContainer](./helper/questions-container.md) | 空源码占位，无可用功能。 |
| [SelectionQuestion](./helper/selection-question.md) | 空源码占位，无可用功能。 |
