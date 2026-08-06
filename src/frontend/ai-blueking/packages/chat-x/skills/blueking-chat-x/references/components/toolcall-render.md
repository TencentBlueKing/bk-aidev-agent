# ToolcallRender 工具调用渲染器

> 能力域：Agent 能力 ｜ 导入：`import { ToolcallRender } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 assistant toolCalls，展示工具调用状态、参数和结果。 源码位置：src/components/tool-call/toolcall-render/toolcall-render.vue。

**关联**：desc-panel（详情区展示参数与描述文本）、highlight-keyword（标题与状态文案关键词高亮）、tool-message（详情底部可内联工具返回消息）

---

# ToolcallRender 工具调用渲染器
## 源码事实

- **源码位置**：`src/components/tool-call/toolcall-render/toolcall-render.vue`
- **能力域**：Agent 能力
- **能力说明**：渲染 assistant toolCalls，展示工具调用状态、参数和结果。

> **能力域**：Agent 能力

展示 AI 调用外部工具/函数过程与结果的渲染组件。由**可折叠头部**和**详情面板**组成，根据 `status` 自动切换颜色和状态文案，支持 MCP 调用识别和内联结果展示。

## 组件结构

```
.ai-toolcall-render
├── .ai-toolcall-render-header（高 40px，class="toolcall-status-{status}"）
│   ├── ArrowRightIcon（14×14px，点击切换折叠；默认 rotate(0deg)，展开后 rotate(90deg)）
│   ├── "调用工具：" / "调用 MCP："（有 mcpName 时）
│   ├── .toolcall-header-title（工具名，overflow-tips 溢出截断）
│   └── .toolcall-status-title
│         ├── Loading（仅 pending / streaming 时显示）
│         ├── 状态文案（调用中 / 调用成功 / 调用失败）
│         └── .toolcall-duration（耗时，如 "(1.2s)"）
│
└── .ai-toolcall-render-content（v-show，默认折叠）
      ├── DescPanel（title="描述"，desc=function.description）← 始终渲染
      ├── DescPanel（title="参数"，desc=function.arguments）← 始终渲染
      └── ToolMessage（v-if="toolCall?.toolMessage"）← 有结果时渲染
```

## 基础用法

```vue
<template>
  <ToolcallRender
    :tool-call="toolCall"
    :status="MessageStatus.Complete"
  />
</template>

<script setup lang="ts">
  import { ToolcallRender, MessageStatus, MessageContentType, type ToolCall } from '@blueking/chat-x';

  const toolCall: ToolCall = {
    id: 'call_1',
    type: MessageContentType.Function,
    function: {
      name: 'get_weather',
      arguments: JSON.stringify({ city: '北京', unit: 'celsius' }),
      description: '获取指定城市的实时天气信息',
    },
    toolMessage: {
      content: JSON.stringify({ city: '北京', temperature: 22, weather: '晴' }),
      status: 'complete',
      duration: 1200,
      toolCallId: 'call_1',
    },
  };
</script>
```

**渲染效果**

## 调用状态

`status` prop 同时控制头部的 CSS class（`toolcall-status-{status}`）、背景/边框颜色、状态文案和 Loading 动画：

| `status`                | 状态文案 | 背景色            | 边框色    | Loading |
| ----------------------- | -------- | ----------------- | --------- | ------- |
| `pending` / `streaming` | 调用中   | `#fafbfd`         | `#dcdee5` | ✓       |
| `complete` / `success`  | 调用成功 | `#ebfaf0`         | `#a1e3ba` | -       |
| `error`                 | 调用失败 | `#fff0f0`         | `#f8b4b4` | -       |
| 其他 / `undefined`      | 调用中   | —（无匹配 class） | —         | -       |

> **说明**：`statusTitle` 的 `switch` 语句中 `default` 与 `case Pending` 共享同一返回值，`streaming` 和未知 status 均命中 `default` 分支，显示"调用中"。Loading 动画由 `v-if="status === 'pending' || status === 'streaming'"` 单独控制。

**三种状态对比**

## 工具标题（toolTitle）

头部标题的计算规则：

```
有 mcpName → "{mcpName} / {function.name}"
无 mcpName → function.name || toolCall.id
```

`function.name` 为空字符串时，自动回退到 `toolCall.id` 作为标题。标题超出容器宽度时截断并配备 overflow-tips。

## 折叠/展开详情面板

详情面板**默认折叠**，点击头部左侧的 **箭头图标**（14×14px 可点区域，非整行）切换折叠状态。折叠状态由 `collapsed`（默认 `true`）和 `superCollapsed` 两个 `shallowRef` 共同管理，不暴露为 prop/v-model。

| 折叠状态     | 箭头旋转角度            | 详情面板      |
| ------------ | ----------------------- | ------------- |
| 折叠（默认） | `rotate(0deg)`（朝右）  | `v-show` 隐藏 |
| 展开         | `rotate(90deg)`（朝下） | 可见          |

详情面板由三块区域构成：

| 区块     | 数据来源               | 渲染方式                                             | 渲染条件                     |
| -------- | ---------------------- | ---------------------------------------------------- | ---------------------------- |
| 描述     | `function.description` | `DescPanel`（纯文本 / key-value 列表）               | **始终渲染**，无值则显示空白 |
| 参数     | `function.arguments`   | `DescPanel`（JSON 对象 → key-value；其他 → 纯文本）  | **始终渲染**，无值则显示空白 |
| 工具结果 | `toolCall.toolMessage` | `ToolMessage` 组件（`v-if="toolCall?.toolMessage"`） | 仅当 `toolMessage` 存在时    |

## 调用耗时

耗时来源优先级（`||` 运算符）：

```typescript
durationDisplay = formatDuration(props.duration || toolCall?.toolMessage?.duration);
```

| 场景                                       | 耗时来源                    |
| ------------------------------------------ | --------------------------- |
| 传入 `duration` prop                       | 使用 prop 值                |
| 未传 `duration`，toolMessage 有 `duration` | 使用 `toolMessage.duration` |
| 两者均无                                   | 不显示耗时                  |

```vue
<!-- 方式一：直接传 duration prop（优先） -->
<ToolcallRender :tool-call="toolCall" status="complete" :duration="1200" />

<!-- 方式二（推荐）：duration 放在 toolMessage 中，无需额外 prop -->
<ToolcallRender :tool-call="toolCallWithDuration" status="complete" />
```

```typescript
// 推荐：duration 统一由 toolMessage 管理
const toolCallWithDuration: ToolCall = {
  id: 'call_1',
  type: 'function',
  function: { name: 'get_weather', arguments: '{"city":"北京"}' },
  toolMessage: {
    content: '{"temperature":22}',
    status: 'complete',
    duration: 1200, // ← 组件自动读取，无需额外传 duration prop
    toolCallId: 'call_1',
  },
};
```

## MCP 工具调用

`function.mcpName` 有值时：

- 头部文案从 **"调用工具："** 自动切换为 **"调用 MCP："**
- 标题格式变为 `{mcpName} / {functionName}`

```typescript
const mcpToolCall: ToolCall = {
  id: 'call_mcp_1',
  type: 'function',
  function: {
    name: 'query_table',
    arguments: JSON.stringify({ table: 'events', limit: 50 }),
    description: '通过 MCP 协议查询蓝鲸数据平台中的事件数据',
    mcpName: 'bk-data-server', // ← 有值时头部显示"调用 MCP："
  },
};
// 头部显示：调用 MCP：  bk-data-server / query_table
```

**渲染效果**

## 调用失败

`toolMessage.error` 有值且 `content` 为空时，`ToolMessage` 内部展示错误信息（由 `content || error` 决定）。`status` 设为 `error` 控制头部红色样式：

```typescript
const failedToolCall: ToolCall = {
  id: 'call_1',
  type: 'function',
  function: {
    name: 'execute_sql',
    arguments: JSON.stringify({ sql: 'SELECT * FROM users' }),
    description: '执行数据库查询',
  },
  toolMessage: {
    content: '', // 空 content → ToolMessage 显示 error
    error: 'Connection timeout: database is unreachable (5000ms)',
    status: 'error',
    duration: 5000,
    toolCallId: 'call_1',
  },
};
```

**渲染效果**

## 无 description 场景

`function.description` 为可选字段，缺失时"描述"区块仍会渲染（`DescPanel` 始终存在），但内容为空白占位：

## 与 AssistantMessage 配合

`ToolcallRender` 通常不需要单独使用，将 `toolCalls` 传给 `AssistantMessage`，会自动为每个工具调用渲染 `ToolcallRender`：

```typescript
const assistantMessage = {
  id: '1',
  role: 'assistant',
  content: '好的，我来帮你查询天气。',
  status: 'complete',
  toolCalls: [
    {
      id: 'call_1',
      type: 'function',
      function: {
        name: 'get_weather',
        arguments: '{"city":"北京"}',
        description: '获取天气信息',
      },
      toolMessage: {
        content: '{"temperature":22,"weather":"晴"}',
        status: 'complete',
        duration: 850,
        toolCallId: 'call_1',
      },
    },
  ],
};
```

需要自定义遍历渲染时：

```vue
<template>
  <ToolcallRender
    v-for="toolCall in assistantMessage.toolCalls"
    :key="toolCall.id"
    :tool-call="toolCall"
    :status="
      !toolCall.toolMessage
        ? MessageStatus.Pending
        : toolCall.toolMessage.error
          ? MessageStatus.Error
          : (toolCall.toolMessage.status ?? assistantMessage.status)
    "
  />
</template>
```

## API

### Props

| 属性名   | 类型            | 默认值 | 说明                                                                        |
| -------- | --------------- | ------ | --------------------------------------------------------------------------- |
| toolCall | `ToolCall`      | —      | 工具调用信息对象                                                            |
| status   | `MessageStatus` | —      | 调用状态，控制头部颜色和状态文案；未传时 `default` 分支显示"调用中"         |
| duration | `number`        | —      | 调用耗时（毫秒），优先于 `toolCall.toolMessage?.duration`；均无时不显示耗时 |

## 类型定义

```typescript
import {
  MessageStatus,
  MessageContentType,
  type ToolCall,
  type FunctionCall,
  type ToolMessage,
} from '@blueking/chat-x';

// ToolCall —— 工具调用对象
type ToolCall = {
  id: string;
  type: 'function'; // MessageContentType.Function
  function: FunctionCall;
  toolMessage?: Partial<ToolMessage>; // 有值时在详情面板底部内联渲染 ToolMessage
};

// FunctionCall —— 函数调用描述
type FunctionCall = {
  name: string; // 函数名；为空时标题 fallback 为 toolCall.id
  arguments: string; // 调用参数（通常为 JSON 字符串）
  description?: string; // 工具描述；为空时"描述"区块保留但内容为空白
  mcpName?: string; // MCP 服务名；有值时头部改为"调用 MCP："，标题格式变为 "{mcpName} / {name}"
};

// ToolMessage —— 工具返回消息
interface ToolMessage {
  role: 'tool';
  content: string; // 返回内容（通常为 JSON 字符串）
  status: MessageStatus;
  duration: number; // 调用耗时（毫秒），被 ToolcallRender 自动读取
  error?: string; // 错误信息（仅当 content 为空时由 ToolMessage 展示）
  toolCallId: string; // 对应 ToolCall.id
}
```

## 关联组件

- [DescPanel](/components/rendering/desc-panel) — 描述与参数面板
- [HighlightKeyword](/components/helper/highlight-keyword) — 标题高亮
- [ToolMessage](/components/message/tool-message) — 内联工具返回
