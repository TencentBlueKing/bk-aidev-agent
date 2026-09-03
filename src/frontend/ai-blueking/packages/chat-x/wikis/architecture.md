---
name: 架构总览
slug: architecture
category: guide
description: >
  @blueking/chat-x 的整体架构、渲染管线、数据模型、组件组合模式和扩展机制。
aiSummary: >
  chat-x 采用「消息驱动 + 角色分发」架构。业务层维护 Message[] 数组，
  useMessageGroup 将其按角色分组为 MessageGroup[]，MessageRender 按 role
  switch 到具体组件（AssistantMessage、UserMessage 等），AssistantMessage 内
  ContentRender 再按内容类型分发到 MarkdownContent、CodeContent、MermaidContent
  等内容渲染器。最小可用组合为 ChatInput + MessageContainer + useMessageGroup，
  ChatContainer 封装了完整对话界面。扩展自定义消息通过 declare global 类型合并
  + MessageRender 默认 slot 实现。
relatedComponents: []
sinceVersion: '1.0.0'
---

# 架构总览

本文描述 `@blueking/chat-x` 的整体架构，帮助开发者和 AI Agent 快速建立全局认知。

## 设计目标

1. **AI Agent 可理解**：组件 API、类型系统、文档元数据均按「AI 可消费」标准设计，AI 通过 MCP 或直接读文档即可选择和组装组件
2. **渐进式组合**：从最小的 `ChatInput + MessageContainer` 到完整的 `ChatContainer`，按需引入
3. **类型安全扩展**：通过 TypeScript 声明合并（`declare global`）扩展消息类型和内容类型，无需修改库代码

## 组件层级

```
ChatContainer                          ← 一站式对话布局
├── ResizeLayout                       ← 可拖拽分栏（bkui-vue）
│   ├── #aside
│   │   ├── Tab + TabPanel             ← 侧栏标签页
│   │   ├── ExecutionSummary           ← 执行摘要（工具调用/流程消息汇总）
│   │   └── 自定义 Tab 组件            ← 业务注入的面板（如节点详情）
│   └── #main
│       ├── MessageContainer           ← 消息列表容器
│       │   ├── MessageRender × N      ← 按组渲染，内部按 role 分发
│       │   │   ├── UserMessage        ← 用户消息（编辑/删除/快捷指令回显）
│       │   │   ├── AssistantMessage   ← AI 回复（正文 + 工具调用列表）
│       │   │   │   ├── ContentRender  ← 正文渲染入口
│       │   │   │   └── ToolcallRender × N  ← 逐个工具调用卡片
│       │   │   ├── ReasoningMessage   ← 推理过程（折叠/展开）
│       │   │   ├── ActivityMessage    ← 活动消息（按 activityType 分发）
│       │   │   │   ├── FlowAgentContent      ← BkFlow 流程
│       │   │   │   ├── KnowledgeRagContent   ← 知识库检索
│       │   │   │   └── ReferenceDocContent   ← 引用文档列表
│       │   │   ├── InfoMessage        ← 系统提示
│       │   │   ├── ToolMessage        ← 工具结果（通常不独立渲染）
│       │   │   └── LoadingMessage     ← 等待动画
│       │   ├── MessageTools           ← 消息组底部工具栏
│       │   └── ScrollBtn              ← 返回底部按钮
│       ├── ShortcutBtns               ← 空对话时的快捷指令按钮
│       ├── ShortcutRender             ← 快捷指令表单
│       ├── ChatInput                  ← 输入区
│       │   ├── InputMenuPanel         ← 统一菜单（/ @ \ 与 + 号共用）
│       │   ├── AiSlashInput           ← 富文本编辑区（触发符识别 + 标签插入）
│       │   │   └── MentionTag × N     ← 已选资源标签
│       │   └── InputAttachment        ← 底部工具栏（+ 号 / 快捷指令 / 模型 / 发送）
│       └── SelectionFooter            ← 多选操作栏
└── AiSelection                        ← 划词选择浮窗（独立于 ChatContainer）
```

## 数据流

```
┌──────────┐   onSendMessage    ┌──────────┐
│ ChatInput │ ─────────────────→ │  业务层  │
└──────────┘                    └────┬─────┘
                                     │ SSE / WebSocket / API
                                     ▼
                              Message[] 写入
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ useMessageGroup  │
                            │                 │
                            │ · User 消息切段  │
                            │ · 非 User 累积  │
                            │ · Tool 注入     │
                            │ · Loading 追加  │
                            └────────┬────────┘
                                     │ MessageGroup[]
                                     ▼
                            ┌─────────────────┐
                            │MessageContainer  │
                            │  v-for groups    │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  MessageRender   │
                            │ switch(role) →   │
                            │ h(XxxMessage)    │
                            └────────┬────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
              AssistantMessage  UserMessage   ActivityMessage ...
                      │
                      ▼
              ┌───────────────┐
              │ ContentRender │  ← string → MarkdownContent
              │               │  ← array  → ReferenceContent
              └───────┬───────┘
                      │ MarkdownContent 内部
                      ▼
          ┌───────────────────────┐
          │ MarkdownIt 解析 token │
          │   ↓ groupTokens      │
          │   ├─ mermaid fence   │→ MermaidContent
          │   ├─ math token      │→ LatexContent
          │   ├─ code fence      │→ CodeContent
          │   └─ 其它 HTML       │→ VNodeRenderer (DOMPurify)
          └───────────────────────┘
```

## 核心数据模型

### Message 类型系统

所有消息继承 `BaseMessage<Role, Content>`，按 `role` 区分具体类型：

```typescript
// 公共字段
interface BaseMessage<T extends MessageType, C = string> {
  id: number | string;
  messageId: number | string;
  role: T;                    // 判别字段
  content: C;                 // 内容，泛型
  status: MessageStatus;
  property?: { extra?: ... }; // 扩展属性（引用、快捷指令上下文等）
}

// 具体消息示例
interface AssistantMessage extends BaseMessage<'assistant'> {
  toolCalls?: ToolCall[];     // 工具调用列表
}
interface ToolMessage extends BaseMessage<'tool', string> {
  toolCallId: string;         // 关联的 toolCall.id
  duration: number;           // 耗时（ms）
  error?: boolean | string;
}
interface ActivityMessage extends BaseMessage<'activity', ...> {
  activityType: string;       // FlowAgent / KnowledgeRag / ReferenceDocument
}

// 总联合类型
type Message = MessageMap[MessageType];
```

### MessageGroup 分组规则

`useMessageGroup` 将 `Message[]` 转为 `MessageGroup[]`，规则如下：

| 条件           | 行为                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------- |
| 遇到 User 消息 | 将之前累积的非 User 消息打包为一个 Assistant 组，User 消息单独成组                           |
| 遇到 Tool 消息 | **不进入分组列表**，而是找到对应的 AssistantMessage.toolCalls，注入到 `toolCall.toolMessage` |
| 遇到其他角色   | 累积到当前 Assistant 组缓冲区                                                                |
| 末尾是 User    | 自动追加一个 Loading 组（显示等待动画）                                                      |

### ToolCall 关联

```
AssistantMessage
  └── toolCalls: ToolCall[]
        ├── { id: 'tc_1', function: { name: '搜索' }, toolMessage?: ToolMessage }
        └── { id: 'tc_2', function: { name: '计算' }, toolMessage?: ToolMessage }

ToolMessage (id: 'tool_1', toolCallId: 'tc_1')
  → useMessageGroup 将其注入到 toolCalls[0].toolMessage
```

## 渲染管线

### MessageRender：角色分发

`MessageRender` 内部通过 `switch(message.role)` 决定渲染哪个组件：

| role        | 渲染组件         | 特殊行为                                                                                |
| ----------- | ---------------- | --------------------------------------------------------------------------------------- |
| `user`      | UserMessage      | 支持编辑、删除、快捷指令回显                                                            |
| `assistant` | AssistantMessage | **唯一支持默认 slot 覆盖**（自定义渲染入口）；内部遍历 toolCalls 渲染 ToolcallRender    |
| `reasoning` | ReasoningMessage | 折叠/展开                                                                               |
| `activity`  | ActivityMessage  | 按 activityType 二次分发到 FlowAgentContent / KnowledgeRagContent / ReferenceDocContent |
| `info`      | InfoMessage      | 系统提示                                                                                |
| `tool`      | ToolMessage      | 通常被注入到 AssistantMessage 内，不独立渲染                                            |
| `loading`   | LoadingMessage   | CSS 骨架屏动画                                                                          |
| 其他        | `null`           | 不渲染                                                                                  |

### ContentRender：内容类型分发

| content 类型                     | 渲染组件         |
| -------------------------------- | ---------------- |
| `string`（或 `type === 'text'`） | MarkdownContent  |
| `Array`（引用文档列表）          | ReferenceContent |

### MarkdownContent：token 级渲染

MarkdownIt 解析后按 token 组分发：

| token 特征                     | 渲染组件                           |
| ------------------------------ | ---------------------------------- |
| `fence` + `info === 'mermaid'` | MermaidContent                     |
| `math_inline` / `math_block`   | LatexContent                       |
| `fence` / `code_block`         | CodeContent                        |
| 其他 HTML                      | VNodeRenderer（经 DOMPurify 过滤） |

## 组件组合模式

### 最小组合

```
ChatInput + MessageContainer + useMessageGroup
```

业务自行维护 `messages`，通过 `useMessageGroup` 生成 `messageGroups` 传给 `MessageContainer`。适合嵌入现有页面或需要完全自定义布局的场景。

### 完整组合

```
ChatContainer
```

内部封装了消息分组、快捷指令、执行摘要、多选分享等全部逻辑。接收 `messages` 即可，推荐大多数场景使用。

详见 [快速上手](./getting-started.md) 中的代码示例。

## 扩展机制

### 自定义消息类型

通过 TypeScript 声明合并扩展 `AIBluekingMessageMap`，然后在 `MessageRender` 的默认 slot 中按 `contentType` 渲染自定义组件。

```typescript
declare global {
  interface AIBluekingMessageMap {
    chart: BaseMessage<'chart', { type: string; data: unknown[] }>;
  }
}
```

详见 [自定义消息类型](./ai/custom-message.md)。

### 自定义内容类型

通过 `AIBluekingContentMap` 声明合并扩展内容块类型，与 `ContentRender` 的 slot 机制配合使用。

### 工具栏定制

通过 `onAgentAction` / `onUserAction` 回调处理工具按钮点击；`messageToolsStatus` 控制按钮的禁用/隐藏；`like`/`unlike` 返回反馈原因数组。

### 主题

CSS 变量 + `useGlobalConfig` 统一调整全局展示配置。

## 相关文档

- [设计理念](./design-philosophy.md) — 能力域架构、API 设计原则、AI 优先策略
- [用例食谱](./recipes.md) — 11 个常见场景的最小代码
- [自定义消息类型](./ai/custom-message.md) — 类型扩展完整流程
- [MCP 服务](./ai/mcp.md) — AI IDE 如何通过 MCP 查询文档
