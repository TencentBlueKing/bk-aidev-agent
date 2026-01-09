# Props

组件支持的属性列表。

::: warning 版本变更提示
部分属性在1.0版本中的行为有所变化，请注意查看相关说明。
:::

| 属性名            | 类型               | 默认值                                                    | 描述                                                                                                                                                                                                  |
| ----------------- | ------------------ | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `url`             | `String`           | `''`                                                      | **必需**. AI 服务接口地址，1.0版本中用于获取智能体配置信息。                                                                                                                                          |
| `title`           | `String`           | `'AI 小鲸'`                                               | 在头部显示的标题文本。                                                                                                                                                                                |
| `helloText`       | `String`           | `'你好，我是小鲸'`                                        | 初始欢迎页面显示的问候语。在1.0版本中，智能体配置的开场白(`openingRemark`)优先级高于此属性。                                                                                                          |
| `enablePopup`     | `Boolean`          | `true`                                                    | 是否启用选中文本后的弹出操作窗口 (需要配合 `shortcuts` 使用)。<Badge type="tip" text="v1.3.2 增强" /> 现在会与智能体配置的 `conversationSettings.enableWordSelectionPopup` 联动控制，只有当两者都不为 `false` 时才启用。 |
| `prompts`         | `Array<String>`    | `[]`                                                      | 预设提示词列表。在1.0版本中，这些提示词会与智能体配置的预设问题(`predefinedQuestions`)合并展示。                                                                                                      |
| `requestOptions`  | `Object`           | `{}`                                                      | 自定义请求选项，可设置 `headers`、`data` 和 `context` 属性。**v1.1.5 新增** `context` 支持静态对象或动态函数形式传递上下文信息。详细说明参见 [自定义请求指南](/guide/advanced-usage/custom-requests)。 |
| `shortcuts`       | `Array<IShortcut>` | `[]`                                                      | 快捷操作列表。详细格式参见 [内容引用与快捷操作指南](/guide/core-features/content-referencing#配置快捷操作-shortcuts)。                                                                                |
| `defaultMinimize` | `Boolean`          | `false`                                                   | 控制 AI 小鲸窗口初始是否处于最小化状态。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#初始最小化状态)。                                                                           |
| `teleportTo`      | `String`           | `'body'`                                                  | 控制组件内容传送到的 DOM 节点，可将组件内容渲染到任意 DOM 位置。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#自定义传送目标)。                                                   |
| `hideHeader`      | `Boolean`          | `false`                                                   | 设置为`true`时隐藏组件的头部栏。                                                                                                                                                                      |
| `hideNimbus`      | `Boolean`          | `false`                                                   | 设置为`true`时隐藏Nimbus悬浮图标。                                                                                                                                                                    |
| `nimbusSize`      | `String`           | `'normal'`                                                | 设置 Nimbus 悬浮图标的尺寸。可选值为 `'small'`, `'normal'`, `'large'`。                                                                                                                               |
| `draggable`       | `Boolean`          | `true`                                                    | 控制组件是否可拖拽。设置为 `false` 时，窗口将固定在位置上不可移动。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。                                    |
| `defaultWidth`    | `Number`           | `400`                                                     | 设置组件初始宽度，单位为像素。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。                                                                         |
| `defaultHeight`   | `Number`           | `undefined`                                               | 设置组件初始高度，单位为像素，不设置组件会动态计算，设置为视窗高度。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。                                   |
| `defaultTop`      | `Number`           | `0`                                                       | 设置组件初始顶部位置，单位为像素。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。                                                                     |
| `defaultLeft`     | `Number`           | `undefined`                                               | 设置组件初始左侧位置，单位为像素。不设置会动态计算，设置为 `视窗宽度 - defaultWidth`。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。                 |
| `disabledInput`   | `Boolean`          | `false`                                                   | 控制输入框是否处于禁用状态。设置为 `true` 时，用户无法在输入框中输入文本。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#输入框禁用控制)。                                         |
| `showHistoryIcon` | `Boolean`          | `true`                                                    | <Badge type="tip" text="v1.1.0" /> 控制头部历史会话图标的显示。设置为 `false` 时隐藏历史会话按钮。                                                                                                                        |
| `showNewChatIcon` | `Boolean`          | `true`                                                    | <Badge type="tip" text="v1.1.0" /> 控制头部新聊天图标的显示。设置为 `false` 时隐藏新建聊天按钮。                                                                                                                          |
| `placeholder`     | `String`           | `'输入 "/" 唤出 Prompt\n通过 Shift + Enter 进行换行输入'` | <Badge type="tip" text="v1.1.1" /> 输入框占位符文本。可以自定义提示用户如何使用输入框。                                                                                                                                   |
| `miniPadding`     | `Number`           | `0`                                                       | <Badge type="tip" text="v1.1.2" /> 压缩状态下的边距，单位为像素。控制组件在压缩状态时与屏幕边缘的距离。                                                                                                                   |
| `initialSessionCode` | `String`        | `''`                                                    | <Badge type="tip" text="v1.2.2" /> 指定组件初始化时要加载的会话代码。如果设置了此属性且 `autoSwitchToInitialSession` 为 `true`，组件将在加载时自动切换到该会话。                                                           |
| `autoSwitchToInitialSession` | `Boolean` | `true`                                                    | <Badge type="tip" text="v1.2.2" /> 控制是否在组件初始化时自动切换到 `initialSessionCode` 指定的会话。设置为 `false` 时，仅加载会话列表但不自动切换。                                                                      |
| `extCls`      | `String`           | `''`                                                      | <Badge type="tip" text="v1.2.3" /> 自定义组件根元素的类名，方便用户进行样式覆盖和扩展。 |
| `sessionList` | `Array<ISession>`  | `[]`                                                      | <Badge type="tip" text="v1.2.3" /> 会话列表，用于展示和管理多个会话。 |
| `shortcutLimit` | `Number`         | `3`                                                       | <Badge type="tip" text="v1.2.3" /> 快捷指令在popover中显示的数量限制。 |
| `shortcutFilter`| `Function`       | `undefined`                                               | <Badge type="tip" text="v1.2.4" /> 快捷指令的过滤函数，用于动态控制快捷指令的显示。当用户选中文本时，每个快捷指令的组件会自动获得 `selectedText` 属性，可在过滤函数中访问该属性以根据选中文本内容进行过滤。函数签名：`(shortcut: IShortcut, selectedText: string) => boolean` |
| `enableChatSession` | `Boolean`    | `true`                                                    | <Badge type="tip" text="v1.2.3" /> 控制是否启用多会话功能。此属性由后端通过 `getAgentInfo` 接口返回的 `conversationSettings.enableChatSession` 配置决定，当设置为 `false` 时将隐藏会话管理相关UI元素。 |
| `loadRecentSessionOnMount` | `Boolean` | `false`                                                   | <Badge type="tip" text="v1.2.5" /> 控制组件挂载时是否自动加载最近会话。设置为 `true` 时，组件初始化时会自动加载并切换到最近的会话，优化会话初始化体验。 |
| `hasSessionContents` | `Boolean`   | `true`                                                    | <Badge type="tip" text="v1.2.5" /> 控制当前是否有会话内容。此属性影响某些UI元素的显示状态，如为空会话时的提示信息等。 |
| `hideDefaultTrigger` | `Boolean`   | `false`                                                   | <Badge type="tip" text="v1.2.7" /> 控制是否隐藏默认的触发按钮。设置为 `true` 时，隐藏默认的AI小鲸触发按钮，适用于需要完全自定义触发方式的场景。 |
| `dropdownMenuConfig` | `Object`    | `{ showRename: true, showAutoGenerate: true, showShare: true }` | <Badge type="tip" text="v1.2.7" /> 下拉菜单配置对象，用于控制会话操作菜单中各项功能的显示。包含 `showRename` (是否显示重命名选项)、`showAutoGenerate` (是否显示自动生成命名选项)、`showShare` (是否显示分享选项) 三个布尔值属性。<Badge type="info" text="v1.3.0" /> `showShare` 默认值从 `false` 改为 `true`。 |
| `iconRender`        | `Function`  | `undefined`                                                    | <Badge type="tip" text="v1.2.8" /> 自定义图标渲染函数，用于替代 `icon` 属性提供更灵活的图标渲染方式。函数接收 Vue 的 `h` 函数作为参数，返回 VNode 节点。当同时设置 `iconRender` 和 `icon` 时，优先使用 `iconRender`。 |
| `showCompressionIcon` | `Boolean` | `true`                                                     | <Badge type="tip" text="v1.2.9" /> 控制是否显示压缩图标。设置为 `false` 时隐藏压缩图标按钮。 |
| `showMoreIcon`      | `Boolean`   | `true`                                                     | <Badge type="tip" text="v1.2.9" /> 控制是否显示更多图标。设置为 `false` 时隐藏更多操作图标按钮。 |
| `defaultChatInputPosition` | `String` | `undefined`                                              | <Badge type="tip" text="v1.2.9" /> 设置默认输入框位置。可选值为 `'bottom'` 或 `undefined`，当设置为 `'bottom'` 时输入框始终显示在底部，`undefined` 时根据是否有会话内容自动判断位置。 |
| `maxWidth`          | `Number` \| `String` | `1000`                                               | <Badge type="tip" text="v1.2.9" /> 设置组件最大宽度。可以是数字（像素值）或字符串（如 '100%'）。 |

## 划词弹窗控制增强 <Badge type="tip" text="v1.3.2" />

v1.3.2 版本优化了划词弹窗的控制逻辑，现在支持通过多个层级进行精细化控制：

### 控制优先级

划词弹窗的启用状态由以下两个配置共同决定：

1. **组件级配置**：`enablePopup` prop（优先级最高）
2. **智能体级配置**：`conversationSettings.enableWordSelectionPopup`（通过 API 返回）

**启用规则**：只有当两者都不为 `false` 时，划词弹窗功能才会启用。

### 配置示例

```vue
<template>
  <!-- 场景1：强制禁用划词弹窗 -->
  <AIBlueking
    :url="apiUrl"
    :enable-popup="false"
  />
  <!-- 无论智能体配置如何，划词弹窗都不会启用 -->

  <!-- 场景2：由智能体配置控制 -->
  <AIBlueking
    :url="apiUrl"
    :enable-popup="true"
  />
  <!-- 实际是否启用取决于智能体的 conversationSettings.enableWordSelectionPopup -->

  <!-- 场景3：检查实际启用状态 -->
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :enable-popup="true"
  />
  <button @click="checkPopupStatus">检查状态</button>
</template>

<script setup>
import { ref } from 'vue'
import { AIBlueking } from '@blueking/ai-blueking'

const aiBlueking = ref(null)

const checkPopupStatus = () => {
  const agentInfo = aiBlueking.value?.agentInfo
  const enableWordSelectionPopup = agentInfo?.conversationSettings?.enableWordSelectionPopup

  // 最终启用状态 = props.enablePopup && conversationSettings.enableWordSelectionPopup !== false
  console.log('划词弹窗最终状态:', enableWordSelectionPopup !== false)
}
</script>
```

### 使用场景

这种设计适用于以下场景：

- **全局控制**：前端统一禁用划词功能（`enablePopup: false`）
- **智能体级控制**：由后端根据智能体类型决定是否启用划词功能
- **动态调整**：智能体配置更新后，前端无需修改代码即可生效
- **灵活组合**：前端和后端配合实现更精细的功能控制

## 压缩状态边距控制 <Badge type="tip" text="v1.1.2" />

v1.1.2版本新增了 `miniPadding` 属性，用于控制组件在压缩状态下与屏幕边缘的距离：

### 使用示例

```vue
<template>
  <!-- 设置20像素的压缩边距 -->
  <AIBlueking :url="apiUrl" :mini-padding="20" />

  <!-- 无边距压缩（默认） -->
  <AIBlueking :url="apiUrl" :mini-padding="0" />
</template>
```

## 多会话管理功能 <Badge type="tip" text="v1.1.0" />

v1.1.0版本引入了全新的多会话管理功能，支持创建、切换、编辑和删除多个聊天会话：

### 会话管理特性

- **🆕 多会话支持**：可以创建和管理多个独立的聊天会话
- **📊 历史面板**：按时间分组显示历史会话（今天、昨天、3天前、5天前、1周前、更早）
- **🔍 会话搜索**：在历史面板中搜索特定会话
- **✏️ 会话重命名**：直接编辑会话名称
- **🗑️ 安全删除**：删除会话时提供确认机制
- **🎨 动态标题**：头部显示当前会话名称

### 相关属性

通过 `showHistoryIcon` 和 `showNewChatIcon` 属性可以控制会话管理相关图标的显示：

```vue
<template>
  <!-- 显示所有会话管理功能 -->
  <AIBlueking :url="apiUrl" :show-history-icon="true" :show-new-chat-icon="true" />

  <!-- 只显示新聊天功能，隐藏历史面板 -->
  <AIBlueking :url="apiUrl" :show-history-icon="false" :show-new-chat-icon="true" />

  <!-- 自定义输入框占位符 -->
  <AIBlueking :url="apiUrl" placeholder="请输入您的问题，我来为您解答..." />

  <!-- 自定义下拉菜单配置 -->
  <AIBlueking
    :url="apiUrl"
    :dropdown-menu-config="{
      showRename: true,
      showAutoGenerate: true,
      showShare: true
    }"
  />

  <!-- 自定义压缩边距 -->
  <AIBlueking :url="apiUrl" :mini-padding="20" :default-width="500" :default-height="600" />

  <!-- URL协议自动适配和上下文配置 -->
  <AIBlueking
    :url="'/api/chat'"
    :request-options="{
      headers: { Authorization: 'Bearer token' },
      context: { userId: '123', department: 'IT' },
    }"
  />

  <!-- 动态上下文配置 -->
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      context: () => ({
        userId: getCurrentUserId(),
        timestamp: Date.now(),
      }),
    }"
  />
</template>
```

## URL 协议自动适配 <Badge type="tip" text="v1.1.5" />

从 v1.1.5 开始，AI 小鲸支持智能的 URL 协议适配功能：

### 支持的URL格式

- **相对路径**：`/api/chat` - 自动使用当前页面的协议和域名
- **协议相对路径**：`//api.example.com/chat` - 自动使用当前页面的协议
- **完整URL**：`http://api.example.com/chat` - HTTPS页面下自动转换为HTTPS
- **HTTPS URL**：`https://api.example.com/chat` - 任何环境下保持HTTPS

### 安全性提升

在HTTPS页面中使用HTTP API时，组件会自动将其转换为HTTPS，提升安全性。

## 上下文配置 <Badge type="tip" text="v1.1.5" />

通过 `requestOptions.context` 可以传递上下文信息给AI服务：

### 静态上下文

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      context: {
        userId: '123',
        department: 'IT',
        role: 'admin',
      },
    }"
  />
</template>
```

### 动态上下文

```vue
<template>
  <AIBlueking :url="apiUrl" :request-options="requestOptions" />
</template>

<script setup>
  import { computed } from "vue"

  const requestOptions = computed(() => ({
    context: () => ({
      userId: getCurrentUser().id,
      sessionId: getSessionId(),
      timestamp: Date.now().toString(),
    }),
  }))
</script>
```

::: danger 已废弃属性
以下属性在1.0版本中已被移除:

- `defaultMessages`: 预设对话内容属性已被移除，在1.0版本中改为从智能体配置获取。详情请参阅[预设对话内容指南](/guide/advanced-usage/default-messages)。
  :::

## `IShortcut` 对象格式

`shortcuts` 数组中的每个对象应符合以下格式：

```typescript
interface IShortcut {
  id: string // 快捷操作的唯一标识符
  name: string // 显示的操作名称
  icon?: string // 按钮图标的类名
  /**
   * 自定义图标渲染函数
   * @param h - Vue 的 h 函数，用于创建 VNode
   * @returns VNode
   * @since v1.2.8
   */
  iconRender?: (h: typeof import('vue').h) => import('vue').VNode // <Badge type="tip" text="v1.2.8" /> 自定义图标渲染函数
  // 组件配置，用于定义表单项
  components: Array<{
    type: string // 组件类型：'input', 'text', 'textarea', 'select', 'number' 等
    name?: string // 表单项名称
    key: string // 表单项键名
    placeholder?: string // 占位文本
    default?: any // 默认值
    required?: boolean // 是否必填
    fillBack?: boolean // 是否自动填充选中文本
    fillRegx?: string | RegExp // 填充的正则匹配表达式
    rows?: number // 输入框行数（仅 textarea 类型有效）
    min?: number // 最小值（仅 number 类型有效）
    max?: number // 最大值（仅 number 类型有效）
    options?: Array<{
      // 下拉选项（仅select类型）
      label: string
      value: string | number
    }>
    hide?: boolean // 是否隐藏该组件（v1.2.4-beta.3 新增）
  }>
}
```

### 组件类型

目前支持以下类型的表单组件：

| 组件类型   | 描述           | 特有属性                            |
| ---------- | -------------- | ----------------------------------- |
| `text`     | 单行文本输入框 | `placeholder`                       |
| `textarea` | 多行文本输入框 | `placeholder`, `rows`               |
| `number`   | 数字输入框     | `min`, `max`, `default`             |
| `select`   | 下拉选择框     | `options`, `placeholder`, `default` |

### 自动填充功能

通过设置 `fillBack: true`，表单项可以自动填充用户选中的文本：

```javascript
{
  id: 'translate',
  name: '翻译文本',
  icon: 'bkai-translate',
  components: [
    {
      type: 'textarea',
      key: 'text',
      name: '待翻译文本',
      fillBack: true, // 启用自动填充
      fillRegx: '.*', // 可选，使用正则表达式匹配选中的文本
      placeholder: '请输入或选中需要翻译的文本'
    },
    {
      type: 'select',
      key: 'targetLang',
      name: '目标语言',
      options: [
        { label: '中文', value: 'zh' },
        { label: '英文', value: 'en' },
        { label: '日文', value: 'jp' }
      ],
      placeholder: '请选择目标语言'
    }
  ]
}
```

## RequestOptions 配置

组件的 `requestOptions` 属性支持以下配置项：

```typescript
interface IRequestOptions {
  headers?: Record<string, any> // 请求头参数
  data?: Record<string, any> // 请求体附加数据
  context?: Array<{
    // 上下文参数数据
    key: string // 参数键名
    value: any // 参数值
  }> | (() => Array<{ key: string, value: any }> | undefined) // 上下文参数数据，支持静态数组或动态函数
}
```

### 示例

```vue
<template>
  <AIBlueking
    :request-options="{
      headers: {
        'X-Custom-Header': 'value',
      },
      data: {
        preset: 'QA',
      },
      context: [
        { key: 'language', value: 'javascript' },
        { key: 'scenario', value: 'code_review' },
      ],
    }"
  />
</template>
```

这些参数会在发送请求时与其他参数一起发送，其中 `context` 会被合并到快捷操作的表单数据中，作为上下文信息传递给后端。

## 暴露属性

组件实例暴露了以下属性，可用于获取组件的内部状态：

### sessionContents

获取当前会话的消息内容列表：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="getContents">获取会话内容</button>
</template>

<script setup>
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"

  const aiBlueking = ref(null)

  const getContents = () => {
    const contents = aiBlueking.value?.sessionContents
    console.log("当前会话内容:", contents)
  }
</script>
```

### agentInfo <Badge type="tip" text="v1.3.2" />

获取智能体的完整配置信息，包含名称、问候语、快捷指令、会话配置等：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="showAgentInfo">查看智能体信息</button>
  <button @click="checkPopupEnabled">检查划词功能状态</button>
</template>

<script setup>
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"

  const aiBlueking = ref(null)

  const showAgentInfo = () => {
    const info = aiBlueking.value?.agentInfo
    console.log('智能体名称:', info?.agentName)
    console.log('开场白:', info?.openingRemark)
    console.log('预设问题:', info?.predefinedQuestions)
    console.log('快捷指令:', info?.commands)
    console.log('会话配置:', info?.conversationSettings)
  }

  const checkPopupEnabled = () => {
    const info = aiBlueking.value?.agentInfo
    const enableWordSelectionPopup = info?.conversationSettings?.enableWordSelectionPopup
    console.log('划词弹窗是否启用:', enableWordSelectionPopup !== false)
  }
</script>
```

**`agentInfo` 包含的主要字段**：

- `agentName`: 智能体名称
- `openingRemark`: 开场白文本
- `predefinedQuestions`: 预设问题列表
- `commands`: 快捷指令配置列表
- `conversationSettings`: 会话相关配置
  - `enableChatSession`: 是否启用多会话功能
  - `enableWordSelectionPopup`: 是否启用划词弹窗（v1.3.2 新增）

**使用场景**：
- **动态UI调整**：根据智能体配置动态显示或隐藏界面元素
- **功能开关控制**：根据智能体的会话配置启用或禁用特定功能
- **状态展示**：在外部组件中展示智能体的相关信息
- **调试和监控**：便于开发和调试时查看智能体的完整配置

## 编程式会话管理

v1.2.2版本新增了编程式会话管理功能，允许通过组件实例方法创建、重命名和切换会话：

### 相关属性

- `initialSessionCode`: 指定初始化时加载的会话代码
- `autoSwitchToInitialSession`: 控制是否自动切换到初始会话

### 相关方法

- `addNewSession()`: 创建新会话
- `updateSessionName(sessionCode, newName)`: 重命名会话
- `switchToSession(sessionCode)`: 切换到指定会话

详细使用方法请参见 [会话生命周期管理指南](/guide/advanced-usage/session-lifecycle)。
