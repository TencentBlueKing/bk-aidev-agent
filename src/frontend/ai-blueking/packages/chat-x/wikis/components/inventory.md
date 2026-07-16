---
name: 组件源码审计清单
slug: component-inventory
kind: guide
description: src/components 与 wiki 文档覆盖关系。
aiSummary: >
  以 packages/chat-x/src/components 为真相源列出所有组件文档覆盖情况。
---

# 组件源码审计清单

本文以 `packages/chat-x/src/components` 为真相源，列出源码组件与 wiki 文档的覆盖关系。

| 文档 | 能力域 | 源码位置 | 状态 |
| ---- | ------ | -------- | ---- |
| [DetailSection 详情分段](/components/agent/detail-section) | Agent 能力 | `src/components/chat-content/flow-agent-content/detail-section.vue` | 已覆盖 |
| [ExecutionSummary 执行摘要](/components/agent/execution-summary) | Agent 能力 | `src/components/execution-summary/execution-summary.vue` | 已覆盖 |
| [FlowAgentContent FlowAgent 执行内容](/components/agent/flow-agent-content) | Agent 能力 | `src/components/chat-content/flow-agent-content/flow-agent-content.vue` | 已覆盖 |
| [FlowAgentNodeDetail FlowAgent 节点详情](/components/agent/flow-agent-node-detail) | Agent 能力 | `src/components/chat-content/flow-agent-content/flow-agent-node-detail.vue` | 已覆盖 |
| [InterruptMessage 中断消息](/components/agent/interrupt-message) | Agent 能力 | `src/components/chat-message/interrupt-message/interrupt-message.vue` | 已覆盖 |
| [KnowledgeRagContent 知识召回内容](/components/agent/knowledge-rag-content) | Agent 能力 | `src/components/chat-content/knowledge-rag-content/knowledge-rag-content.vue` | 已覆盖 |
| [ReferenceDocContent 引用文档活动](/components/agent/reference-doc-content) | Agent 能力 | `src/components/chat-content/reference-doc-content/reference-doc-content.vue` | 已覆盖 |
| [SimpleTable 简易表格](/components/agent/simple-table) | Agent 能力 | `src/components/chat-content/flow-agent-content/simple-table.vue` | 已覆盖 |
| [ToolApprovalCard 工具审批卡片](/components/agent/tool-approval-card) | Agent 能力 | `src/components/chat-message/interrupt-message/tool-approval-card.vue` | 已覆盖 |
| [ToolcallRender 工具调用渲染器](/components/agent/toolcall-render) | Agent 能力 | `src/components/tool-call/toolcall-render/toolcall-render.vue` | 已覆盖 |
| [UserQuestionAnsweredCard 用户问题回答回显](/components/agent/user-question-answered-card) | Agent 能力 | `src/components/chat-message/interrupt-message/user-question/user-question-answered-card.vue` | 已覆盖 |
| [UserQuestionCard 用户问题中断](/components/agent/user-question-card) | Agent 能力 | `src/components/chat-message/interrupt-message/user-question/user-question-card.vue` | 已覆盖 |
| [UserQuestionChoice 用户问题选择题](/components/agent/user-question-choice) | Agent 能力 | `src/components/chat-message/interrupt-message/user-question/user-question-choice.vue` | 已覆盖 |
| [UserQuestionOption 用户问题选项](/components/agent/user-question-option) | Agent 能力 | `src/components/chat-message/interrupt-message/user-question/user-question-option.vue` | 已覆盖 |
| [DeleteTool 删除确认按钮](/components/feedback/delete-tool) | 工具与反馈 | `src/components/message-tools/delete-tool/delete-tool.vue` | 已覆盖 |
| [MessageTools 消息工具栏](/components/feedback/message-tools) | 工具与反馈 | `src/components/message-tools/message-tools.vue` | 已覆盖 |
| [ScrollBtn 滚动按钮](/components/feedback/scroll-btn) | 工具与反馈 | `src/components/ai-buttons/scroll-btn/scroll-btn.vue` | 已覆盖 |
| [ToolBtn 工具按钮](/components/feedback/tool-btn) | 工具与反馈 | `src/components/ai-buttons/tool-btn/tool-btn.vue` | 已覆盖 |
| [UserFeedback 用户反馈](/components/feedback/user-feedback) | 工具与反馈 | `src/components/message-tools/user-feedback/user-feedback.vue` | 已覆盖 |
| [ActivityLayout 活动布局](/components/helper/activity-layout) | 辅助能力 | `src/components/chat-content/activity-layout/activity-layout.vue` | 已覆盖 |
| [AiLoading 三点加载](/components/helper/ai-loading) | 辅助能力 | `src/components/ai-loading/ai-loading.vue` | 已覆盖 |
| [HighlightKeyword 关键词高亮](/components/helper/highlight-keyword) | 辅助能力 | `src/components/highlight-keyword/highlight-keyword.ts` | 已覆盖 |
| [MessageLoading 品牌加载](/components/helper/message-loading) | 辅助能力 | `src/components/message-loading/message-loading.vue` | 已覆盖 |
| [QuestionsContainer 问题容器占位](/components/helper/questions-container) | 辅助能力 | `src/components/ai-questions/questions-container.vue` | 空源码占位 |
| [SelectionQuestion 选择问题占位](/components/helper/selection-question) | 辅助能力 | `src/components/ai-questions/selection-question.vue` | 空源码占位 |
| [VNodeRenderer VNode 渲染器](/components/helper/vnode-renderer) | 辅助能力 | `src/components/chat-content/vnode-renderer.ts` | 已覆盖 |
| [AiPromptList Prompt 列表](/components/input/ai-prompt-list) | 输入交互 | `src/components/chat-input/ai-slash-input/ai-prompt-list/ai-prompt-list.vue` | 已覆盖 |
| [AiSelection 划词选择](/components/input/ai-selection) | 输入交互 | `src/components/ai-selection/ai-selection.vue` | 已覆盖 |
| [AiSkillList Skill 列表](/components/input/ai-skill-list) | 输入交互 | `src/components/chat-input/ai-slash-input/ai-skill-list/ai-skill-list.vue` | 已覆盖 |
| [AiSlashEditor 富文本编辑器](/components/input/ai-slash-editor) | 输入交互 | `src/components/chat-input/ai-slash-editor/ai-slash-editor.vue` | 已覆盖 |
| [AiSlashInput 富文本命令输入](/components/input/ai-slash-input) | 输入交互 | `src/components/chat-input/ai-slash-input/ai-slash-input.vue` | 已覆盖 |
| [AiSlashMenu 资源菜单](/components/input/ai-slash-menu) | 输入交互 | `src/components/chat-input/ai-slash-input/ai-slash-menu/ai-slash-menu.vue` | 已覆盖 |
| [ChatInput 聊天输入框](/components/input/chat-input) | 输入交互 | `src/components/chat-input/chat-input.vue` | 已覆盖 |
| [FileUploadBtn 文件上传按钮](/components/input/file-upload-btn) | 输入交互 | `src/components/ai-buttons/file-upload-btn/file-upload-btn.vue` | 已覆盖 |
| [InputAttachment 输入附件区](/components/input/input-attachment) | 输入交互 | `src/components/chat-input/input-attachment/input-attachment.vue` | 已覆盖 |
| [InputInfoAlert 输入提示条](/components/input/input-info-alert) | 输入交互 | `src/components/chat-input/input-info-alert.vue` | 已覆盖 |
| [SelectionFooter 多选操作栏](/components/input/selection-footer) | 输入交互 | `src/components/selection-footer/selection-footer.vue` | 已覆盖 |
| [ShortcutBtn 快捷指令按钮](/components/input/shortcut-btn) | 输入交互 | `src/components/ai-shortcut/shortcut-btn/shortcut-btn.vue` | 已覆盖 |
| [ShortcutBtns 快捷指令按钮组](/components/input/shortcut-btns) | 输入交互 | `src/components/ai-shortcut/shortcut-btns/shortcut-btns.vue` | 已覆盖 |
| [ShortcutRender 快捷指令表单](/components/input/shortcut-render) | 输入交互 | `src/components/ai-shortcut/shortcut-render/shortcut-render.vue` | 已覆盖 |
| [AiImage 图片展示](/components/medias/ai-image) | 媒体文件 | `src/components/image-preview/image.vue` | 已覆盖 |
| [FileContent 文件内容](/components/medias/file-content) | 媒体文件 | `src/components/chat-content/file-content/file-content.vue` | 已覆盖 |
| [ImageContent 图片内容](/components/medias/image-content) | 媒体文件 | `src/components/markdown-token/image-content/image-content.vue` | 已覆盖 |
| [ImagePreview 图片预览](/components/medias/image-preview) | 媒体文件 | `src/components/image-preview/image-preview.vue` | 已覆盖 |
| [ImagePreviewGroup 图片预览组](/components/medias/image-preview-group) | 媒体文件 | `src/components/image-preview/image-preview-group.vue` | 已覆盖 |
| [PreviewToolbar 图片预览工具栏](/components/medias/preview-toolbar) | 媒体文件 | `src/components/image-preview/preview-toolbar.vue` | 已覆盖 |
| [ActivityMessage 活动消息](/components/message/activity-message) | 消息系统 | `src/components/chat-message/activity-message/activity-message.vue` | 已覆盖 |
| [AssistantMessage AI 助手消息](/components/message/assistant-message) | 消息系统 | `src/components/chat-message/assistant-message/assistant-message.vue` | 已覆盖 |
| [InfoMessage 信息消息](/components/message/info-message) | 消息系统 | `src/components/chat-message/info-message/info-message.vue` | 已覆盖 |
| [LoadingMessage 加载消息](/components/message/loading-message) | 消息系统 | `src/components/chat-message/loading-message/loading-message.vue` | 已覆盖 |
| [MessageRender 消息渲染器](/components/message/message-render) | 消息系统 | `src/components/chat-message/message-render/message-render.vue` | 已覆盖 |
| [ReasoningMessage 推理消息](/components/message/reasoning-message) | 消息系统 | `src/components/chat-message/reasoning-message/reasoning-message.vue` | 已覆盖 |
| [ToolMessage 工具消息](/components/message/tool-message) | 消息系统 | `src/components/chat-message/tool-message/tool-message.vue` | 已覆盖 |
| [UserMessage 用户消息](/components/message/user-message) | 消息系统 | `src/components/chat-message/user-message/user-message.vue` | 已覆盖 |
| [AnimationText 动画文本](/components/rendering/animation-text) | 内容渲染 | `src/components/animation-text/animation-text.vue` | 已覆盖 |
| [CiteContent 引用内容](/components/rendering/cite-content) | 内容渲染 | `src/components/chat-content/cite-content/cite-content.vue` | 已覆盖 |
| [CodeContent 代码块](/components/rendering/code-content) | 内容渲染 | `src/components/markdown-token/code-content/code-content.vue` | 已覆盖 |
| [CommonErrorContent 错误内容](/components/rendering/common-error-content) | 内容渲染 | `src/components/chat-content/common-error-content/common-error-content.vue` | 已覆盖 |
| [ContentRender 内容渲染器](/components/rendering/content-render) | 内容渲染 | `src/components/chat-content/content-render/content-render.vue` | 已覆盖 |
| [DescPanel 描述面板](/components/rendering/desc-panel) | 内容渲染 | `src/components/tool-call/desc-panel/desc-panel.vue` | 已覆盖 |
| [KeyValueContent 键值内容](/components/rendering/key-value-content) | 内容渲染 | `src/components/chat-content/key-value-content/key-value-content.vue` | 已覆盖 |
| [LatexContent LaTeX 公式](/components/rendering/latex-content) | 内容渲染 | `src/components/markdown-token/latex-content/latex-content.vue` | 已覆盖 |
| [MarkdownContent Markdown 内容渲染](/components/rendering/markdown-content) | 内容渲染 | `src/components/chat-content/markdown-content/markdown-content.vue` | 已覆盖 |
| [MermaidContent Mermaid 图表](/components/rendering/mermaid-content) | 内容渲染 | `src/components/markdown-token/mermaid-content/mermaid-content.vue` | 已覆盖 |
| [ReferenceContent 引用来源](/components/rendering/reference-content) | 内容渲染 | `src/components/chat-content/reference-content/reference-content.vue` | 已覆盖 |
| [TextContent 文本内容](/components/rendering/text-content) | 内容渲染 | `src/components/chat-content/text-content/text-content.vue` | 已覆盖 |
| [ChatContainer 聊天容器](/components/setup/chat-container) | 对话搭建 | `src/components/chat-container/chat-container.vue` | 已覆盖 |
| [MessageContainer 消息列表容器](/components/setup/message-container) | 对话搭建 | `src/components/chat-message/message-container/message-container.vue` | 已覆盖 |
