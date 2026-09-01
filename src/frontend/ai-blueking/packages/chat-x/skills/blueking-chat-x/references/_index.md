# @blueking/chat-x 能力地图（自动生成）

> 由 `scripts/generate-references.mjs` 从 `wikis/` 生成，请勿手改。
> 查某个能力时：先在本索引定位 slug，再读对应 `path` 的 reference 文档。

> 生成时间：2026-09-01T03:51:31.378Z

## 组件（按能力域）

### 对话搭建

- **ChatContainer 聊天容器** — 完整对话容器，组合消息列表、输入区、模型选择、快捷指令、执行摘要、分享选择和自定义 Tab。 → `components/chat-container.md`
- **MessageContainer 消息列表容器** — 负责消息分组渲染、滚动控制、工具栏和消息插槽透传。 → `components/message-container.md`

### 消息系统

- **ActivityMessage 活动消息** — 按 activityType 分发 FlowAgent、知识召回、引用文档等活动内容。 → `components/activity-message.md`
- **AssistantMessage AI 助手消息** — 渲染助手消息主体、工具调用与文件产物，默认插槽可覆盖正文渲染。 → `components/assistant-message.md`
- **FileArtifactPanel 文件产物预览** — 汇总当前会话全部文件产物，支持搜索、选中与分类型预览，挂载在 ChatContainer 侧栏「文件产物」Tab。 → `components/file-artifact-panel.md`
- **InfoMessage 信息消息** — 渲染居中的系统信息提示。 → `components/info-message.md`
- **LoadingMessage 加载消息** — 消息列表中的加载占位，默认使用 AiLoading，也支持默认插槽覆盖。 → `components/loading-message.md`
- **MessageRender 消息渲染器** — 按 message.role 分发到用户、助手、工具、推理、活动、中断等消息组件。 → `components/message-render.md`
- **ReasoningMessage 推理消息** — 渲染推理过程，覆盖加载、错误与 Markdown 内容展示。 → `components/reasoning-message.md`
- **ToolMessage 工具消息** — 渲染工具返回内容，JSON 场景交给 DescPanel + HighlightKeyword 展示。 → `components/tool-message.md`
- **UserMessage 用户消息** — 渲染用户消息，支持纯文本、键值引用、文件附件和编辑态输入。 → `components/user-message.md`

### 内容渲染

- **AnimationText 动画文本** — 按文本增量播放流式动画。 → `components/animation-text.md`
- **CiteContent 引用内容** — 渲染输入或消息中的引用片段。 → `components/cite-content.md`
- **CodeContent 代码块** — 渲染 Markdown 代码块，支持高亮、复制和 header 插槽。 → `components/code-content.md`
- **CommonErrorContent 错误内容** — 展示统一错误提示内容。 → `components/common-error-content.md`
- **ContentRender 内容渲染器** — 按 MessageContentType 分发 Markdown、文本、引用、键值、图片等内容。 → `components/content-render.md`
- **DescPanel 描述面板** — 将文本或 JSON 内容降级为可读描述面板。 → `components/desc-panel.md`
- **KeyValueContent 键值内容** — 以键值列表展示结构化内容。 → `components/key-value-content.md`
- **LatexContent LaTeX 公式** — 使用 KaTeX 渲染 LaTeX 公式内容。 → `components/latex-content.md`
- **MarkdownContent Markdown 内容渲染** — Markdown 主渲染器，集成代码块、公式、错误降级和 codeHeader 插槽。 → `components/markdown-content.md`
- **MermaidContent Mermaid 图表** — 渲染 Mermaid 图表并处理渲染事件。 → `components/mermaid-content.md`
- **ReferenceContent 引用来源** — 渲染引用文档/来源列表。 → `components/reference-content.md`
- **TextContent 文本内容** — 渲染纯文本内容。 → `components/text-content.md`

### 媒体文件

- **AiImage 图片展示** — 图片展示组件，组合加载、错误、预览和 extra 插槽。 → `components/ai-image.md`
- **FileContent 文件内容** — 渲染文件附件，支持图片预览和下载事件。 → `components/file-content.md`
- **ImageContent 图片内容** — 渲染 Markdown 图片 token。 → `components/image-content.md`
- **ImagePreview 图片预览** — 图片全屏预览容器，支持缩放、旋转、下载工具栏。 → `components/image-preview.md`
- **ImagePreviewGroup 图片预览组** — 通过 provide/inject 管理同组图片预览。 → `components/image-preview-group.md`
- **PreviewToolbar 图片预览工具栏** — 图片预览的缩放、旋转、下载等工具按钮。 → `components/preview-toolbar.md`

### 输入交互

- **AiPromptList Prompt 列表** — \ Prompt 选择列表，供 AiSlashInput 插入模板文本。 → `components/ai-prompt-list.md`
- **AiSelection 划词选择** — 监听选中文本并展示快捷操作浮窗。 → `components/ai-selection.md`
- **AiSkillList Skill 列表** — / Skill 选择列表，供 AiSlashInput 插入 Skill 标签。 → `components/ai-skill-list.md`
- **AiSlashEditor 富文本编辑器** — 旧版富文本编辑器实现，封装 command selection 与提示菜单。 → `components/ai-slash-editor.md`
- **AiSlashInput 富文本命令输入** — ChatInput 内部富文本输入，支持 / Skill、\ Prompt 与 @ 资源标签。 → `components/ai-slash-input.md`
- **AiSlashMenu 资源菜单** — @ 资源选择菜单，展示资源项供 AiSlashInput 插入标签。 → `components/ai-slash-menu.md`
- **ChatInput 聊天输入框** — 聊天输入区，组合富文本输入、快捷指令、附件、引用、发送/停止等交互。 → `components/chat-input.md`
- **FileUploadBtn 文件上传按钮** — 文件选择按钮，封装 input[type=file] 并输出选择事件。 → `components/file-upload-btn.md`
- **InputAttachment 输入附件区** — ChatInput 底部附件区布局，承载快捷按钮、文件与发送图标。 → `components/input-attachment.md`
- **InputInfoAlert 输入提示条** — ChatInput 上方的信息提示条。 → `components/input-info-alert.md`
- **ModelSelector 模型选择器** — 聊天输入区的模型下拉选择器，支持搜索过滤、能力标签与键盘导航。 → `components/model-selector.md`
- **SelectionFooter 多选操作栏** — 消息多选/分享模式下的底部操作栏。 → `components/selection-footer.md`
- **ShortcutBtn 快捷指令按钮** — 单个快捷指令按钮，支持默认/append 插槽和 expose focus。 → `components/shortcut-btn.md`
- **ShortcutBtns 快捷指令按钮组** — 快捷指令列表入口，内部组合多个 ShortcutBtn。 → `components/shortcut-btns.md`
- **ShortcutRender 快捷指令表单** — 渲染快捷指令 components 表单并回传确认数据。 → `components/shortcut-render.md`

### Agent 能力

- **DetailSection 详情分段** — FlowAgent 节点详情中的标题/内容分段容器。 → `components/detail-section.md`
- **ExecutionSummary 执行摘要** — 按消息流提取执行摘要，支持关键词定位和消息渲染。 → `components/execution-summary.md`
- **FlowAgentContent FlowAgent 执行内容** — 渲染 FlowAgent 任务/节点执行状态、耗时、详情入口和自定义 Tab 联动。 → `components/flow-agent-content.md`
- **FlowAgentNodeDetail FlowAgent 节点详情** — 展示 FlowAgent 节点输入、输出、异常、耗时等详情。 → `components/flow-agent-node-detail.md`
- **InterruptMessage 中断消息** — 渲染 human-in-the-loop 中断消息，分发工具审批，并按 reason 回显 resume 结果。 → `components/interrupt-message.md`
- **KnowledgeRagContent 知识召回内容** — 渲染知识召回活动，包含加载态、Markdown 内容与引用来源。 → `components/knowledge-rag-content.md`
- **ReferenceDocContent 引用文档活动** — 渲染引用文档类活动内容，复用 ActivityLayout 与 ReferenceContent。 → `components/reference-doc-content.md`
- **SimpleTable 简易表格** — FlowAgent 节点详情中的轻量表格展示组件。 → `components/simple-table.md`
- **ToolApprovalCard 工具审批卡片** — 渲染 AIDevToolApproval 中断的审批信息与取消/刷新操作，readonly prop 支持纯只读展示。 → `components/tool-approval-card.md`
- **ToolcallRender 工具调用渲染器** — 渲染 assistant toolCalls，展示工具调用状态、参数和结果。 → `components/toolcall-render.md`
- **UserQuestionAnsweredCard 用户问题回答回显** — 在 UserQuestion resume 成功后回显用户回答或取消状态。 → `components/user-question-answered-card.md`
- **UserQuestionCard 用户问题中断** — 渲染 UserQuestion 中断的待回答面板；一次一题分页切换，支持单选/多选、Others、跳过与已完成进度。 → `components/user-question-card.md`
- **UserQuestionChoice 用户问题选择题** — UserQuestionCard 默认的选择题渲染组件，封装单选/多选、Others 输入与答案组装。 → `components/user-question-choice.md`
- **UserQuestionOption 用户问题选项** — UserQuestionChoice 内部选项行，处理单选/多选状态和 Others 输入。 → `components/user-question-option.md`

### 工具与反馈

- **DeleteTool 删除确认按钮** — 消息删除二次确认工具。 → `components/delete-tool.md`
- **MessageTime 消息时间** — 按「今天 / 昨天 / 今年内 / 跨年」四档格式展示消息创建时间。 → `components/message-time.md`
- **MessageTools 消息工具栏** — 消息悬浮工具栏，组合复制、删除、反馈等工具按钮。 → `components/message-tools.md`
- **ScrollBtn 滚动按钮** — 停止生成或返回底部等滚动/状态按钮。 → `components/scroll-btn.md`
- **ToolBtn 工具按钮** — 工具栏图标按钮。 → `components/tool-btn.md`
- **UserFeedback 用户反馈** — 用户反馈弹层，提交踩/反馈原因。 → `components/user-feedback.md`

### 辅助能力

- **ActivityLayout 活动布局** — 活动消息的折叠布局容器，提供 title/default 插槽。 → `components/activity-layout.md`
- **AiLoading 三点加载** — 小尺寸 AI 加载动效。 → `components/ai-loading.md`
- **FileIcon 文件类型图标** — 按文件扩展名渲染对应类型图标，尺寸随外层 font-size 自适应。 → `components/file-icon.md`
- **HighlightKeyword 关键词高亮** — 根据注入关键词高亮文本片段。 → `components/highlight-keyword.md`
- **MessageLoading 品牌加载** — 带品牌图标和逐字渐变动画的加载组件。 → `components/message-loading.md`
- **QuestionsContainer 问题容器占位** — 源码为空文件，没有 props、emits、slots 或渲染能力；不建议作为功能组件使用。 → `components/questions-container.md`
- **SelectionQuestion 选择问题占位** — 源码为空文件，没有 props、emits、slots 或渲染能力；不建议作为功能组件使用。 → `components/selection-question.md`
- **VNodeRenderer VNode 渲染器** — 将 Markdown token 转成 VNode 的内部渲染桥。 → `components/vnode-renderer.md`

## Composables 组合式函数

- **useAnimationText** — 文本淡入动画的组合式函数。将响应式文本按**增量**拆分为独立 chunk，每个新增 chunk 对应一次淡入动画，适用于 AI 流式输出的逐段渐显效果。 → `composables/use-animation-text.md`
- **useArtifactPreview** — Provider/Consumer 模式的文件产物预览状态管理，用于 ChatContainer 侧栏「文件产物」Tab 的命中与切换。 Provider 在 ChatContainer 中创建，Consumer 在深层文件卡片中注入使用。 → `composables/use-artifact-preview.md`
- **useClipboard** — 复制文本到剪贴板的组合式函数。内置两级降级策略，并自动通过 bkui-vue `Message` 提示复制结果，调用方无需关心成功/失败处理。 → `composables/use-clipboard.md`
- **useCommandSelection** — 为 `edix` 富文本编辑器提供光标位置追踪能力的组合式函数。内部封装一个 `EditorCommand`，由编辑器调用后将光标的行列信息存入响应式变量，供后续编辑命令（如插入 tag、删除关键词）精确定位。 → `composables/use-command-selection.md`
- **useContainerScroll** — 为消息容器提供滚动控制的组合式函数对，通过 **Provider/Consumer** 模式在父子组件间共享滚动状态。 → `composables/use-container-scroll.md`
- **useCustomTab** — Provider/Consumer 模式的自定义 Tab 管理，用于 `ChatContainer` 侧边栏的 Tab 动态管理。Provider 在 `ChatContainer` 中创建，Consumer 在任意后代组件中注入使用。 → `composables/use-custom-tab.md`
- **useFlowNodeActions** — 聚合 FlowAgent 节点行尾操作（详情 / 重试 / 跳过）为声明式视图模型列表，显隐与 resume 回调收敛于此。 → `composables/use-flow-node-actions.md`
- **useFullScreen** — 基于浏览器原生 Fullscreen API 的全屏控制组合式函数，自动嗅探标准与 WebKit 前缀，状态与 ESC 退出保持同步。 → `composables/use-full-screen.md`
- **useGlobalConfig** — 在聊天根容器与子组件之间通过 provide/inject 共享全局展示配置（字号主题档位、是否支持上传、消息时间时区等）。 → `composables/use-global-config.md`
- **useMenuKeydown** — 为弹出菜单提供键盘导航能力的组合式函数。在 `onMounted` 时于 **`window` 捕获阶段**注册 `keydown` 监听，在 `onScopeDispose` 时自动移除，通过 `menuRef.offsetParent` 检测菜单可见性来决定是否响应按键。 → `composables/use-menu-keydown.md`
- **useMessageGroup** — 核心消息分组逻辑，将原始 `Message[]` 数组转换为结构化的 `MessageGroup[]`。处理 Tool 消息合并、Loading 自动注入、执行摘要过滤和消息多选/分享等逻辑。 → `composables/use-message-group.md`
- **useObserverVisibleList** — 基于 `ResizeObserver` 的容器宽度感知组合式函数：遍历列表项的实际 `offsetWidth`，使用贪心算法计算在容器中能完整显示的项目子集，并为"更多"按钮动态预留空间。 → `composables/use-observer-visible-list.md`
- **useParentScrolling** — 向上递归查找**最近可滚动祖先**，监听其 `scroll` / `scrollend` 事件，提供 `isScrolling` 状态。常用于滚动时自动关闭浮层、禁用交互等场景。 → `composables/use-parent-scrolling.md`

## 类型定义

- **常量枚举** — `@blueking/chat-x` 导出的常量和枚举类型。 → `types/constants.md`
- **中断类型 Interrupt** — AG-UI human-in-the-loop 中断相关类型，含 Interrupt、UserQuestion、InterruptMessage 与 resume 回调。 → `types/interrupt.md`
- **消息类型** — `@blueking/chat-x` 提供了完整的消息类型定义，用于构建 AI 对话消息。 → `types/messages.md`
- **用户问题 Schema** — 历史 human-in-the-loop 用户问题 JSON Schema 工具；新 UserQuestion 中断协议以 Interrupt 文档为准。 → `types/schema.md`

## 主题

- **主题配置** — `@blueking/chat-x` 使用 SCSS 变量和 CSS 类来控制样式，支持通过覆盖变量或样式来自定义主题。 → `theme/theme.md`
