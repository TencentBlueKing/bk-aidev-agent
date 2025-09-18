# 版本升级指南

本指南提供了各版本间的主要变化和迁移方法，帮助您顺利升级 AI 小鲸组件。

## v1.2.6 更新指南 <Badge type="tip" text="最新" />

v1.2.6 版本主要增强了群聊转人工功能，新增了编程式引用文本设置能力，并优化了相关代码逻辑。

### 主要变更

1. **群聊咨询用户名支持**：在选择模式中新增 `username` 字段，用于群聊转人工时显示咨询用户名称
2. **动态群聊名称生成**：聊天群名称现在根据智能体名称、会话名称和用户名动态生成，格式为：`智能体名称-会话名称-咨询用户`
3. **编程式引用文本设置**：新增 `setCiteText` 方法，支持动态设置输入框中的引用文本
4. **依赖升级**：升级 @blueking/ai-ui-sdk 到 0.1.16-beta.4，获取更多底层能力支持
5. **代码优化**：优化选择模式逻辑，移除不必要的依赖，提升代码可维护性

### 新增功能

#### 1. 编程式设置引用文本

v1.2.6 版本新增了 `setCiteText` 方法，允许通过编程方式动态设置输入框中的引用文本：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="addCiteText">添加引用文本</button>
</template>

<script setup>
  const aiBlueking = ref(null)

  const addCiteText = () => {
    // 动态添加引用文本到输入框
    aiBlueking.value?.setCiteText("这是要引用的文本内容")
  }
</script>
```

此功能特别适用于：

- **动态内容引用**：根据用户操作动态添加引用内容
- **外部系统集成**：从其他系统获取数据并设置为引用文本
- **自定义快捷操作**：在快捷操作中自动填充引用内容

#### 2. 群聊咨询用户信息支持

新增了群聊咨询用户名支持，在转人工操作时会自动包含咨询用户的信息：

```typescript
// 聊天群名称格式：智能体名称-会话名称-咨询用户
// 例如：小鲸助手-产品咨询-张三
```

### API 更新

#### 新增方法

- `setCiteText(citeText: string): void` - 编程式设置输入框中的引用文本

#### 数据结构更新

- `chatGroup` 配置新增 `username` 字段，用于存储咨询用户的用户名

### 升级注意事项

1. **向后兼容**：所有现有功能完全兼容，无需修改现有代码
2. **依赖版本**：@blueking/ai-ui-sdk 已升级到 0.1.16-beta.4，请确保相关依赖版本匹配
3. **新功能可选**：新增功能均为可选特性，不会影响现有功能的正常使用

### 升级步骤

1. 更新依赖包到 v1.2.6 版本
2. （可选）根据需要使用 `setCiteText` 方法进行编程式引用文本设置
3. （可选）在群聊转人工场景中配置和使用 `username` 字段
4. 测试所有现有功能确保兼容性

## v1.2.5 更新指南

v1.2.5 版本重点优化了快捷操作体验，增强了会话管理功能，改进了权限和错误处理机制，并提升了开发体验。

### 主要变更

1. **快捷操作优化**：移除 `ai-selected-box` 组件，简化快捷操作事件处理，提升响应性能
2. **会话初始化增强**：新增 `loadRecentSessionOnMount` 属性，支持自动加载最近会话
3. **权限处理完善**：新增 403 错误页面支持，完善无权限访问处理
4. **开发体验提升**：重构 ESLint 配置，新增 tsconfig.build.json，优化 TypeScript 构建流程
5. **依赖升级**：升级 @blueking/ai-ui-sdk 到 0.1.16-beta.3，获取更多底层能力
6. **环境配置简化**：移除开发环境配置中的 `BK_API_URL_TMPL` 和 `BKUI_PREFIX` 变量

### 新增功能

#### 1. 最近会话自动加载

v1.2.5 版本引入了 `loadRecentSessionOnMount` 属性，实现组件挂载时自动加载最近会话：

```vue
<template>
  <AIBlueking :load-recent-session-on-mount="true" :url="apiUrl" />
</template>
```

此功能特别适用于：

- **用户回访**：自动恢复到上次的会话
- **页面刷新**：快速恢复到之前的对话状态
- **多标签页**：在不同标签页间保持会话连续性

#### 2. 会话内容状态管理

新增 `hasSessionContents` 属性，用于控制会话内容状态的显示：

```vue
<template>
  <AIBlueking :has-session-contents="hasContents" :url="apiUrl" />
</template>

<script setup>
  import { computed } from "vue"

  const hasContents = computed(() => sessionContents.value.length > 0)
</script>
```

#### 3. 选择模式功能

v1.2.5 版本新增了消息选择模式，支持消息的批量选择和操作：

```vue
<script setup>
  const aiBlueking = ref(null)

  // 进入选择模式
  const enterSelectMode = () => {
    aiBlueking.value?.enterSelectMode("transfer")
  }

  // 获取选中的消息
  const getSelectedMessages = () => {
    return aiBlueking.value?.getSelectedMessages()
  }
</script>
```

### 开发环境变更

#### 环境配置简化

v1.2.5 版本移除了开发环境配置中的 `BK_API_URL_TMPL` 和 `BKUI_PREFIX` 变量：

```bash
# 旧版本可能需要的环境变量（现在已移除）
# BK_API_URL_TMPL=http://localhost:8080/api
# BKUI_PREFIX=bk

# 新版本只需基本配置
NODE_ENV=development
```

#### TypeScript 构建优化

新增 `tsconfig.build.json` 配置文件，优化了 TypeScript 构建流程，提供更好的类型检查和构建性能。

### 迁移注意事项

1. **环境配置更新**：检查并更新您的开发环境配置，移除 `BK_API_URL_TMPL` 和 `BKUI_PREFIX` 相关配置
2. **依赖兼容性**：@blueking/ai-ui-sdk 已升级到新版本，请确保后端服务兼容新的 SDK 版本
3. **快捷操作功能**：所有现有快捷操作配置完全兼容，无需修改
4. **会话管理**：`loadRecentSessionOnMount` 是可选功能，默认关闭以保持向后兼容

### 升级步骤

1. 更新依赖包到 v1.2.5 版本
2. 清理开发环境配置中的 `BK_API_URL_TMPL` 和 `BKUI_PREFIX` 变量
3. （可选）根据需求配置 `loadRecentSessionOnMount` 属性
4. （可选）利用新的选择模式功能和会话状态管理功能
5. 测试所有现有功能确保兼容性

## v1.1.6 更新指南

v1.1.6 版本专注于提升用户体验和稳定性，引入了增强的 Markdown 渲染支持和多实例优化。

### 主要变更

1. **Markdown 渲染增强**：新增完整的 Markdown 样式支持
2. **多实例支持**：重构 sessionStore 为实例化模式，避免多个组件实例间的状态冲突
3. **会话初始化优化**：改进初始化逻辑，避免重复初始化
4. **新增事件支持**：支持监听 `session-init` 事件获取会话初始化状态
5. **窗口高度响应式处理**：优化问候文本的最大高度计算

### 新增功能

#### 1. Markdown 渲染增强

从 v1.1.6 开始，组件提供了增强的 Markdown 渲染功能：

- 支持代码块语法高亮和行号显示
- 优化表格、列表、标题等元素的显示效果
- 支持图片响应式显示和链接点击
- 所有内容经过安全处理，防止 XSS 攻击

**无需额外配置**，Markdown 渲染功能开箱即用。

#### 2. 多实例支持

v1.1.6 版本通过重构 sessionStore 为实例化模式，解决了多个 AI 小鲸组件实例间的状态冲突问题：

```vue
<!-- 现在可以在同一页面安全使用多个实例 -->
<template>
  <div>
    <AIBlueking :url="apiUrl1" />
    <AIBlueking :url="apiUrl2" />
  </div>
</template>
```

#### 3. 会话初始化事件

新增 `session-init` 事件，可在会话初始化完成时获取会话ID：

```vue
<template>
  <AIBlueking :url="apiUrl" @session-init="onSessionInit" />
</template>

<script setup>
  const onSessionInit = (sessionId) => {
    console.log("会话初始化完成:", sessionId)
  }
</script>
```

### 升级注意事项

v1.1.6 是一个向后兼容的更新，不需要修改现有代码。所有新功能都是可选的增强特性。

## v1.1.0 更新指南

v1.1.0 版本引入了自定义表单输入功能，这是一个重大更新，对快捷操作接口进行了升级，同时改变了与后端的交互方式。

### 主要变更

1. 快捷操作接口由 `ShortCut` 更改为 `IShortcut`
2. 新增自定义表单输入功能，支持多种表单组件类型
3. `shortcut-click` 事件参数格式变更，现在包含用户填写的表单数据
4. **重要**：快捷操作不再使用前端拼接 prompt 的方式处理，改为将表单数据作为上下文直接发送到后端

### 后端适配要求

**v1.1.0 版本要求后端必须进行适配**，才能正常使用快捷操作功能：

1. 后端需要处理新的数据结构，从 `extra.command` 和 `extra.context` 字段获取操作信息
2. 不再依赖前端拼接的 prompt 字符串，需要后端自行根据 command 和表单数据生成适当的响应

```javascript
// 后端接收到的数据结构示例
{
  // ... 其他参数
  "property": {
    "extra": {
      "command": "translate",  // 快捷操作ID，对应IShortcut的id
      "context": [
        { "key": "text", "value": "需要翻译的文本" },
        { "key": "targetLang", "value": "en" }
        // ... 其他表单数据
      ]
    }
  }
}
```

### 升级步骤

#### 1. 更新快捷操作配置

**旧版格式:**

```javascript
const shortcuts = [
  {
    label: "解释",
    key: "explanation",
    prompt: "请解释以下内容：\n{{ SELECTED_TEXT }}",
    icon: "icon-help",
  },
]
```

**新版格式:**

```javascript
const shortcuts = [
  {
    id: "explanation", // 原 key 改为 id
    name: "解释", // 原 label 改为 name
    icon: "bkai-help", // 图标前缀由 icon- 变为 bkai-
    components: [
      // 新增 components 数组
      {
        type: "input",
        key: "text",
        label: "内容",
        fillBack: true, // 自动填充选中文本
        placeholder: "请输入或选中需要解释的内容",
      },
    ],
  },
]
```

#### 2. 更新事件处理

**旧版处理方式:**

```javascript
const handleShortcutClick = (shortcut) => {
  console.log("操作:", shortcut.label)
  console.log("提示词:", shortcut.prompt)
}
```

**新版处理方式:**

```javascript
const handleShortcutClick = (data) => {
  console.log("操作:", data.shortcut.name)
  console.log("表单数据:", data.formData)
  // formData 示例: [{ key: 'text', value: '选中的文本内容' }]
}
```

### 向下兼容

为了确保平滑过渡，v1.1.0 版本可能提供了有限的向下兼容支持：

- 如果您仍使用旧的 `ShortCut` 格式，组件会尝试将其转换为新的 `IShortcut` 格式
- 旧版的 `prompt` 字段可能会被转换为一个自动填充的 input 组件

然而，**由于后端交互方式的变化，即使前端兼容了旧格式，后端仍需要适配新的数据结构**，否则功能将无法正常使用。因此，我们强烈建议您同时更新前端和后端代码，以确保功能正常。

## v0.5.6 更新指南

v0.5.6 版本主要修复了在加载状态下仍可发送消息的问题，这是一个小型修复更新，不需要特殊的升级步骤。

## v0.5.5 更新指南

v0.5.5 版本主要改进了组件的位置交互计算方式，修复了多个与位置和宽度计算相关的问题。

### 主要变更

- 改进组件定位算法，提高组件在各种场景下的定位精度
- 修复初始位置调整导致位置交互错位的问题
- 修复Vue2部分属性不生效的问题
- 修复组件默认宽度计算错误的问题

### 使用示例

```html
<AIBlueking :default-top="50" :draggable="true" />
```

## v0.5.4 更新指南

v0.5.4 版本增强了组件的可拖拽功能和初始位置设置能力。

### 主要变更

- 新增 `draggable` 属性，控制组件是否可拖拽
- 新增 `defaultWidth`、`defaultHeight`、`defaultTop`、`defaultLeft` 属性，用于设置组件初始位置和大小

### 使用示例

```html
<AIBlueking :draggable="false" :default-width="600" :default-height="400" :default-top="100" :default-left="200" />
```
