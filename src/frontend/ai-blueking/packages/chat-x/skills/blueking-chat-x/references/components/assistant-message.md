# AssistantMessage AI 助手消息

> 能力域：消息系统 ｜ 导入：`import { AssistantMessage } from '@blueking/chat-x'` ｜ since 0.0.20

渲染助手 Markdown 正文、ToolCallRender 工具调用列表，以及 property.artifacts 文件卡片； 默认插槽仅覆盖正文。源码位置：src/components/chat-message/assistant-message/assistant-message.vue。

**关联**：message-render（由 MessageRender 在 role 为 assistant 时创建）、tool-message（工具结果通过 toolCall.toolMessage 内联或独立 tool 消息关联展示）、toolcall-render（多条工具调用由 ToolcallRender 统一渲染）、file-artifact-panel（property.artifacts 文件产物点击后在侧栏预览）

---

# AssistantMessage AI 助手消息

## 源码事实

- **源码位置**：`src/components/chat-message/assistant-message/assistant-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染助手 Markdown 正文、工具调用列表与 `property.artifacts` 文件产物。

> **导出说明**：`AssistantMessage` **未**从 `@blueking/chat-x` 包入口导出（入口同名是 TS interface）。消费方请用 `MessageRender` / `MessageContainer`。下文 `AssistantMessageComp` 为文档站内部相对路径示例。

AI 助手消息展示组件：正文（Markdown）、工具调用（Tool Calls）、文件产物卡片。

## 渲染管线

```
AssistantMessage（根类名：ai-assistant-message）
├── ai-assistant-message-content（内容区，v-if content）
│   └── [default slot { content }] 或 ContentRender → MarkdownContent
├── ai-assistant-message-toolcalls（v-if toolCalls 非空，flex column，gap: 8px）
│   └── ToolCallRender × N（toolCalls，不受 slot 影响）
└── MessageArtifacts（v-if property.artifacts 非空）
      └── ArtifactFileCard × N（点击 → useArtifactPreview → 侧栏 FileArtifactPanel → ArtifactPreviewHost）
```

- **内容区**：`content` 经 `ContentRender`（`MessageContentType.Text`）由 `MarkdownContent` 渲染；default slot 仅收到 `{ content }`
- **工具调用区**：每个 `toolCall` 渲染一个 `ToolCallRender`，位于内容区下方；多条工具调用由 `.ai-assistant-message-toolcalls` 容器统一控制为 `8px` 间距，不受消息根节点 `12px` 间距影响
- **文件产物区**：读取 `property.artifacts`，用 `uid ?? String(id)` 作为 `messageUid` 传给 `MessageArtifacts`

## 基础用法

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Assistant,
    content: '你好！我是 AI 助手，有什么可以帮助你的吗？',
    status: MessageStatus.Complete,
  };
</script>
```

**渲染效果**

## Markdown 内容渲染

`content` 支持 Markdown 格式，组件内部通过 `MarkdownContent` 自动渲染标题、列表、代码块、链接等：

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Assistant,
    status: MessageStatus.Complete,
    content: `## Vue 3 核心特性

Vue 3 引入了多项重要更新：

1. **Composition API**：提供更灵活的逻辑组织方式
2. **性能优化**：虚拟 DOM 重写，编译时优化
3. **TypeScript 支持**：内置完整的类型定义

\\\`\\\`\\\`typescript
import { ref, computed } from 'vue';

const count = ref(0);
const doubled = computed(() => count.value * 2);
\\\`\\\`\\\`

> 更多详情请参考 [Vue 3 官方文档](https://vuejs.org)。`,
  };
</script>
```

**渲染效果**

## 消息状态

`status` 直接影响 **内容区**（`ContentRender`）。`ToolCallRender` 的状态**按工具维度推导**（见下方「工具调用状态推导」），不直接等于本组件的 `status`。

| `status`    | 内容区效果                          |
| ----------- | ----------------------------------- |
| `pending`   | 正常渲染（通常 content 为空）       |
| `streaming` | Markdown 自动补全未闭合语法         |
| `complete`  | 正常渲染完整 Markdown               |
| `error`     | 红色错误图标 + content 作为错误提示 |
| `stop`      | 正常渲染（内容停留在中止时的状态）  |

### Pending

### Streaming

流式输出中，`MarkdownContent` 自动补全未闭合的 Markdown 语法（代码块、列表等），适合逐字/逐段追加内容：

### Complete

### Error

渲染为错误信息样式（红色错误图标），`content` 作为错误提示文案展示：

### Stop

用户手动中止生成，内容停留在中止时的状态，与 `complete` 表现相同：

## 工具调用

当 AI 回复中包含工具调用时，传入 `toolCalls` 数组，每项自动渲染为 `ToolCallRender`，位于内容区下方。传给每个 `ToolCallRender` 的 `status` 按下方优先级从 `toolCall.toolMessage` 推导，而非直接同步本组件的 `status`。

### 单个工具调用

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Assistant,
    content: '让我帮你查询一下天气信息。',
    status: MessageStatus.Complete,
    toolCalls: [
      {
        id: 'call_1',
        type: 'function',
        function: {
          name: 'get_weather',
          arguments: '{"city": "北京", "unit": "celsius"}',
          description: '获取指定城市的天气信息',
        },
      },
    ],
  };
</script>
```

**渲染效果**

### 多个工具调用

AI 可在一次回复中发起多个工具调用，组件依次渲染：

```vue
<script setup lang="ts">
  const toolCalls = [
    {
      id: 'call_1',
      type: 'function',
      function: {
        name: 'search_documents',
        arguments: '{"query": "Vue 3 Composition API"}',
        description: '搜索知识库中的相关文档',
      },
    },
    {
      id: 'call_2',
      type: 'function',
      function: {
        name: 'get_code_snippet',
        arguments: '{"language": "typescript", "topic": "ref vs reactive"}',
        description: '获取代码示例片段',
      },
    },
  ];
</script>
```

**渲染效果**

### MCP 工具调用

`function.type` 为 `'mcp'`（或旧数据仅有 `mcpName`）时，`ToolCallRender` 头部显示为「调用 MCP {mcpName} / {name}」：

```vue
<script setup lang="ts">
  const toolCalls = [
    {
      id: 'call_mcp_1',
      type: 'function',
      function: {
        type: 'mcp', // 调用类型，缺省时有 mcpName 也会兼容判定为 MCP
        name: 'query_database',
        arguments: '{"sql": "SELECT * FROM users LIMIT 10"}',
        description: '执行数据库查询',
        mcpName: 'database-server', // MCP 服务名
      },
    },
  ];
</script>
```

**渲染效果**

### 携带执行结果

`toolMessage` 字段包含工具的执行结果；`ToolCallRender` 会展示返回内容（JSON 自动解析为键值对）和执行耗时：

```vue
<script setup lang="ts">
  const toolCalls = [
    {
      id: 'call_1',
      type: 'function',
      function: {
        name: 'get_weather',
        arguments: '{"city": "北京"}',
        description: '获取天气信息',
      },
      toolMessage: {
        role: 'tool',
        content: '{"weather":"晴","temperature":"22°C","humidity":"45%","wind":"东北风 3 级"}',
        status: 'complete',
        duration: 1200, // 毫秒
        toolCallId: 'call_1',
      },
    },
  ];
</script>
```

**渲染效果**（点击展开箭头可查看返回结果）

### 工具调用失败

`toolMessage.error` 不为空时，`ToolCallRender` 显示错误信息：

```vue
<script setup lang="ts">
  const toolCalls = [
    {
      id: 'call_1',
      type: 'function',
      function: {
        name: 'get_weather',
        arguments: '{"city": "北京"}',
        description: '获取天气信息',
      },
      toolMessage: {
        role: 'tool',
        content: '',
        status: 'error',
        error: 'API rate limit exceeded',
        duration: 350,
        toolCallId: 'call_1',
      },
    },
  ];
</script>
```

**渲染效果**

### 工具调用状态推导

传给每个 `ToolCallRender` 的 `status` 按以下优先级计算：

1. 无 `toolMessage` → `MessageStatus.Pending`（进行中）
2. `toolMessage.error` 为真 → `MessageStatus.Error`（失败）
3. 否则 → `toolMessage.status ??` 本组件 `status`

**进行中**（有 `toolCalls`、尚无 `toolMessage`；即便助手 `status` 已是 `complete`，工具调用仍显示「正在调用」）：

**成功**（`toolMessage.status = "complete"`）：

## 自定义内容渲染

默认插槽替换**内容区**的渲染（即 `ContentRender` 部分），工具调用仍在内容区外独立渲染，不受插槽影响：

```
[自定义 slot 内容]   ← 替换 ai-assistant-message-content 内默认渲染
[ToolCallRender]     ← 不受影响，仍正常渲染
[ToolCallRender]
```

```vue
<template>
  <MessageRender :message="message">
    <template #default="{ content }">
      <div style="padding: 12px; background: #f0f9ff; border-left: 3px solid #3a84ff; border-radius: 4px;">
        {{ content }}
      </div>
    </template>
  </MessageRender>
</template>
```

> **注意**：使用默认插槽后，内置 Markdown 渲染被替换，需自行处理格式化。slot 运行时仅保证 `{ content }`（见 [MessageRender](/components/message/message-render)）。

**渲染效果**

## 在 MessageContainer 中使用

`AssistantMessage` 通常不需要单独引入，`MessageContainer` 会对 `role: 'assistant'` 的消息自动渲染：

```vue
<template>
  <MessageContainer :messages="messages" />
</template>

<script setup lang="ts">
  import { MessageContainer } from '@blueking/chat-x';

  const messages = [
    {
      id: '1',
      messageId: '1',
      role: 'user',
      content: '北京今天天气怎么样？',
      status: 'complete',
    },
    {
      id: '2',
      messageId: '2',
      role: 'assistant',
      content: '让我帮你查询一下天气信息。',
      status: 'complete',
      toolCalls: [
        {
          id: 'call_1',
          type: 'function',
          function: {
            name: 'get_weather',
            arguments: '{"city": "北京"}',
            description: '获取天气',
          },
          toolMessage: {
            role: 'tool',
            content: '{"weather":"晴","temperature":"22°C"}',
            status: 'complete',
            duration: 800,
            toolCallId: 'call_1',
          },
        },
      ],
    },
    {
      id: '3',
      messageId: '3',
      role: 'assistant',
      content: '北京今天天气晴朗，气温 22°C，适合出行。',
      status: 'complete',
    },
  ];
</script>
```

## 文件产物

当 `property.artifacts` 非空时，在工具调用区下方渲染 `MessageArtifacts` 文件卡片列表。点击卡片会通过 `useArtifactPreview` 打开 `ChatContainer` 侧栏「文件产物」Tab（见 [FileArtifactPanel](/components/message/file-artifact-panel)）。

`AIFileInfo` 仅含元信息（`name` / `outputId` / `size` / `type`）；`download_url` / `preview_url` 由容器 `onArtifactClick` 异步获取。命中唯一文件依赖 `messageUid = uid ?? String(id)` + 卡片下标 + `outputId`。

侧栏预览由面板内 `ArtifactPreviewHost` 按**文件分类**分派（详见面板文档「预览机制」）：

| 分类 | 典型 type | 预览依赖 | 渲染 |
| ---- | --------- | -------- | ---- |
| 源码 / 配置 | `py` / `ts` / `json` / `yaml` / `Dockerfile` | `download_url` | highlight.js 高亮 |
| Markdown | `md` / `markdown` | `download_url` | MarkdownContent 富文本 |
| HTML | `html` / `htm` | `download_url` | `<iframe srcdoc>` 真实渲染 |
| 纯文本 | `txt` / `rst` | `download_url` | `<pre>` |
| 图片 | `png` / `jpg` / `svg` | `preview_url` | `<img>` |
| 其余（含未知类型） | `pdf` / `docx` / `xlsx` | `preview_url` | iframe（一般为后台转好的 PDF） |

`type` 为扩展名字符串（大小写不敏感），缺省时回退文件名推断；`md` 与 `markdown` 等价。预览重载、重试与取链约定见 [FileArtifactPanel 预览机制](/components/message/file-artifact-panel#预览机制)。

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';
  import type { AIFileInfo } from '@blueking/chat-x';

  const artifacts: AIFileInfo[] = [
    { name: '监控大盘周报.html', outputId: 'output-html', size: 10240, type: 'html' },
    { name: '系统配置说明.md', outputId: 'output-md', size: 8192, type: 'md' },
    { name: '周例会纪要.txt', outputId: 'output-txt', size: 4096, type: 'txt' },
    { name: '告警策略配置.json', outputId: 'output-json', size: 2048, type: 'json' },
    { name: '立项说明书.pdf', outputId: 'output-pdf', size: 204800, type: 'pdf' },
    { name: '巡检现场照片.jpg', outputId: 'output-jpg', size: 1048576, type: 'jpg' },
  ];

  const message = {
    id: 'a1',
    messageId: 'a1',
    uid: 'assistant-uid-1',
    role: MessageRole.Assistant,
    status: MessageStatus.Complete,
    content: '已为你生成一组评审材料，可点击卡片在侧栏预览或下载：',
    property: { artifacts },
  };
</script>
```

**渲染效果（文档站内部示例；无 Provider 时卡片不可点击预览）**

## API

### Props

组件 Props 来自 `Partial<AssistantMessage>`（所有字段均可选）：

| 属性名    | 类型                    | 说明                                                                                      |
| --------- | ----------------------- | ----------------------------------------------------------------------------------------- |
| content   | `string`                | AI 回复文本，支持 Markdown；空值时不渲染内容区                                            |
| status    | `MessageStatus`         | 影响 ContentRender；ToolCallRender 在无 toolMessage.status 时回退使用此值                 |
| toolCalls | `ToolCall[]`            | 工具调用列表，每项渲染一个 `ToolCallRender`                                               |
| id        | `number \| string`      | 消息 ID；无 `uid` 时回退为 `messageUid`                                                   |
| messageId | `number \| string`      | 消息唯一标识                                                                              |
| uid       | `string`                | 优先作为文件产物命中 / 「在对话中定位」的 `messageUid`                                    |
| name      | `string`                | 消息发送者名称（可选）                                                                    |
| role      | `MessageRole.Assistant` | 消息角色，固定为 `'assistant'`                                                            |
| property  | `{ artifacts?: AIFileInfo[]; extra?: ... }` | **本组件消费** `property.artifacts` 渲染文件卡片；`extra` 等由上层按需使用 |

### Slots

| 插槽名  | 参数                  | 说明                                                              |
| ------- | --------------------- | ----------------------------------------------------------------- |
| default | `{ content: string }` | 替换内容区渲染；toolCalls / MessageArtifacts 在内容区外独立渲染 |

### Events / Expose

无。

## 类型定义

```typescript
import type { AssistantMessage, ToolCall, FunctionCall, ToolMessage } from '@blueking/chat-x';

interface AssistantMessage extends BaseMessage<MessageRole.Assistant> {
  toolCalls?: ToolCall[];
}

// 工具调用
type ToolCall = {
  id: string;
  type: MessageContentType.Function; // 固定为 'function'
  function: FunctionCall;
  toolMessage?: Partial<ToolMessage>; // 工具执行结果（可选）
};

// 函数调用信息
type FunctionCall = {
  name: string; // 函数名
  arguments: string; // JSON 字符串格式的参数
  description?: string; // 函数描述
  mcpName?: string; // MCP 服务名（存在时标题显示 "调用 MCP"）
};

// 工具执行结果
interface ToolMessage extends BaseMessage<MessageRole.Tool, string> {
  toolCallId: string; // 对应的 ToolCall.id
  duration: number; // 执行耗时（ms）
  error?: string; // 错误信息（存在时 ToolCallRender 显示失败状态）
}
```

## 使用场景

- **文本消息展示**：聊天界面渲染 AI 回复的 Markdown 文本
- **工具调用过程展示**：展示 Function Call / MCP 调用的参数、状态和返回结果
- **流式输出**：`streaming` 状态下 Markdown 自动补全未闭合语法，配合流式响应实时更新
- **自动渲染**：通过 `MessageContainer` 对 `role: 'assistant'` 消息自动处理，无需手动引入
- **自定义内容渲染**：通过默认插槽替换内置 Markdown 渲染器，保留工具调用渲染

## 关联组件

- [MessageRender](/components/message/message-render) — assistant 角色由其实例化
- [ToolMessage](/components/message/tool-message) — 工具执行结果可通过 toolCall.toolMessage 内联
- [ToolcallRender](/components/agent/toolcall-render) — 工具调用列表渲染
- [FileArtifactPanel](/components/message/file-artifact-panel) — 文件产物侧栏列表与分类型预览 Host
