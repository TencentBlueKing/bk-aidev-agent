---
name: 设计理念
slug: design-philosophy
category: guide
description: >
  @blueking/chat-x 的 AI 优先设计策略、原子设计方法论、功能域划分和 API 设计原则。
aiSummary: >
  chat-x 以 AI 优先为核心设计理念：结构化 frontmatter 元数据、AI 专用摘要、MCP 服务
  让 AI Agent 在 1-2 次工具调用内选择组件。架构上采用原子设计分层 + 6 功能域组织，
  API 设计遵循：只读 Props、回写 v-model、通知 emit、可覆盖函数 prop、自定义 slot、
  数据逻辑 composable。类型系统通过 declare global 声明合并实现零侵入扩展。
relatedComponents: []
sinceVersion: '1.0.0'
---

# 设计理念

## AI 优先设计

`@blueking/chat-x` 将 **AI Agent 作为第一优先级消费者**。这不仅影响文档结构，也贯穿组件 API、类型系统和工具链的设计。

### 为什么 AI 优先

传统组件库文档面向人类开发者，以视觉示例和自然语言为主。但在 AI 辅助开发时代，AI Agent（如 Cursor、Copilot）需要的是：

- **结构化元数据**：不是「读完 500 行文档才知道该用什么」，而是「2 句话告诉我这个组件干什么、必须传什么 prop」
- **可程序化查询**：不是「全文搜索」，而是「按功能域过滤、按角色查找」
- **清晰的关联图谱**：不是「散落在段落中的提及」，而是「这个组件和哪些组件配合使用、什么关系」

### 实现方式

| 策略                   | 实现                                                                                                                             | 消费者                           |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| **结构化 Frontmatter** | 每个组件/API 页面顶部 YAML 元数据：`name`、`slug`、`category`、`domain`、`description`、`aiSummary`、`relatedComponents`         | MCP 索引、AI Agent               |
| **AI 专用摘要**        | `aiSummary` 字段：2-4 句话，包含组件职责、必填 props、关键行为、常见搭配                                                         | MCP `get_component_doc` 返回头部 |
| **MCP 服务**           | 内置 `@modelcontextprotocol/sdk` Server，暴露 `list_components`（支持 domain/category 过滤）、`get_component_doc`、`search_docs` | AI IDE（Cursor 等）              |
| **文档清洗**           | `build-index` 自动剥离 `<script setup>`、`<div class="demo">` 等 VitePress 运行时代码，只保留对 AI 有用的内容                    | MCP 返回的文档                   |
| **功能域导航**         | 按使用场景（而非实现细节）组织组件，AI 可通过 `domain` 参数快速缩小范围                                                          | MCP `list_components` 过滤       |
| **关联组件图谱**       | `relatedComponents` 字段明确标注组件间关系和协作方式                                                                             | MCP 索引、页面底部               |

### AI Agent 的典型使用路径

```
AI Agent 收到需求：「添加一个带工具调用的 AI 对话界面」
    │
    ├─ 1. list_components(domain='message') → 找到 MessageContainer、AssistantMessage
    ├─ 2. get_component_doc(slug='assistant-message')
    │      → aiSummary 告知：需要 toolCalls 字段、搭配 ToolcallRender
    │      → relatedComponents 告知：与 message-container 配合使用
    ├─ 3. get_component_doc(slug='chat-container')
    │      → aiSummary 告知：一站式方案，传 messages 即可
    └─ 4. 生成代码，使用 ChatContainer + toolCalls 结构
```

整个过程 **4 次 MCP 调用**，无需阅读完整文档。

## 原子设计方法论

### 为什么分层

AI Chat 界面的复杂度在于**组合爆炸**：消息类型 × 内容格式 × 交互模式 × 布局变体。原子设计通过分层约束依赖方向：

```
原子组件 → 不依赖本库其他组件，只接收 Props
   ↑
分子组件 → 组合多个原子/分子组件，实现完整功能区域
   ↑
组合组件 → ChatContainer 封装标准对话页面
```

### 原子组件（Atomic）

**单一职责**，不导入本库其他业务组件。通过 Props 接收数据，通过 Events 通知父组件。

| 特征     | 说明                                              |
| -------- | ------------------------------------------------- |
| 依赖方向 | 只依赖 Vue、bkui-vue 等外部库，不依赖本库其他组件 |
| 状态管理 | 无内部业务状态，或只有极少的 UI 状态（如 hover）  |
| 可复用性 | 可在任意上下文中独立使用                          |

**代表**：`AiImage`（图片展示）、`CodeContent`（代码块高亮）、`ToolBtn`（工具按钮）、`ScrollBtn`（滚动按钮）、`MarkdownContent`（Markdown 渲染）

### 分子组件（Molecular）

**组合多个原子组件**，形成完整的功能区域。承担业务逻辑编排。

| 特征     | 说明                                                 |
| -------- | ---------------------------------------------------- |
| 依赖方向 | 导入本库原子组件和/或其他分子组件                    |
| 状态管理 | 管理区域级状态（如消息列表的滚动位置、工具栏的显隐） |
| 数据流   | 通过 Props 接收业务数据，通过回调/事件与父组件通信   |

**代表**：`MessageContainer`（消息列表 + 滚动 + 工具栏）、`ChatInput`（编辑器 + 附件 + 快捷指令）、`AssistantMessage`（正文 + 工具调用列表）、`ImagePreviewGroup`（多图预览管理）

### 组合组件（Composition）

`ChatContainer` 作为唯一的顶层组合组件，将分子组件 + `ResizeLayout` + `useMessageGroup` 等编排为标准对话页面，对外暴露 `ChatContainerProps`（合并了 `ChatInputProps` + `MessageContainerProps` 的大部分字段）。

**设计决策**：不提供多种组合组件，而是提供一个「完整版」 + 自由组合的「零件」，避免 API 表面积膨胀。

## 功能域划分

组件按使用者心智模型的 **6 个功能域** 组织，而非实现细节（文件路径、内部依赖）：

| 功能域         | 心智模型              | 核心组件                                                                                          |
| -------------- | --------------------- | ------------------------------------------------------------------------------------------------- |
| **消息展示**   | 「我要展示对话列表」  | MessageContainer、MessageRender、AssistantMessage、UserMessage、ReasoningMessage、ActivityMessage |
| **输入交互**   | 「我要让用户输入」    | ChatInput、AiSelection、ShortcutBtns、ShortcutRender、ChatContainer                               |
| **内容渲染**   | 「我要渲染富文本」    | ContentRender、MarkdownContent、CodeContent、LatexContent、MermaidContent、AnimationText          |
| **文件与图片** | 「我要处理附件/图片」 | AiImage、ImagePreview、ImagePreviewGroup、FileContent、FileUploadBtn                              |
| **工具与反馈** | 「我要加工具栏/反馈」 | MessageTools、ToolBtn、UserFeedback、ToolcallRender、DeleteTool                                   |
| **辅助组件**   | 「我要加辅助功能」    | ScrollBtn、DescPanel、HighlightKeyword、CiteContent、ExecutionSummary、SelectionFooter            |

**为什么这样分**：对齐开发者（和 AI Agent）的问题——「我在做消息列表 / 输入框 / 富文本 / 媒体 / 工具条」，而不是「我在找 `components/atomic/` 下的某个文件」。AI Agent 通过 MCP 的 `domain` 参数可直接按功能域检索。

## API 设计原则

### 数据流边界

| 机制                      | 用途         | 何时选择                                                               |
| ------------------------- | ------------ | ---------------------------------------------------------------------- |
| **Props**                 | 只读配置数据 | 父组件传入，子组件不修改。如 `messages`、`prompts`、`shortcuts`        |
| **v-model / defineModel** | 双向绑定     | 子组件确实需要回写时。如 `v-model:cite`、`v-model:selected-shortcut`   |
| **Events (emit)**         | 通知         | 「发生了某事」，父组件决定后续。如 `@stopStreaming`、`@selectShortcut` |
| **函数 prop (onXxx)**     | 可覆盖回调   | 需要「内置默认行为 + 业务可拦截」时。如 `onSendMessage`、`onDownload`  |
| **Slots**                 | 自定义渲染   | 需要完全替换某块 UI。如 AssistantMessage 默认 slot                     |
| **Composables**           | 数据逻辑抽取 | 可复用的纯数据流程。如 `useMessageGroup`、`useClipboard`               |

### 为什么用函数 prop 而非 emit

Vue 自定义事件没有 `preventDefault` 机制。当组件内置了默认行为（如下载文件），但业务需要替换或拦截时，函数 prop 是更合适的选择：

```typescript
// 函数 prop：业务可完全替换下载行为
onDownload?: (url: string) => Promise<void>

// 如果用 emit，组件内部无法知道业务是否「阻止了默认行为」
// emit('download', url)  ← 无法 preventDefault
```

### Composable 的职责边界

Composable **只负责数据逻辑**，不包含 UI 交互状态：

| 放在 Composable                  | 放在组件内本地 ref |
| -------------------------------- | ------------------ |
| 消息分组算法 (`useMessageGroup`) | hover 高亮状态     |
| 剪贴板操作 (`useClipboard`)      | 菜单展开/折叠      |
| 键盘导航逻辑 (`useMenuKeydown`)  | 拖拽坐标           |

**原因**：UI 状态与组件实例生命周期绑定，抽到 composable 会导致多实例共享问题，且增加不必要的响应式开销。

## 类型系统设计

### 声明合并扩展

消息类型和内容类型均通过 `declare global` 提供扩展点：

```typescript
// 库内定义
type MessageMap = AIBluekingMessageMap & {
  [MessageRole.User]: UserMessage;
  [MessageRole.Assistant]: AssistantMessage;
  // ...
};
type Message = MessageMap[MessageType];

// 业务扩展（零侵入）
declare global {
  interface AIBluekingMessageMap {
    approval: BaseMessage<'approval', { title: string; status: string }>;
  }
}
// 此后 Message 联合类型自动包含 approval
```

**设计决策**：选择 `declare global` 而非泛型参数，是因为消息类型需要在多个组件间传递，泛型会导致类型参数在组件树中逐层透传，增加使用复杂度。

### 判别联合

`Message` 是按 `role` 区分的判别联合类型，TypeScript 在 `switch(message.role)` 后可自动收窄类型：

```typescript
function process(msg: Message) {
  switch (msg.role) {
    case 'assistant':
      msg.toolCalls; // ✓ TypeScript 知道这是 AssistantMessage
      break;
    case 'tool':
      msg.toolCallId; // ✓ TypeScript 知道这是 ToolMessage
      break;
  }
}
```

## 渲染管线设计

### 为什么是「多级分发」而非「大 switch」

渲染管线分为三级：`MessageRender` → `ContentRender` → `MarkdownContent`（token 级），每级只关心自己层面的「类型」：

| 层级            | 分发依据                                     | 职责                         |
| --------------- | -------------------------------------------- | ---------------------------- |
| MessageRender   | `message.role`                               | 选择整条消息的渲染组件       |
| ContentRender   | `typeof content`（string / array）           | 选择内容块的渲染器           |
| MarkdownContent | MarkdownIt token 类型（fence / math / html） | 选择代码块/公式/图表的渲染器 |

**好处**：每个层级的 switch 分支数量可控（≤10），扩展时只需在对应层级加分支，不会影响其他层级。

### Activity 消息的二次分发

`ActivityMessage` 内部维护 `activityType → Component` 的静态映射：

```typescript
const activityComponentMap: Record<string, Component> = {
  [MessageContentType.FlowAgent]: FlowAgentContent,
  [MessageContentType.KnowledgeRag]: KnowledgeRagContent,
  [MessageContentType.ReferenceDocument]: ReferenceDocContent,
};
```

`<component :is="activityComponentMap[activityType]" />` 动态渲染。新增活动类型时需同步扩展此映射。

## 相关文档

- [架构总览](./architecture.md) — 组件层级、数据流、组合模式
- [用例食谱](./recipes.md) — 11 个常见场景的最小代码
- [MCP 服务](./ai/mcp.md) — AI IDE 如何通过 MCP 查询文档
- [最佳实践](./ai/best-practices.md) — 性能优化、安全规范、集成模式
