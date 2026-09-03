# ToolMessage 工具消息

> 能力域：消息系统 ｜ 导入：`import { ToolMessage } from '@blueking/chat-x'` ｜ since 0.0.20

渲染工具返回内容；DescPanel 解析 JSON 为 key-value，嵌套值 JSON.stringify 后经 HighlightKeyword 展示。 源码位置：src/components/chat-message/tool-message/tool-message.vue。

**关联**：assistant-message（结果常作为 assistant 消息中 toolCall.toolMessage 内联展示）、message-render（独立 tool 角色消息由 MessageRender 渲染为 ToolMessage）、desc-panel（内部使用 DescPanel 展示「返回内容」）

---

# ToolMessage 工具消息

## 源码事实

- **源码位置**：`src/components/chat-message/tool-message/tool-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染工具返回内容，JSON 场景交给 DescPanel + HighlightKeyword 展示。

> **导出说明**：`ToolMessage` **未**从包入口导出（入口同名是 TS interface）。消费方经 `MessageRender` / `ToolcallRender` 使用。下文 `ToolMessageComp` 为文档站内部示例。

工具执行结果展示组件。内部通过 `DescPanel` 渲染，标题固定为「返回内容」，可解析 JSON 为 key-value 列表。

> **通常不需要直接使用**。`ToolcallRender` 在 `toolCall.toolMessage` 有值时内联渲染；`role: 'tool'` 也可由 `MessageRender` 渲染。

## 渲染架构

```
ToolMessage
└── DescPanel（desc = content || (typeof error === 'string' ? error : undefined)，title="返回内容"）
      ├── JSON.parse 成功且结果为 object/array（排除 null）
      │     └── key-value 列表
      │           · key / value 均经 HighlightKeyword 展示
      │           · 嵌套 object/array：JSON.stringify 后展示（无 overflow-tips）
      └── 其他（parse 失败 / 标量）
            └── HighlightKeyword 纯文本
```

## 基础用法

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: 't1',
    messageId: 't1',
    role: MessageRole.Tool,
    status: MessageStatus.Complete,
    toolCallId: 'call_1',
    duration: 850,
    content: JSON.stringify({
      city: '北京',
      temperature: 22,
      weather: '晴',
      humidity: '45%',
      wind: '东北风 3 级',
    }),
  };
</script>
```

**JSON 对象内容（key-value 列表）**

**纯文本内容**

## 错误状态

`content` 为空时展示 `error`，由 `content || (typeof error === 'string' ? error : undefined)` 决定。仅当 `error` 为字符串类型时才会展示，非字符串类型的 `error`（如对象）会被忽略：

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: 't3',
    messageId: 't3',
    role: MessageRole.Tool,
    status: MessageStatus.Error,
    toolCallId: 'call_3',
    duration: 5000,
    content: '',
    error: 'Connection timeout: database server is unreachable (timeout: 5000ms)',
  };
</script>
```

## DescPanel 内容渲染规则

`DescPanel` 内部对 `desc`（即 `content || (typeof error === 'string' ? error : undefined)`）进行 `JSON.parse`，然后根据解析结果类型决定渲染方式：

| `desc` 内容                 | `JSON.parse` 结果               | 渲染方式                            |
| --------------------------- | ------------------------------- | ----------------------------------- |
| 合法 JSON 对象 `{}`         | `object`（非 null）             | **key-value 列表**，键为字段名      |
| 合法 JSON 数组 `[]`         | `array`（也是 `object`）        | **index-keyed 列表**，键为 0、1、2… |
| 合法 JSON 基本类型          | `number` / `string` / `boolean` | 纯文本                              |
| `"null"` 字符串             | `null`（`typeof 'object'`）     | 空内容区（v-for 遍历 null 无输出）  |
| 解析失败（非法 JSON）       | 捕获异常，返回原字符串          | 纯文本                              |
| `content` 和 `error` 均为空 | `''` → 解析失败                 | 空内容区                            |

> **注意**：JSON 数组 `typeof [] === 'object'`，会以 `0:`、`1:`、`2:` 为键渲染为列表，而非整段纯文本。

**嵌套对象 / 数组值**：`DescPanel` 用 `JSON.stringify(value)` 转成字符串后交给 `HighlightKeyword`，**不再**使用 overflow-tips。

```typescript
// key-value 列表
const jsonObject = '{"city":"北京","temperature":22}';

// index-keyed 列表（0: item1, 1: item2）
const jsonArray = '["item1","item2","item3"]';

// 嵌套值 stringify 展示
const nested = '{"result":"success","data":{"city":"北京","meta":{"humidity":45}}}';

// 标量 / 非法 JSON → 纯文本
const jsonNumber = '42';
const plainText = '查询成功，共返回 10 条记录。';
```

**嵌套 JSON 渲染效果**

## 与 ToolcallRender 的关系

`ToolcallRender` 在详情面板展开时，若 `toolCall.toolMessage` 有值，会在底部内联渲染 `ToolMessage`：

```typescript
// toolcall-render.vue 内部逻辑（简化）
// <ToolMessage v-if="toolCall?.toolMessage" v-bind="toolCall.toolMessage" />

const toolCall = {
  id: 'call_weather',
  type: 'function',
  function: {
    name: 'get_weather',
    arguments: '{"city":"北京"}',
    description: '获取天气信息',
  },
  // 提供此字段后 ToolcallRender 会自动渲染 ToolMessage
  toolMessage: {
    id: '3',
    messageId: '3',
    role: 'tool',
    content: '{"temperature":22,"weather":"晴"}',
    status: 'complete',
    duration: 850,
    toolCallId: 'call_weather',
  },
};
```

## 与 MessageContainer 的关系

`MessageContainer` 通过 `toolCallId` 将 `role: 'tool'` 消息注入对应 AssistantMessage 的 `toolCall.toolMessage`，整个过程自动完成，无需手动引入 `ToolMessage`：

```typescript
const messages = [
  {
    id: '1',
    messageId: '1',
    role: 'assistant',
    content: '好的，我来查询天气。',
    status: 'complete',
    toolCalls: [
      {
        id: 'call_weather',
        type: 'function',
        function: { name: 'get_weather', arguments: '{"city":"北京"}' },
      },
    ],
  },
  {
    id: '2',
    messageId: '2',
    role: 'tool', // MessageContainer 自动处理
    content: '{"temperature":22,"weather":"晴"}',
    status: 'complete',
    toolCallId: 'call_weather', // ← 通过此字段自动关联并注入上方 toolCall
    duration: 850,
  },
];
```

## API

### Props

组件 Props 继承自 `Partial<ToolMessage>`，所有字段均可选：

| 属性名     | 类型               | 说明                                                                            |
| ---------- | ------------------ | ------------------------------------------------------------------------------- |
| content    | `string`                 | 工具执行返回内容；与 `error` 通过 `\|\|` 决定优先级，**truthy 时 error 被忽略** |
| error      | `boolean \| string`      | 类型上可为 boolean；**仅当为 `string` 且 content 为 falsy 时**才会展示           |
| toolCallId | `string`           | 关联的工具调用 ID（透传，组件内不使用）                                         |
| duration   | `number`           | 工具执行耗时（毫秒，透传，组件内不使用）                                        |
| status     | `MessageStatus`    | 消息状态（透传，组件内不使用）                                                  |
| id         | `string \| number` | 消息 ID（透传，组件内不使用）                                                   |
| messageId  | `string \| number` | 消息唯一标识（透传，组件内不使用）                                              |

> **说明**：`ToolMessage` 组件内部只使用 `content` 和 `error` 两个字段（传给 `DescPanel`），其他字段均被透传接收但不使用，由父组件（`ToolcallRender` / `MessageContainer`）在外部管理。

## 类型定义

```typescript
import { MessageRole, MessageStatus, type ToolMessage } from '@blueking/chat-x';

// ToolMessage 继承自 BaseMessage<MessageRole.Tool, string>
interface ToolMessage {
  id: string | number;
  messageId: string | number;
  role: MessageRole.Tool; // 'tool'
  status: MessageStatus;
  content: string;
  toolCallId: string; // 关联的 ToolCall.id
  duration: number; // 工具执行耗时（毫秒）
  error?: boolean | string; // 仅 string 会展示在 DescPanel
  name?: string;
}
```

### Events / Slots / Expose

无。

## 关联组件

- [AssistantMessage](/components/message/assistant-message) — toolCall.toolMessage 内联场景
- [MessageRender](/components/message/message-render) — 独立 tool 消息派发
- [DescPanel](/components/rendering/desc-panel) — 返回内容面板
