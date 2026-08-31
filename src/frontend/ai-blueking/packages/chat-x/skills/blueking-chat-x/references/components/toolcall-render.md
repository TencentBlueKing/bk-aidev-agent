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

展示 AI 调用外部工具 / MCP / Skill 过程与结果的渲染组件。由**单行可折叠头部**和**详情面板**组成：头部是一段弱化的灰色文本（`#979ba5`），按调用类型给出前缀，进行中用文字渐变闪动表示、结束后在工具名右侧补一段状态与耗时；详情面板默认折叠。

## 组件结构

```
.ai-toolcall-render（font-size: 12px，line-height: 20px）
├── .ai-toolcall-render-header（单行，整行可点击切换折叠；class="is-expanded" 表示已展开）
│   ├── ToolCallIcon（.ai-toolcall-icon，16×16px）
│   ├── .toolcall-header-text（内联文本块，溢出截断 + overflow-tips）
│   │     ├── .toolcall-header-title（前缀 + HighlightKeyword(工具名)）
│   │     │     └── .is-loading（进行中，渐变光带闪动）
│   │     └── .toolcall-header-status（v-if 有状态词；括号与耗时为弱显示）
│   │           └── .toolcall-header-result（.is-success #2caf5e / .is-error #ea3636）
│   └── ChevronRightIcon（.ai-chevron-right-icon，10×10px；v-if 非进行中，展开时 rotate(90deg)）
│
└── .ai-toolcall-render-content（v-show，默认折叠，子项 gap: 8px）
      ├── DescPanel（title="描述"，desc=function.description）← 始终渲染
      ├── DescPanel（title="参数"，desc=function.arguments）← 始终渲染
      └── ToolMessage（v-if="toolCall?.toolMessage"）← 有结果时渲染
```

> **头部悬停/展开反馈**：头部默认 `#979ba5`；`:hover` 或 `.is-expanded` 时，`ToolCallIcon` 与非闪动态的工具名变为 `#313238`，展开态的箭头同样变为 `#313238`。头部不再有背景色与边框（旧版的 `$toolcallStatusMap` 状态底色已随重构移除）。

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

组件内部把 `status` 归一为**成功 / 失败 / 进行中**三态，不再逐个 status 匹配底色：

```typescript
isSuccess = [complete, completed, success].includes(status);
isError = status === 'error' || !!toolCall?.toolMessage?.error; // toolMessage.error 可独立判定失败
isPending = !isSuccess && !isError; // 其余（含 pending / streaming / stop / undefined）统一视为进行中
```

| 归一状态 | 命中条件                                             | 头部渲染                                                       |
| -------- | ---------------------------------------------------- | -------------------------------------------------------------- |
| 进行中   | 非成功且非失败（含未传 `status`）                    | 前缀替换为「正在调用」（Skill 为「正在读取」），标题带 `is-loading` 闪动，无状态段、无箭头 |
| 成功     | `complete` / `completed` / `success`                 | 状态段 `( 成功 )`，状态词 `#2caf5e`                            |
| 失败     | `status === 'error'` **或** `toolMessage.error` 为真 | 状态段 `( 失败 )`，状态词 `#ea3636`                            |

关于状态段的三个细节：

- **只有状态词着色**：`.toolcall-header-result` 只包住「成功 / 失败」，括号与耗时留在 `.toolcall-header-status` 内保持弱显示
- **括号写法**：头部渲染用半角括号并在两侧补 `&nbsp;` 撑开间距；`overflow-tips` 气泡里的纯文本用全角括号，形如 `调用工具 search（成功，耗时：1.2s）`
- **失败优先**：`toolMessage.error` 有值时即便 `status` 是成功态也判为失败

进行中的「文字 loading」由 CSS 实现：`.toolcall-header-title.is-loading` 用 `linear-gradient` + `background-clip: text` 让一条光带以 `1.8s linear infinite` 循环扫过文字；`prefers-reduced-motion: reduce` 下自动关闭动画。

**三种状态对比**

## 调用类型前缀

非进行中态的前缀由 `function.type` 决定；进行中态工具 / MCP 显示「正在调用」，Skill 显示「正在读取」：

| `function.type`          | 前缀        | 说明                                     |
| ------------------------ | ----------- | ---------------------------------------- |
| `'function'` / 不传      | 调用工具    | 普通函数调用                             |
| `'mcp'`                  | 调用 MCP    | MCP 调用，通常同时带 `mcpName`           |
| `'skill'`                | 读取 Skill  | Skill 读取                               |

```typescript
const callType = fn?.type ?? (fn?.mcpName ? 'mcp' : 'function');
```

- **旧数据兼容**：未下发 `type` 时，有 `mcpName` 仍按 MCP 判定，历史消息展示不变
- **`type` 优先**：显式 `type: 'function'` 不会被 `mcpName` 覆盖回 MCP，但标题仍是 `{mcpName} / {name}`

**三种前缀对比**

## 工具标题（toolTitle）

头部标题的计算规则：

```
有 mcpName → "{mcpName} / {function.name}"
无 mcpName → function.name || toolCall.id
```

`function.name` 为空字符串时，自动回退到 `toolCall.id` 作为标题。前缀、标题与状态段同处一个内联文本块 `.toolcall-header-text`，整体超出容器宽度时统一截断，并由 overflow-tips 展示完整文案。

## 折叠/展开详情面板

详情面板**默认折叠**，点击**整行头部**切换折叠状态（旧版仅箭头可点）。折叠状态由 `collapsed`（默认 `true`）和 `superCollapsed` 两个 `shallowRef` 管理，不暴露为 prop/v-model。

| 折叠状态     | 箭头                                | 头部 class    | 详情面板      |
| ------------ | ----------------------------------- | ------------- | ------------- |
| 折叠（默认） | `ChevronRightIcon` 朝右             | —             | `v-show` 隐藏 |
| 展开         | `rotate(90deg)` 朝下，颜色 `#313238` | `is-expanded` | 可见          |

> **进行中不渲染箭头**：`isPending` 为真时箭头隐藏（此时通常还没有结果可看），但头部点击仍会切换详情面板。
>
> **关键词联动**：接入 `useKeywordMatch` 后，若上层正在搜索关键词且用户未手动点过头部（`superCollapsed` 为 `null`），面板会按「命中关键词则展开」自动切换；用户一旦点击，`superCollapsed` 接管并固定为手动选择的状态。

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

耗时不再单独占一个元素，而是拼进状态段：有耗时时渲染为 `( 成功，耗时：1.2s )`，无耗时时只保留 `( 成功 )`。进行中态没有状态段，因此也不展示耗时。

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

## MCP 调用

`function.type` 为 `'mcp'`（或旧数据仅有 `mcpName`）时，前缀为「调用 MCP」，标题格式变为 `{mcpName} / {functionName}`：

```typescript
const mcpToolCall: ToolCall = {
  id: 'call_mcp_1',
  type: 'function',
  function: {
    type: 'mcp', // ← 前缀显示「调用 MCP」；缺省时有 mcpName 也会兼容判定为 MCP
    name: 'query_table',
    arguments: JSON.stringify({ table: 'events', limit: 50 }),
    description: '通过 MCP 协议查询蓝鲸数据平台中的事件数据',
    mcpName: 'bk-data-server',
  },
};
// 头部显示：调用 MCP bk-data-server / query_table（成功，耗时：830ms）
```

## 调用失败

`toolMessage.error` 有值且 `content` 为空时，`ToolMessage` 内部展示错误信息（由 `content || error` 决定）。头部状态词是否红色由 `status === 'error'` **或** `toolMessage.error` 任一命中决定，因此下例即使不传 `status` 也会显示失败：

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

> **多条工具调用**：`AssistantMessage` 把 `toolCalls` 包在 `.ai-assistant-message-toolcalls` 容器内，条目之间固定 `8px` 间距，不受消息区 `12px` 间距影响。

## API

### Props

| 属性名   | 类型            | 默认值 | 说明                                                                                |
| -------- | --------------- | ------ | ----------------------------------------------------------------------------------- |
| toolCall | `ToolCall`      | —      | 工具调用信息对象                                                                    |
| status   | `MessageStatus` | —      | 调用状态，归一为成功 / 失败 / 进行中三态；未传时按进行中渲染（「正在调用」+ 闪动）  |
| duration | `number`        | —      | 调用耗时（毫秒），优先于 `toolCall.toolMessage?.duration`；均无时状态段不展示耗时   |

## 类型定义

```typescript
import {
  MessageStatus,
  MessageContentType,
  type ToolCall,
  type FunctionCall,
  type FunctionCallType,
  type ToolMessage,
} from '@blueking/chat-x';

// ToolCall —— 工具调用对象
type ToolCall = {
  id: string;
  type: 'function'; // MessageContentType.Function
  function: FunctionCall;
  toolMessage?: Partial<ToolMessage>; // 有值时在详情面板底部内联渲染 ToolMessage
};

// FunctionCallType —— 调用类型
type FunctionCallType = 'function' | 'mcp' | 'skill';

// FunctionCall —— 函数调用描述
type FunctionCall = {
  name: string; // 函数名；为空时标题 fallback 为 toolCall.id
  arguments: string; // 调用参数（通常为 JSON 字符串）
  description?: string; // 工具描述；为空时"描述"区块保留但内容为空白
  mcpName?: string; // MCP 服务名；有值时标题格式变为 "{mcpName} / {name}"，缺省 type 时兼容判定为 MCP
  type?: FunctionCallType; // 调用类型，决定头部前缀；不传按 mcpName 兼容判定
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
