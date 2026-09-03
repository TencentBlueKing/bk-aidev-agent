# 快速上手

本文将帮助你快速开始使用 `@blueking/chat-x` 组件库，搭建一个 AI 对话界面。

## 安装

使用你喜欢的包管理器安装：

```bash
# pnpm（推荐）
pnpm add @blueking/chat-x

# npm
npm install @blueking/chat-x

# yarn
yarn add @blueking/chat-x
```

### 前置依赖

`@blueking/chat-x` 依赖以下库，请确保项目中已安装：

| 依赖       | 最低版本 | 说明                  |
| ---------- | -------- | --------------------- |
| `vue`      | 3.5+     | Vue 3 Composition API |
| `bkui-vue` | 2.x      | 蓝鲸 UI 基础组件库    |

## 引入方式

### 按需引入（推荐）

`@blueking/chat-x` 支持按需引入，只加载你需要的组件：

```typescript
import { ChatInput, MessageContainer } from '@blueking/chat-x';
```

### 引入样式

组件库全局样式会在导入时自动加载，无需额外配置。

## 核心概念

在开始使用之前，了解以下核心概念有助于你更好地组织代码。

### 消息角色（MessageRole）

每条消息都有一个 `role` 字段，标识消息的发送者：

| 角色        | 值            | 说明                           |
| ----------- | ------------- | ------------------------------ |
| `User`      | `'user'`      | 用户发送的消息                 |
| `Assistant` | `'assistant'` | AI 助手回复的消息              |
| `Tool`      | `'tool'`      | 工具调用结果                   |
| `Reasoning` | `'reasoning'` | AI 推理过程                    |
| `Info`      | `'info'`      | 信息提示消息                   |
| `Loading`   | `'loading'`   | 加载中占位消息                 |
| `System`    | `'system'`    | 系统消息                       |
| `Guide`     | `'guide'`     | 引导消息                       |
| `Activity`  | `'activity'`  | 活动消息（知识库、引用文档等） |

> 此外还有 `Hidden*`、`Template*` 等隐藏/模板系列角色，用于不渲染或模板化的消息，详见 [类型定义](./types/constants.md)。

### 消息状态（MessageStatus）

每条消息拥有 `status` 字段，表示当前的处理状态：

```typescript
import { MessageStatus } from '@blueking/chat-x';

MessageStatus.Pending; // 等待响应
MessageStatus.Streaming; // 流式输出中
MessageStatus.Complete; // 已完成
MessageStatus.Error; // 出错
MessageStatus.Stop; // 已停止
MessageStatus.Success; // 成功
MessageStatus.Disabled; // 已禁用
```

### 消息结构（Message）

一条典型的消息对象：

```typescript
import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';

const userMessage: Message = {
  id: 'msg-1',
  messageId: 1001,
  role: MessageRole.User,
  content: '你好，请介绍一下蓝鲸智云',
  status: MessageStatus.Complete,
};

const assistantMessage: Message = {
  id: 'msg-2',
  messageId: 1002,
  role: MessageRole.Assistant,
  content: '蓝鲸智云是腾讯开源的一站式运维平台...',
  status: MessageStatus.Complete,
};
```

## 基本使用

### 方式一：ChatContainer 一站式方案（推荐）

`ChatContainer` 封装了 `MessageContainer`、`ChatInput`、`ShortcutBtns`、`ShortcutRender`、`ExecutionSummary` 等子组件，内部自动完成消息分组、快捷指令渲染、执行摘要等逻辑，适合大多数场景。

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
      @update:model-value="handleUpdateInput"
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
    // 1. 添加用户消息
    messages.value.push({
      id: `user_${Date.now()}`,
      messageId: `user_${Date.now()}`,
      role: MessageRole.User,
      content,
      status: MessageStatus.Complete,
    });

    // 2. 添加 AI 占位消息，开始流式输出
    const aiMessage: Message = {
      id: `ai_${Date.now()}`,
      messageId: `ai_${Date.now()}`,
      role: MessageRole.Assistant,
      content: '',
      status: MessageStatus.Streaming,
    };
    messages.value.push(aiMessage);

    // 3. 模拟流式 API 响应（实际项目中替换为 SSE/WebSocket 调用）
    try {
      const reply = '这是一个 **Markdown** 回复。\n\n```javascript\nconsole.log("Hello!");\n```';
      for (const char of reply) {
        await new Promise(r => setTimeout(r, 20));
        aiMessage.content += char;
      }
      aiMessage.status = MessageStatus.Complete;
    } catch {
      aiMessage.status = MessageStatus.Error;
      aiMessage.content = '请求失败，请稍后重试。';
    }
  };

  const handleStopSending = async () => {
    const last = messages.value.at(-1);
    if (last) last.status = MessageStatus.Stop;
  };

  const handleAgentAction = async (tool: IToolBtn) => {
    if (tool.id === 'like') return ['回答准确', '信息全面', '表达清晰'];
    if (tool.id === 'unlike') return ['信息错误', '回答不相关', '解释不清楚'];
  };

  const handleUpdateInput = (value: string | TagSchema) => {
    // 输入框内容变化时触发
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

`ChatContainer` 自动处理：

- 消息分组（内部使用 `useMessageGroup`）
- 空对话时展示快捷指令按钮
- 快捷指令表单渲染
- 执行摘要侧边面板
- 多选与分享模式

### 方式二：自定义组合（进阶）

如需完全控制布局，可单独使用 `MessageContainer` + `ChatInput` + `useMessageGroup`。

> **注意**：`MessageContainer` 需要同时接收 `messages`（原始消息数组）和 `messageGroups`（分组后的消息），后者通过 `useMessageGroup` 生成。

```vue
<template>
  <div class="chat-page">
    <MessageContainer
      :messages="messages"
      :message-groups="messageGroups"
      :on-agent-action="handleAgentAction"
    />
    <ChatInput
      :menu-sources="menuSources"
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
    type IInputMenuItem,
    type Message,
    type TagSchema,
    type UserMessage,
  } from '@blueking/chat-x';

  const messages = deepRef<Message[]>([]);
  const userInput = shallowRef<string | TagSchema>('');

  // 自行组合时，会话产物不会被自动收集，需要自己维护完整的 menuSources
  const menuSources = shallowRef<IInputMenuItem[]>([
    { id: 'prompt-code', name: '写代码', type: 'prompt', content: '帮我写一段代码' },
    { id: 'prompt-error', name: '解释报错', type: 'prompt', content: '解释这段报错' },
  ]);

  // useMessageGroup 将 Message[] 转为 MessageGroup[]
  const { messageGroups } = useMessageGroup({
    messages: computed(() => messages.value),
    selectedUserMessages: deepRef(undefined),
  });

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

    // 模拟流式响应
    const reply = 'Hello from AI!';
    for (const char of reply) {
      await new Promise(r => setTimeout(r, 30));
      aiMessage.content += char;
    }
    aiMessage.status = MessageStatus.Complete;
  };

  const handleStopSending = async () => {
    const last = messages.value.at(-1);
    if (last) last.status = MessageStatus.Stop;
  };

  const handleAgentAction = async () => {};
</script>

<style scoped>
  .chat-page {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
</style>
```

## 组件一览

`@blueking/chat-x` 按功能域组织组件：

### 消息展示

| 组件               | 说明                     | 文档                                                            |
| ------------------ | ------------------------ | --------------------------------------------------------------- |
| `ChatContainer`    | 完整对话布局（推荐入口） | [ChatContainer](./components/setup/chat-container)       |
| `MessageContainer` | 消息列表容器             | [MessageContainer](./components/setup/message-container) |
| `MessageRender`    | 单条消息渲染             | [MessageRender](./components/message/message-render)       |

### 输入交互

| 组件             | 说明                                            | 文档                                                        |
| ---------------- | ----------------------------------------------- | ----------------------------------------------------------- |
| `ChatInput`      | 聊天输入框，支持 `/` Prompt、`@` 资源、文件上传 | [ChatInput](./components/input/chat-input)           |
| `AiSelection`    | AI 划词选择浮窗                                 | [AiSelection](./components/input/ai-selection)       |
| `ShortcutBtns`   | 快捷指令按钮组                                  | [ShortcutBtns](./components/input/shortcut-btns.md)        |
| `ShortcutRender` | 快捷指令表单渲染器                              | [ShortcutRender](./components/input/shortcut-render) |

### 内容渲染

| 组件              | 说明                     | 文档                                                       |
| ----------------- | ------------------------ | ---------------------------------------------------------- |
| `ContentRender`   | 内容渲染器（按类型分发） | [ContentRender](./components/rendering/content-render)  |
| `MarkdownContent` | Markdown 渲染            | [MarkdownContent](./components/rendering/markdown-content) |
| `CodeContent`     | 代码块高亮               | [CodeContent](./components/rendering/code-content)         |

### 文件与图片

| 组件                | 说明         | 文档                                                               |
| ------------------- | ------------ | ------------------------------------------------------------------ |
| `AiImage`           | 图片展示     | [AiImage](./components/medias/ai-image)                         |
| `ImagePreview`      | 图片全屏预览 | [ImagePreview](./components/medias/image-preview)            |
| `ImagePreviewGroup` | 多图预览管理 | [ImagePreviewGroup](./components/medias/image-preview-group.md) |

> 完整组件列表见 [组件文档](/components/)。

## 类型导入

组件库提供完整的 TypeScript 类型定义，可按需导入：

```typescript
import type {
  // 消息类型
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

  // 快捷指令
  Shortcut,
  ShortcutComponent,

  // 工具按钮
  IToolBtn,

  // 输入相关
  TagSchema,
  InputContent,
  UploadFile,

  // 图片
  ImageItem,
  ImagePreviewConfig,

  // 输入框菜单
  IInputMenuItem,
  MenuItemType,
  MenuTrigger,
} from '@blueking/chat-x';
```

## 常量导入

```typescript
import {
  // 枚举
  MessageRole,
  MessageStatus,
  MessageContentType,

  // 预置工具按钮
  CONST_MESSAGE_TOOLS, // AI 消息默认工具：复制、重新生成、分享
  CONST_USER_MESSAGE_TOOLS, // 用户消息默认工具：复制、编辑、删除
  CONST_UPDATE_TOOLS, // 更新工具：点赞、不满意、删除
} from '@blueking/chat-x';
```

## 完整示例

下面展示一个包含工具调用、快捷指令、流式输出的完整聊天界面，与项目 playground 中的 `chat-bot-new.vue` 对齐：

````vue
<template>
  <div class="chat-page">
    <ChatContainer
      v-model:cite="cite"
      v-model:selected-shortcut="selectedShortcut"
      :messages="messages"
      :model-value="userInput"
      :on-agent-action="handleAgentAction"
      :menu-sources="menuSources"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :shortcuts="shortcuts"
      @select-shortcut="handleSelectShortcut"
      @shortcut-close="handleShortcutClose"
      @shortcut-submit="handleShortcutSubmit"
      @update:model-value="handleUpdateInput"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref as deepRef, shallowRef } from 'vue';
  import {
    ChatContainer,
    MessageContentType,
    MessageRole,
    MessageStatus,
    type AssistantMessage,
    type IInputMenuItem,
    type IToolBtn,
    type Message,
    type Shortcut,
    type TagSchema,
    type ToolMessage,
    type UserMessage,
  } from '@blueking/chat-x';

  // ==================== 响应式状态 ====================

  const cite = shallowRef('');
  const userInput = shallowRef<string | TagSchema>('');
  const selectedShortcut = deepRef<null | Shortcut>(null);
  const messages = deepRef<Message[]>([]);

  // ==================== 配置数据 ====================

  // 输入框菜单统一数据源：按 type 分发到 "/"、"@"、"\" 与左下角 + 号
  // 会话产物（type: 'artifact'）由 ChatContainer 从 messages 自动收集，无需自行提供
  const menuSources = shallowRef<IInputMenuItem[]>([
    { id: 'search', name: '知识库搜索', type: 'tool' },
    { id: 'log-query', name: '日志查询', type: 'mcp' },
    { id: 'kb-ops', name: '运维知识库', type: 'knowledgebase' },
    { id: 'prompt-code', name: '写代码', type: 'prompt', content: '帮我写一段代码' },
  ]);

  // 空对话时展示的快捷指令
  const shortcuts = shallowRef<Shortcut[]>([
    { id: 'ask', name: '问问小鲸', description: '向 AI 助手提问' },
    {
      id: 'translate',
      name: '翻译',
      description: '翻译选中的文本',
      components: [
        {
          type: 'textarea',
          key: 'content',
          name: '翻译内容',
          placeholder: '请输入要翻译的内容',
          fillBack: true,
        },
      ],
    },
  ]);

  // ==================== 核心事件处理 ====================

  /** 发送消息 */
  const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
    // 1. 添加用户消息
    const userMsgId = `user_${Date.now()}`;
    messages.value.push({
      id: userMsgId,
      messageId: userMsgId,
      role: MessageRole.User,
      content,
      status: MessageStatus.Complete,
    });
    userInput.value = '';

    // 2. 调用后端 API（以下为模拟）
    await simulateAIResponse();
  };

  /** 停止生成 */
  const handleStopSending = async () => {
    const last = messages.value.at(-1);
    if (last) last.status = MessageStatus.Stop;
  };

  /** 工具栏操作（复制由内部自动处理） */
  const handleAgentAction = async (tool: IToolBtn) => {
    if (tool.id === 'like') return ['回答准确', '信息全面', '表达清晰'];
    if (tool.id === 'unlike') return ['信息错误', '回答不相关', '解释不清楚'];
  };

  // ==================== 快捷指令事件 ====================

  const handleSelectShortcut = (shortcut: Shortcut) => {
    selectedShortcut.value = { ...shortcut };
  };

  const handleShortcutClose = () => {
    selectedShortcut.value = null;
    userInput.value = '';
  };

  const handleShortcutSubmit = (formModel: Record<string, unknown>) => {
    console.log('快捷指令提交:', formModel);
    selectedShortcut.value = null;
    userInput.value = '';
  };

  const handleUpdateInput = (value: string | TagSchema, selectedResourceList?: IInputMenuItem[]) => {
    userInput.value = value;
  };

  // ==================== 模拟 AI 响应 ====================

  async function simulateAIResponse() {
    // 模拟：AI 先调用工具，再返回总结
    const assistantId = `ai_${Date.now()}`;
    const toolCallId = `tc_${Date.now()}`;

    // Assistant 消息 + 工具调用
    messages.value.push({
      id: assistantId,
      messageId: assistantId,
      role: MessageRole.Assistant,
      content: '正在为您查询相关信息...',
      status: MessageStatus.Complete,
      toolCalls: [
        {
          id: toolCallId,
          type: MessageContentType.Function,
          function: {
            name: '知识库搜索',
            arguments: JSON.stringify({ query: '蓝鲸智云介绍' }),
            description: '搜索相关文档',
          },
        },
      ],
    } as AssistantMessage);

    // 模拟工具返回
    await new Promise(r => setTimeout(r, 1000));
    messages.value.push({
      id: `tool_${Date.now()}`,
      messageId: `tool_${Date.now()}`,
      role: MessageRole.Tool,
      content: JSON.stringify({ results: ['蓝鲸智云是腾讯开源的一站式运维平台...'] }),
      status: MessageStatus.Complete,
      toolCallId,
      duration: 980,
    } as ToolMessage);

    // 流式输出最终回复
    const finalMessage: Message = {
      id: `ai2_${Date.now()}`,
      messageId: `ai2_${Date.now()}`,
      role: MessageRole.Assistant,
      content: '',
      status: MessageStatus.Streaming,
    };
    messages.value.push(finalMessage);

    const reply =
      '根据知识库检索结果：\n\n**蓝鲸智云**是腾讯开源的一站式运维平台，提供 CMDB、作业平台、监控、容器管理等能力。\n\n```bash\n# 快速部署\ncurl -sSL https://bk.tencent.com/install.sh | bash\n```';

    for (const char of reply) {
      await new Promise(r => setTimeout(r, 15));
      finalMessage.content += char;
    }
    finalMessage.status = MessageStatus.Complete;
  }
</script>

<style scoped>
  .chat-page {
    display: flex;
    width: 100%;
    height: 100vh;
    background: #fff;
  }
</style>
````

## 下一步

- 阅读 [架构总览](./architecture.md) 了解组件层级与数据流
- 浏览 [用例食谱](./recipes.md) 查看 11 个常见场景的最小代码
- 阅读 [ChatContainer](./components/setup/chat-container) 了解一站式方案的完整配置
- 阅读 [ChatInput](./components/input/chat-input) 了解输入框的 `/` Prompt、`@` 资源等高级功能
- 阅读 [MessageContainer](./components/setup/message-container) 了解消息容器的自定义用法
- 了解 [自定义消息类型](./ai/custom-message.md) 扩展图表、审批单等非标准消息
- 查看 [Composables](./composables/) 了解可复用的组合式函数
- 了解 [主题配置](./theme/theme.md) 自定义组件外观
