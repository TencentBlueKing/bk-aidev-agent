# @blueking/chat-x

蓝鲸智云 AI Chat 组件库 —— 基于 Vue 3 + TypeScript，遵循 [AG-UI（Agent-User Interaction Protocol）](https://docs.ag-ui.com/) 协议规范，为 AI Agent 和人类开发者共同设计的对话 UI 组件库。

提供符合 AG-UI 协议的标准化消息模型、流式消息渲染、Markdown 内容展示、代码高亮、LaTeX 公式、Mermaid 图表、快捷指令、划词选择等一站式 AI 对话能力，并内置 MCP Server 让 AI IDE 直接查询组件文档。

## 特性

- **AG-UI 协议支持** — 基于 [AG-UI](https://docs.ag-ui.com/) 开放协议规范构建消息类型系统，标准化 AI Agent 与用户界面之间的交互，支持流式事件、工具调用、多角色消息等协议能力
- **AI 优先设计** — 每个组件携带结构化元数据和 AI 专用摘要（aiSummary），内置 MCP Server 让 Cursor 等 AI IDE 通过标准协议直接查询文档
- **流式渲染** — 原生支持 AI 响应的实时流式输出，逐字渲染并自动补全未闭合的 Markdown 语法
- **20+ 消息角色** — 覆盖 User、Assistant、Tool、Reasoning、Activity、Info、Loading 等全部 AI 对话场景，支持 `declare global` 零侵入扩展自定义角色
- **多级内容管线** — `ContentRender → MarkdownContent → CodeContent / LatexContent / MermaidContent`，按 token 类型自动分发，支持 180+ 语言代码高亮
- **渐进式组合** — 最小组合 `ChatInput + MessageContainer`，完整方案 `ChatContainer` 一行搞定，原子 / 分子分层设计，按需引入
- **快捷指令与斜杠命令** — 内置 `/` 和 `@` 触发的命令系统，支持文本、数字、下拉、复选等表单组件
- **划词选择** — `AiSelection` 监听页面文本选中，弹出快捷操作浮窗
- **图片与文件** — 文件上传、图片展示、全屏预览、多图管理，内置下载与错误重试
- **类型安全** — 完整的 TypeScript 类型定义，泛型 + 全局类型扩展

## 安装

```bash
# pnpm（推荐）
pnpm add @blueking/chat-x

# npm
npm install @blueking/chat-x

# yarn
yarn add @blueking/chat-x
```

### 前置依赖

| 依赖       | 最低版本 | 说明                  |
| ---------- | -------- | --------------------- |
| `vue`      | 3.5+     | Vue 3 Composition API |
| `bkui-vue` | 2.x      | 蓝鲸 UI 基础组件库    |

## 快速开始

### 方式一：ChatContainer 一站式方案（推荐）

`ChatContainer` 封装了 `MessageContainer`、`ChatInput`、`ShortcutBtns`、`ShortcutRender`、`ExecutionSummary` 等子组件，内部自动完成消息分组、快捷指令渲染、执行摘要等逻辑。

````vue
<template>
  <div class="chat-page">
    <ChatContainer
      :messages="messages"
      :on-agent-action="handleAgentAction"
      :menu-sources="menuSources"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :shortcuts="shortcuts"
      @update:model-value="val => (userInput = val)"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref as deepRef, shallowRef } from 'vue';
  import {
    ChatContainer,
    MessageRole,
    MessageStatus,
    type IInputMenuItem,
    type IToolBtn,
    type Message,
    type Shortcut,
    type TagSchema,
    type UserMessage,
  } from '@blueking/chat-x';

  const messages = deepRef<Message[]>([]);
  const userInput = shallowRef<string | TagSchema>('');
  // 输入框菜单统一数据源：按 type 分发到 "/"、"@"、"\" 与左下角 + 号
  const menuSources = shallowRef<IInputMenuItem[]>([
    { id: 'prompt-code', name: '写代码', type: 'prompt', content: '帮我写一段代码' },
    { id: 'kb-ops', name: '运维知识库', type: 'knowledgebase' },
  ]);
  const shortcuts = shallowRef<Shortcut[]>([
    { id: 'ask', name: '问问小鲸', description: '向 AI 助手提问' },
    { id: 'code-review', name: '代码审查', description: '让 AI 审查你的代码' },
  ]);

  const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
    messages.value.push({
      id: `user_${Date.now()}`,
      messageId: `user_${Date.now()}`,
      role: MessageRole.User,
      content,
      status: MessageStatus.Complete,
    });
    userInput.value = '';

    const aiMessage: Message = {
      id: `ai_${Date.now()}`,
      messageId: `ai_${Date.now()}`,
      role: MessageRole.Assistant,
      content: '',
      status: MessageStatus.Streaming,
    };
    messages.value.push(aiMessage);

    // 替换为实际 SSE / WebSocket 调用
    const reply = '这是一个 **Markdown** 回复。\n\n```javascript\nconsole.log("Hello!");\n```';
    for (const char of reply) {
      await new Promise(r => setTimeout(r, 20));
      aiMessage.content += char;
    }
    aiMessage.status = MessageStatus.Complete;
  };

  const handleStopSending = async () => {
    const last = messages.value.at(-1);
    if (last) last.status = MessageStatus.Stop;
  };

  const handleAgentAction = async (tool: IToolBtn) => {
    if (tool.id === 'like') return ['回答准确', '信息全面', '表达清晰'];
    if (tool.id === 'unlike') return ['信息错误', '回答不相关', '解释不清楚'];
  };
</script>

<style scoped>
  .chat-page {
    display: flex;
    height: 100vh;
    background: #fff;
  }
</style>
````

### 方式二：自定义组合（进阶）

如需完全控制布局，可单独使用 `MessageContainer` + `ChatInput` + `useMessageGroup`。

```vue
<template>
  <div class="chat-page">
    <MessageContainer
      :messages="messages"
      :message-groups="messageGroups"
      :on-agent-action="handleAgentAction"
    />
    <ChatInput
      :model-value="userInput"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      @update:model-value="val => (userInput = val)"
    />
  </div>
</template>

<script setup lang="ts">
  import { computed, ref as deepRef, shallowRef } from 'vue';
  import {
    ChatInput,
    MessageContainer,
    MessageRole,
    MessageStatus,
    useMessageGroup,
    type Message,
    type TagSchema,
    type UserMessage,
  } from '@blueking/chat-x';

  const messages = deepRef<Message[]>([]);
  const userInput = shallowRef<string | TagSchema>('');

  const { messageGroups } = useMessageGroup({
    messages: computed(() => messages.value),
    selectedUserMessages: deepRef(undefined),
  });

  const handleSendMessage = async (content: UserMessage['content']) => {
    messages.value.push({
      id: `user_${Date.now()}`,
      messageId: `user_${Date.now()}`,
      role: MessageRole.User,
      content,
      status: MessageStatus.Complete,
    });
    userInput.value = '';
    // ...发送 AI 请求并流式追加响应
  };

  const handleStopSending = async () => {
    const last = messages.value.at(-1);
    if (last) last.status = MessageStatus.Stop;
  };

  const handleAgentAction = async () => {};
</script>
```

## AG-UI 协议

`@blueking/chat-x` 的消息类型系统基于 [AG-UI（Agent@blueking/chat-x@0.0.10-User Interaction Protocol）](https://docs.ag-ui.com/) 协议规范构建。AG-UI 是一个开放的、轻量级的、基于事件的协议，标准化了 AI Agent 后端与用户前端之间的实时双向通信。

### 协议栈定位

AG-UI 与 MCP、A2A 构成互补的三层 Agent 协议栈：

```
┌─────────────────────────────────────────┐
│            用户界面 (Frontend)            │
└──────────────────┬──────────────────────┘
                   │ AG-UI — Agent ↔ 用户交互
┌──────────────────┴──────────────────────┐
│            AI Agent (Backend)            │
├──────────────────┬──────────────────────┤
│ MCP — Agent ↔ 工具/数据  │ A2A — Agent ↔ Agent │
└──────────────────┴──────────────────────┘
```

- **AG-UI**：连接 Agent 与用户界面，处理消息流、状态同步、工具调用展示
- **MCP**：连接 Agent 与工具/数据源
- **A2A**：协调分布式 Agent 间的通信

### chat-x 中的 AG-UI 实现

组件库在 `src/ag-ui/types/` 中实现了 AG-UI 协议的核心类型定义：

| 模块                         | 对应协议能力 | 说明                                                                                       |
| ---------------------------- | ------------ | ------------------------------------------------------------------------------------------ |
| `MessageRole`                | 消息角色标识 | 22 种角色枚举，覆盖 User、Assistant、Tool、Reasoning、Activity 等全部 Agent 对话场景       |
| `MessageStatus`              | 运行生命周期 | Pending → Streaming → Complete / Error / Stop，对应 AG-UI 的 Run Lifecycle 事件            |
| `MessageContentType`         | 内容类型分发 | Text、Binary、Function、FlowAgent、KnowledgeRag 等，驱动多级内容渲染管线                   |
| `ToolCall` / `FunctionCall`  | 工具调用     | 标准化的工具调用结构，包含函数名、参数、描述，`ToolMessage` 通过 `toolCallId` 关联执行结果 |
| `BaseMessage<Role, Content>` | 消息基础模型 | 泛型消息基类，按 `role` 判别联合类型，支持 `declare global` 零侵入扩展                     |
| `ContentMap`                 | 内容类型映射 | 按 `MessageContentType` 映射到具体内容结构，同样支持全局类型扩展                           |

所有组件（`MessageRender`、`ContentRender`、`ChatInput` 等）均基于这套 AG-UI 类型系统进行消息分发和渲染，确保前端 UI 与 Agent 后端的交互遵循统一的协议规范。

## 核心概念

### 消息角色（MessageRole）

| 类别     | 角色                                 | 说明                                                 |
| -------- | ------------------------------------ | ---------------------------------------------------- |
| 核心对话 | `User`、`Assistant`                  | 用户消息和 AI 回复                                   |
| AI 能力  | `Tool`、`Reasoning`、`Activity`      | 工具调用结果、推理过程、活动（知识库/流程/引用文档） |
| 系统     | `System`、`Info`、`Guide`、`Loading` | 系统消息、信息提示、引导、加载                       |
| 控制     | `Pause`、`Placeholder`、`Hidden*`    | 暂停、占位、隐藏系列                                 |
| 模板     | `Template*`                          | 预设对话模板系列                                     |

通过 `declare global { interface AIBluekingMessageMap }` 注册自定义消息角色，类型自动合并到 `Message` 联合中。

### 消息状态（MessageStatus）

```
Pending → Streaming → Complete / Error / Stop
```

| 状态        | 说明       |
| ----------- | ---------- |
| `Pending`   | 等待响应   |
| `Streaming` | 流式输出中 |
| `Complete`  | 已完成     |
| `Error`     | 出错       |
| `Stop`      | 已停止     |
| `Success`   | 成功       |
| `Disabled`  | 已禁用     |

### 消息结构（Message）

```typescript
import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';

const message: Message = {
  id: 'msg-1',
  messageId: 1001,
  role: MessageRole.User,
  content: '你好，请介绍一下蓝鲸智云',
  status: MessageStatus.Complete,
};
```

## 组件一览

### 消息展示

| 组件               | 说明                                                                 |
| ------------------ | -------------------------------------------------------------------- |
| `ChatContainer`    | 完整对话布局（推荐入口），封装消息分组、快捷指令、执行摘要、多选分享 |
| `MessageContainer` | 消息列表容器                                                         |
| `MessageRender`    | 单条消息渲染器，按 role 分发到具体消息组件                           |

### 输入交互

| 组件             | 说明                                            |
| ---------------- | ----------------------------------------------- |
| `ChatInput`      | 聊天输入框，支持 `/` Prompt、`@` 资源、文件上传 |
| `AiSelection`    | AI 划词选择浮窗                                 |
| `ShortcutBtns`   | 快捷指令按钮组（空对话引导）                    |
| `ShortcutRender` | 快捷指令表单渲染器                              |

### 内容渲染

| 组件              | 说明                                      |
| ----------------- | ----------------------------------------- |
| `ContentRender`   | 内容渲染器（按内容类型分发）              |
| `MarkdownContent` | Markdown 渲染（内含代码、公式、图表分发） |
| `CodeContent`     | 代码块高亮（180+ 语言）                   |
| `LatexContent`    | LaTeX 公式渲染（KaTeX）                   |
| `MermaidContent`  | Mermaid 图表渲染                          |

### 文件与图片

| 组件                | 说明                             |
| ------------------- | -------------------------------- |
| `AiImage`           | 图片展示（加载状态、错误重试）   |
| `ImagePreview`      | 图片全屏预览（缩放、旋转、下载） |
| `ImagePreviewGroup` | 多图预览管理（provide/inject）   |

### 工具与反馈

| 组件                  | 说明                                   |
| --------------------- | -------------------------------------- |
| `MessageTools`        | 消息工具栏（复制、引用、点赞、分享等） |
| `MessageUserFeedback` | 用户反馈组件                           |
| `ToolCallRender`      | 工具调用卡片渲染                       |
| `ExecutionSummary`    | 执行摘要侧栏                           |

### 辅助组件

| 组件               | 说明         |
| ------------------ | ------------ |
| `ScrollBtn`        | 返回底部按钮 |
| `ToolBtn`          | 工具按钮     |
| `ShortcutBtn`      | 快捷指令按钮 |
| `AnimationText`    | 流式动画文本 |
| `HighlightKeyword` | 关键词高亮   |
| `SelectionFooter`  | 多选操作栏   |
| `MessageLoading`   | 消息加载动画 |

## Composables 组合式函数

| Composable               | 说明                                                                  |
| ------------------------ | --------------------------------------------------------------------- |
| `useMessageGroup`        | 将 `Message[]` 转为 `MessageGroup[]`（分组、Tool 注入、Loading 追加） |
| `useContainerScroll`     | 消息容器自动滚动管理                                                  |
| `useClipboard`           | 剪贴板操作                                                            |
| `useAnimationText`       | 文本流式动画                                                          |
| `useCommandSelection`    | 斜杠命令选择                                                          |
| `useMenuKeydown`         | 菜单键盘导航                                                          |
| `useObserverVisibleList` | IntersectionObserver 可见列表监听                                     |
| `useParentScrolling`     | 父容器滚动检测                                                        |
| `useGlobalConfig`        | 全局配置注入                                                          |

## 类型导入

```typescript
import type {
  Message,
  UserMessage,
  AssistantMessage,
  ReasoningMessage,
  ToolMessage,
  InfoMessage,
  LoadingMessage,
  ActivityMessage,
  GuideMessage,
  SystemMessage,
  Shortcut,
  ShortcutComponent,
  IToolBtn,
  TagSchema,
  InputContent,
  UploadFile,
  ImageItem,
  IInputMenuItem,
  MenuItemType,
  MenuTrigger,
} from '@blueking/chat-x';
```

## 常量导入

```typescript
import {
  MessageRole,
  MessageStatus,
  MessageContentType,
  CONST_MESSAGE_TOOLS, // AI 消息默认工具：复制、重新生成、分享
  CONST_USER_MESSAGE_TOOLS, // 用户消息默认工具：复制、编辑、删除
  CONST_UPDATE_TOOLS, // 更新工具：点赞、不满意、删除
} from '@blueking/chat-x';
```

## 架构概览

```
ChatContainer                          ← 一站式对话布局
├── MessageContainer                   ← 消息列表容器
│   ├── MessageRender × N             ← 按 role 分发渲染
│   │   ├── UserMessage               ← 用户消息
│   │   ├── AssistantMessage           ← AI 回复
│   │   │   ├── ContentRender          ← 内容分发
│   │   │   │   └── MarkdownContent    ← Markdown 解析
│   │   │   │       ├── CodeContent    ← 代码高亮
│   │   │   │       ├── LatexContent   ← LaTeX 公式
│   │   │   │       └── MermaidContent ← 图表
│   │   │   └── ToolcallRender × N    ← 工具调用卡片
│   │   ├── ReasoningMessage           ← 推理过程
│   │   ├── ActivityMessage            ← 活动消息
│   │   └── LoadingMessage             ← 加载动画
│   ├── MessageTools                   ← 消息工具栏
│   └── ScrollBtn                      ← 返回底部
├── ShortcutBtns                       ← 快捷指令引导
├── ShortcutRender                     ← 快捷指令表单
├── ChatInput                          ← 输入区
│   ├── InputMenuPanel                 ← 统一菜单（/ @ \ 与 + 号共用）
│   ├── AiSlashInput                   ← 富文本编辑区（触发符识别 + 资源标签）
│   └── InputAttachment                ← 底部工具栏（+ 号 / 快捷指令 / 模型 / 发送）
└── SelectionFooter                    ← 多选操作栏
```

**数据流**：`ChatInput → onSendMessage → 业务层 API → AG-UI Message[] 写入 → useMessageGroup 分组 → MessageContainer 按 role 分发渲染`

## 扩展

### 自定义消息类型

通过 TypeScript 声明合并扩展消息角色，在 `MessageRender` 的默认 slot 中渲染自定义组件：

```typescript
declare global {
  interface AIBluekingMessageMap {
    chart: BaseMessage<'chart', { type: string; data: unknown[] }>;
  }
}
```

### 工具栏定制

通过 `onAgentAction` / `onUserAction` 回调处理工具按钮点击，`messageToolsStatus` 控制按钮的禁用/隐藏，`like`/`unlike` 返回反馈原因数组。

### 主题定制

CSS 变量 + `useGlobalConfig` 统一调整全局展示配置。

## MCP Server

`@blueking/chat-x` 内置 MCP Server，供 AI IDE（如 Cursor）通过标准协议查询组件文档。

### 配置

在 Cursor 的 `.cursor/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "chat-x": {
      "command": "npx",
      "args": ["@blueking/chat-x"]
    }
  }
}
```

### 可用工具

| 工具                | 说明                                        |
| ------------------- | ------------------------------------------- |
| `list_components`   | 列出所有索引条目，支持按 kind / domain 过滤 |
| `get_component_doc` | 获取指定组件文档，含 AI 摘要                |
| `search_docs`       | 关键词搜索文档                              |

## 依赖说明

| 依赖         | 版本     | 说明                  |
| ------------ | -------- | --------------------- |
| vue          | ^3.5.24  | Vue 3 核心库          |
| bkui-vue     | 2.x      | 蓝鲸 UI 组件库        |
| highlight.js | ^11.11.1 | 代码高亮（180+ 语言） |
| katex        | ^0.16.27 | LaTeX 公式渲染        |
| mermaid      | ^11.12.2 | 图表渲染              |
| dompurify    | ^3.3.1   | HTML 安全过滤         |
