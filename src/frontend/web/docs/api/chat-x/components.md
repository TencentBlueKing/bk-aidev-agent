# UI 组件 (chat-x)

`@blueking/chat-x` 是 AI 小鲸的纯 UI 组件层，不包含任何业务逻辑。所有组件均可独立使用或自由组合。

## ChatInput

聊天输入框组件，支持文本输入、快捷指令、资源引用、文件上传等功能。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `modelValue` | `string` | `''` | 输入框内容（`v-model`） |
| `cite` | `string` | - | 引用文本 |
| `messageStatus` | `MessageStatus` | - | 当前消息状态（控制发送/停止按钮） |
| `placeholder` | `string` | - | 输入框占位符 |
| `prompts` | `string[]` | - | 预设提示词列表（`/` 触发） |
| `resources` | `IAiSlashMenuItem[]` | `[]` | 资源列表（`@` 触发） |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |
| `shortcutId` | `string` | - | 当前选中的快捷指令 ID |
| `supportUpload` | `boolean` | `false` | 是否支持文件上传 |
| `models` | `IModelOption[]` | — | 可选模型列表；传入后在发送按钮左侧展示 ModelSelector |
| `onSendMessage` | `(message: string) => void` | - | 发送消息回调 |
| `onStopSending` | `() => void` | - | 停止发送回调 |
| `onUpload` | `(file: File) => void` | - | 文件上传回调 |

### v-model

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `selectedModel` | `string` | 当前选中模型的 `llm_name` |

### Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `select-shortcut` | `(shortcut: IShortcut)` | 选择快捷指令 |
| `delete-shortcut` | - | 删除当前快捷指令 |
| `model-change` | `(model: IModelOption)` | 切换模型 |

### Slots

| 插槽名 | 说明 |
| --- | --- |
| `top` | 输入框上方区域 |
| `input-header` | 输入框头部区域 |
| `attachment` | 附件区域 |
| `send-icon` | 自定义发送按钮图标 |

### Expose

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `focus` | `() => void` | 聚焦输入框 |

### 快捷键

| 快捷键 | 说明 |
| --- | --- |
| `Enter` | 发送消息 |
| `Shift + Enter` | 换行 |
| `/` | 触发提示词选择 |
| `@` | 触发资源选择 |
| `↑` / `↓` | 在提示词/资源列表中导航 |
| `Esc` | 关闭提示词/资源选择面板 |

### 用法示例

```vue
<template>
  <ChatInput
    v-model="inputText"
    :message-status="status"
    :shortcuts="shortcuts"
    placeholder="输入你的问题..."
    @send-message="onSend"
    @stop-sending="onStop"
  />
</template>
```

## MessageContainer

消息列表容器，负责渲染消息列表和管理消息选择。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `messages` | `Message[]` | `[]` | 消息列表 |
| `messageStatus` | `MessageStatus` | - | 当前消息状态 |
| `messageToolsStatus` | `MessageToolsStatus` | - | 消息工具栏状态 |
| `enableSelection` | `boolean` | `false` | 是否启用多选模式 |
| `onAgentAction` | `(tool, message) => void` | - | Agent 消息工具栏点击回调 |
| `onAgentFeedback` | `(tool, message, reasons, other) => void` | - | Agent 反馈回调 |
| `onUserAction` | `(tool, message) => void` | - | 用户消息工具栏点击回调 |
| `onUserInputConfirm` | `(message, content) => void` | - | 用户编辑消息确认回调 |
| `onUserShortcutConfirm` | `(message, formData) => void` | - | 用户快捷指令表单确认回调 |

### v-model

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `selectedMessages` | `Message[]` | 选中的消息列表（多选模式下） |

### Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `stopStreaming` | - | 停止流式输出 |

### Slots

| 插槽名 | 参数 | 说明 |
| --- | --- | --- |
| `default` | `{ message }` | 自定义单条消息渲染 |

### Expose

| 方法/属性 | 类型 | 说明 |
| --- | --- | --- |
| `isAllSelected` | `ComputedRef<boolean>` | 是否已全选 |
| `selectAll` | `() => void` | 全选所有消息 |
| `deselectAll` | `() => void` | 取消全选 |

### 用法示例

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="status"
    :enable-selection="isSelectionMode"
    v-model:selected-messages="selectedMsgs"
    @stop-streaming="onStop"
  />
</template>
```

## MessageRender

单条消息渲染组件，根据消息角色自动选择对应的渲染方式。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `message` | `Partial<Message>` | - | 消息对象 |
| `onAction` | `(tool, message) => void` | - | 工具栏操作回调 |

### Slots

| 插槽名 | 参数 | 说明 |
| --- | --- | --- |
| `default` | `{ content, status }` | 自定义消息内容渲染 |

### 角色与组件映射

| 角色 (`MessageRole`) | 渲染组件 | 说明 |
| --- | --- | --- |
| `User` | `UserMessage` | 用户消息，支持编辑 |
| `Assistant` | `AssistantMessage` | AI 回复，支持 Markdown 渲染 |
| `Reasoning` | `ReasoningMessage` | 推理过程（思考链） |
| `Tool` | `ToolMessage` | 工具调用结果 |
| `Activity` | `ActivityMessage` | 活动/状态消息 |
| `Info` | `InfoMessage` | 信息提示 |
| `System` | `SystemMessage` | 系统消息 |

### 用法示例

```vue
<template>
  <MessageRender :message="msg" :on-action="handleAction" />
</template>
```

## ShortcutRender

快捷指令表单渲染组件，根据快捷指令配置渲染动态表单。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `string` | - | 快捷指令名称 |
| `components` | `ShortcutComponent[]` | `[]` | 表单组件列表 |
| `formModel` | `Record<string, any>` | `{}` | 表单数据模型 |
| `description` | `string` | - | 快捷指令描述 |

### Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `close` | - | 关闭快捷指令表单 |
| `submit` | `(formData: Record<string, any>)` | 提交表单数据 |

### 用法示例

```vue
<template>
  <ShortcutRender
    :name="shortcut.name"
    :components="shortcut.components"
    :form-model="shortcut.formModel"
    :description="shortcut.description"
    @close="onClose"
    @submit="onSubmit"
  />
</template>
```

## ShortcutBtns

快捷指令按钮组，以按钮组形式展示快捷指令列表。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |

### Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `selectShortcut` | `(shortcut: IShortcut)` | 选择快捷指令 |

### 用法示例

```vue
<template>
  <ShortcutBtns :shortcuts="shortcuts" @select-shortcut="onSelect" />
</template>
```

## ModelSelector {#modelselector}

模型下拉选择器，支持搜索与能力标签。通常由 `ChatInput` / `ChatContainer` 在传入 `models` 后自动渲染于发送按钮左侧；也可独立使用。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `models` | `IModelOption[]` | `[]` | 可选模型列表 |
| `disabled` | `boolean` | `false` | 是否禁用 |
| `placeholder` | `string` | `'选择模型'` | 无选中时的占位文案 |
| `searchPlaceholder` | `string` | `'搜索模型关键字'` | 搜索框占位文案 |

### v-model

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| — | `string` | 当前选中模型的 `llm_name` |

### Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `change` | `(model: IModelOption)` | 用户选中模型时触发 |

### 用法示例

```vue
<template>
  <ModelSelector
    v-model="selectedModel"
    :models="models"
    @change="handleModelChange"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ModelSelector, type IModelOption } from '@blueking/chat-x';

const selectedModel = ref('混元预览');
const models: IModelOption[] = [
  {
    id: 1,
    llm_code: 'hy3-preview',
    llm_name: '混元预览',
    llm_type: 'chat.completion',
    max_token_size: 128000,
    property: { default: true, support_thinking: true },
    space_auth_mode: '',
    user_auth_mode: '',
  },
];

const handleModelChange = (model: IModelOption) => {
  console.log('选中:', model.llm_code);
};
</script>
```

::: tip 与小鲸业务层的关系
`AIBlueking` / `ChatBot` 默认启用模型选择，由 `ChatBusinessManager` 编排拉取与选中。详见 [模型选择](/guide/core-features/model-selection)。
:::

## AiSelection

AI 选区组件，用于在页面中通过选区触发快捷指令。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `visible` | `boolean` | `false` | 是否显示（`v-model`） |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |
| `maxShortcutCount` | `number` | - | 最大显示快捷指令数量 |
| `offset` | `{ x: number; y: number }` | - | 偏移量 |

### Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `selectShortcut` | `(shortcut: IShortcut)` | 选择快捷指令 |
| `selectionChange` | `(text: string)` | 选区文本变化 |

### Slots

| 插槽名 | 参数 | 说明 |
| --- | --- | --- |
| `default` | `{ shortcuts }` | 自定义快捷指令渲染 |

### 用法示例

```vue
<template>
  <AiSelection
    v-model:visible="showSelection"
    :shortcuts="shortcuts"
    :max-shortcut-count="5"
    @select-shortcut="onSelect"
    @selection-change="onSelectionChange"
  />
</template>
```

## ContentRender

内容渲染组件，支持 Markdown 渲染（含 v2.1.4-beta.6+ 蓝鲸行内富文本 `::bk{...}...:/bk::`，不解析任意 HTML）。

### Props

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `content` | `string` | `''` | 要渲染的内容（支持 Markdown 及蓝鲸行内富文本） |

### 用法示例

```vue
<template>
  <ContentRender content="## 标题\n这是一段 **Markdown** 内容。" />
  <ContentRender content="::bk{color=red; bold}重要:/bk::" />
</template>
```

行内富文本语法与 LLM 提示词配置见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)。
