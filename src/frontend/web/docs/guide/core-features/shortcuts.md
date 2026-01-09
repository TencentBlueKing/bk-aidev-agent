# 快捷操作

快捷操作是 AI 小鲸的核心功能之一，可以帮助用户快速执行常见任务，提高使用效率。v1.1.0 版本对快捷操作进行了重大升级，引入了自定义表单能力，使交互更加灵活和强大。

## 快捷操作的新特性

新版快捷操作支持：

1. **自定义表单输入**：不再局限于预设提示词，可以通过表单收集用户输入
2. **多种组件类型**：支持文本输入框、下拉选择框、数字输入框和多行文本域等多种组件类型
3. **自动填充选中文本**：可以智能地将用户选中的文本填充到指定表单项中
4. **正则表达式匹配**：支持使用正则表达式匹配选中文本的特定部分 <Badge type="tip" text="v1.3.2 增强" />
5. **别名显示**：支持为快捷指令设置显示别名，提供更灵活的展示方式 <Badge type="tip" text="v1.3.2" />
6. **细粒度显示控制**：支持控制快捷指令在划词弹窗中的显示 <Badge type="tip" text="v1.3.2" />
7. **后端处理逻辑**：表单数据不再拼接为前端prompt，而是作为结构化数据发送到后端处理

## 重要提示：后端适配要求

**v1.1.0 版本要求后端必须进行适配**，才能正常使用快捷操作功能：

1. 快捷操作不再使用前端拼接 prompt 的方式处理
2. 表单数据以结构化的方式直接发送到后端
3. 后端需要处理 `command` 和 `context` 字段，生成适当的响应

如果您的后端尚未适配，请先与后端开发人员沟通，确保后端能够处理新的数据结构。

## 基础使用

### 配置快捷操作

```vue
<template>
  <AIBlueking :shortcuts="shortcuts" />
</template>

<script setup>
  const shortcuts = [
    {
      id: "explain",
      name: "解释代码",
      icon: "bkai-icon bkai-code",
      components: [
        {
          type: "textarea",
          key: "code",
          label: "代码内容",
          fillBack: true,
          placeholder: "请输入或选中需要解释的代码",
          rows: 5,
        },
      ],
    },
  ]
</script>
```

### 处理快捷操作事件

```vue
<template>
  <AIBlueking :shortcuts="shortcuts" @shortcut-click="handleShortcutClick" />
</template>

<script setup>
  const handleShortcutClick = (data) => {
    console.log("执行了快捷操作:", data.shortcut.name)
    console.log("表单数据:", data.formData)
  }
</script>
```

## 快捷操作配置详解

### IShortcut 接口

快捷操作配置对象的完整接口定义：

```typescript
interface IShortcut {
  id: string // 快捷操作的唯一标识符
  name: string // 显示的操作名称
  alias?: string // <Badge type="tip" text="v1.3.2" /> 显示别名，优先于 name 显示
  icon?: string // 按钮图标的完整类名（如：'bkai-icon bkai-translate'）
  enableFillBack?: boolean // <Badge type="tip" text="v1.3.2" /> 是否在划词弹窗中显示
  components: Array<{
    type: string // 组件类型
    name?: string // 表单项名称
    key: string // 表单项键名
    placeholder?: string // 占位文本
    default?: any // 默认值
    required?: boolean // 是否必填
    fillBack?: boolean // <Badge type="tip" text="v1.3.2 增强" /> 是否将选中文本填充到该组件
    fillRegx?: string | RegExp // <Badge type="tip" text="v1.3.2" /> 用于从选中文本提取的正则表达式
    rows?: number // 输入框行数（仅 textarea 类型有效）
    min?: number // 最小值（仅 number 类型有效）
    max?: number // 最大值（仅 number 类型有效）
    options?: Array<{
      // 下拉选项（仅 select 类型有效）
      label: string
      value: string | number
    }>
    hide?: boolean // 是否隐藏该组件 <Badge type="tip" text="v1.2.4-beta.3" />
  }>
}
```

### hide 属性 <Badge type="tip" text="v1.2.4-beta.3" />

`hide` 属性允许开发者动态控制快捷操作表单中特定组件的显示/隐藏。当设置为 `true` 时，该组件将不会在表单中显示，同时其数据也不会包含在提交的表单数据中。

这在以下场景中特别有用：
1. 根据条件动态显示/隐藏表单字段
2. 在不同上下文中复用相同的快捷操作配置
3. 实现更复杂的表单交互逻辑

## 快捷操作优化 <Badge type="tip" text="v1.2.5" />

v1.2.5 版本对快捷操作功能进行了重要的架构优化和用户体验提升：

### 架构优化

- **组件简化**：移除了 `ai-selected-box` 组件，简化了快捷操作的整体架构
- **事件处理优化**：重新设计了快捷操作点击事件的处理逻辑，提升了响应性能和稳定性
- **过滤器增强**：优化了 `shortcutFilter` 函数的实现，增强了快捷操作的灵活性和可定制性

### 新特性

- **更强的类型支持**：改进了 TypeScript 类型定义，提供了更好的开发体验
- **性能提升**：通过组件轻量化和事件处理优化，提升了整体性能表现
- **更好的错误处理**：增强了错误捕获和处理机制，提供了更稳定的用户体验

### 向后兼容

所有现有快捷操作配置在 v1.2.5 版本中仍然完全兼容，无需进行任何修改。优化主要针对内部实现，对外部 API 保持完全一致。

### 使用建议

```vue
<template>
  <AIBlueking
    :shortcuts="enhancedShortcuts"
    :shortcut-filter="smartFilter"
    @shortcut-click="handleShortcutClick"
  />
</template>

<script setup>
const enhancedShortcuts = [
  {
    id: 'smart_operation',
    name: '智能操作',
    icon: 'bkai-icon bkai-ai',
    components: [
      {
        type: 'textarea',
        key: 'content',
        name: '内容',
        fillBack: true,
        placeholder: '请输入或选择内容',
        // v1.2.5 优化后的 hide 属性支持更灵活的控制
        hide: false
      }
    ]
  }
]

// v1.2.5 优化后的过滤器性能更好
const smartFilter = (shortcut, selectedText) => {
  // 更智能的过滤逻辑
  if (shortcut.id === 'code_analysis') {
    return selectedText.includes('function') || selectedText.includes('const')
  }
  return true
}
</script>
```

```javascript
{
  id: 'dynamic_form',
  name: '动态表单',
  icon: 'bkai-icon bkai-form',
  components: [
    {
      type: 'select',
      key: 'userType',
      name: '用户类型',
      options: [
        { label: '普通用户', value: 'normal' },
        { label: 'VIP用户', value: 'vip' }
      ],
      placeholder: '请选择用户类型'
    },
    {
      type: 'input',
      key: 'vipCode',
      name: 'VIP码',
      placeholder: '请输入VIP码',
      // 只有当用户类型为VIP时才显示此字段
      hide: false // 初始可见，可通过程序动态控制
    }
  ]
}
```

## 快捷指令增强功能 <Badge type="tip" text="v1.3.2" />

v1.3.2 版本对快捷指令功能进行了重要增强，新增了别名显示、精准文本填充和细粒度显示控制等特性：

### 别名显示

快捷指令新增 `alias` 字段，用于显示与原始名称不同的别名。当设置了别名后，在所有展示位置（快捷栏、弹窗、表单等）会优先显示别名：

```javascript
const shortcuts = [
  {
    id: 'translate',
    name: '翻译',  // 内部标识名称
    alias: '智能翻译',  // 用户看到的名称
    icon: 'bkai-icon bkai-translate',
    // ... 其他配置
  },
  {
    id: 'extract_email',
    name: '提取邮箱',
    alias: '邮箱提取器',  // 更友好的显示名称
    icon: 'bkai-icon bkai-email',
    // ... 其他配置
  }
]
```

**使用场景**：
- 为技术性名称提供更用户友好的显示文本
- 在不同语言环境下显示本地化名称
- 保持内部标识稳定的同时调整外部显示

### 精准文本填充 - fillRegx

组件级别新增 `fillRegx` 字段，支持使用正则表达式从选中文本中提取特定内容：

```javascript
{
  id: 'extract_url',
  name: '分析链接',
  alias: 'URL分析器',
  icon: 'bkai-icon bkai-link',
  enableFillBack: true,
  components: [
    {
      type: 'textarea',
      key: 'url',
      name: 'URL地址',
      fillBack: true,
      // 只提取 URL 部分
      fillRegx: 'https?://[^\\s]+',
      placeholder: '自动提取选中文本中的URL'
    }
  ]
}
```

**更多示例**：

```javascript
// 提取邮箱地址
{
  type: 'input',
  key: 'email',
  name: '邮箱',
  fillBack: true,
  fillRegx: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
}

// 提取代码块
{
  type: 'textarea',
  key: 'code',
  name: '代码',
  fillBack: true,
  fillRegx: '```[\\s\\S]*?```|`[^`]+`'  // 提取 markdown 代码块或行内代码
}

// 提取数字
{
  type: 'number',
  key: 'amount',
  name: '金额',
  fillBack: true,
  fillRegx: '\\d+(?:\\.\\d+)?'  // 提取整数或小数
}
```

### 划词弹窗显示控制

快捷指令级别新增 `enableFillBack` 字段，支持控制快捷指令是否在划词弹窗中显示：

```javascript
const shortcuts = [
  {
    id: 'simple_translate',
    name: '翻译',
    icon: 'bkai-icon bkai-translate',
    enableFillBack: true,  // 在划词弹窗中显示
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '文本',
        fillBack: true
      }
    ]
  },
  {
    id: 'complex_analysis',
    name: '深度分析',
    icon: 'bkai-icon bkai-analysis',
    enableFillBack: false,  // 不在划词弹窗中显示，仅在主菜单显示
    components: [
      // ... 复杂的表单配置
    ]
  }
]
```

**使用场景**：
- 简单快捷的操作显示在划词弹窗中
- 复杂的多步骤操作仅在主菜单中显示
- 根据场景区分快速操作和完整操作

### 组合使用示例

```javascript
const shortcuts = [
  {
    id: 'smart_translate',
    name: '翻译',
    alias: '智能翻译助手',  // 友好的显示名称
    icon: 'bkai-icon bkai-translate',
    enableFillBack: true,  // 在划词弹窗中显示
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '待翻译文本',
        fillBack: true,
        fillRegx: '[^\\d\\s]+',  // 只提取非数字和非空白字符
        placeholder: '自动填充选中的文本'
      },
      {
        type: 'select',
        key: 'targetLang',
        name: '目标语言',
        options: [
          { label: '英文', value: 'en' },
          { label: '中文', value: 'zh' }
        ]
      }
    ]
  },
  {
    id: 'extract_contact',
    name: '提取联系方式',
    alias: '联系信息提取器',
    icon: 'bkai-icon bkai-contact',
    enableFillBack: true,
    components: [
      {
        type: 'input',
        key: 'phone',
        name: '电话',
        fillBack: true,
        fillRegx: '1[3-9]\\d{9}',  // 提取手机号
        placeholder: '提取手机号码'
      },
      {
        type: 'input',
        key: 'email',
        name: '邮箱',
        fillBack: true,
        fillRegx: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}',  // 提取邮箱
        placeholder: '提取邮箱地址'
      }
    ]
  }
]
```

### 最佳实践

1. **合理使用别名**：为用户提供清晰易懂的快捷指令名称
2. **精确的正则表达式**：使用适当的正则表达式确保提取的内容准确
3. **划词弹窗显示策略**：
   - 简单、单步操作 → `enableFillBack: true`
   - 复杂、多步操作 → `enableFillBack: false`
4. **测试正则表达式**：在实际使用前充分测试正则表达式的匹配效果
5. **提供回退机制**：即使正则匹配失败，也应确保表单可以正常使用

### 支持的组件类型

目前支持以下组件类型：

| 类型       | 描述           | 特有属性                     |
| ---------- | -------------- | ---------------------------- |
| `text`     | 单行文本输入框 | -                            |
| `textarea` | 多行文本输入框 | `rows`：文本框行数，默认为 3 |
| `number`   | 数字输入框     | `min`, `max`：数值范围限制   |
| `select`   | 下拉选择框     | `options`：选项列表          |

## 高级用法

### 组合多种表单组件

```javascript
{
  id: 'translate',
  name: '翻译',
  icon: 'bkai-icon bkai-translate',
  components: [
    {
      type: 'textarea',
      key: 'text',
      name: '待翻译文本',
      fillBack: true,
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
    },
    {
      type: 'select',
      key: 'style',
      name: '翻译风格',
      options: [
        { label: '标准', value: 'standard' },
        { label: '正式', value: 'formal' },
        { label: '口语化', value: 'casual' }
      ],
      placeholder: '请选择翻译风格'
    }
  ]
}
```

### 使用正则表达式匹配选中文本

```javascript
{
  id: 'analyze_error',
  name: '分析错误',
  icon: 'bkai-icon bkai-bug',
  components: [
    {
      type: 'textarea',
      key: 'error_message',
      label: '错误信息',
      fillBack: true,
      fillRegx: /Error:(.+)/,  // 使用正则表达式对象
      placeholder: '请输入或选中错误信息'
    },
    {
      type: 'input',
      key: 'context',
      label: '上下文信息',
      placeholder: '请提供发生错误的上下文'
    }
  ]
}
```

### 控制快捷指令弹窗

在某些情况下，您可能不希望在页面的特定区域选中文字时弹出快捷指令窗口。例如，在一个代码编辑器或者一个具有复杂交互的表格中，这个弹窗可能会干扰正常操作。

AI 小鲸提供了一个简单的方法来禁用特定区域的弹窗功能。您只需要在不希望弹出快捷指令的任何 HTML 元素上添加 `ai-blueking-hide` 属性即可。

```html
<div ai-blueking-hide>
  <p>在这部分区域内选中文本，将不会触发 AI 小鲸的快捷指令弹窗。</p>
  <code> // 这里是代码区域，同样不会触发弹窗 const x = 10; console.log(x); </code>
</div>
```

当您在带有 `ai-blueking-hide` 属性的元素或其任何子元素中选择文本时，快捷指令弹窗将不会出现。这为您提供了精细的控制能力，确保 AI 小鲸的交互不会干扰您应用中的其他功能。

#### 工作原理

AI 小鲸在响应文本选择事件时，会从被选中的文本所在的元素开始，向上遍历DOM树。如果在这个遍历过程中发现了任何一个元素带有 `ai-blueking-hide` 属性，它就会停止处理，从而阻止了弹窗的显示。

这个特性对于提升与现有复杂前端应用的集成体验非常有用。更多关于内容引用的信息，请参考[内容引用](./content-referencing.md)文档。

### 配置数字输入

```javascript
{
  id: 'generate_code',
  name: '生成代码',
  icon: 'bkai-icon bkai-code',
  components: [
    {
      type: 'input',
      key: 'description',
      label: '描述',
      placeholder: '请描述需要生成的代码功能'
    },
    {
      type: 'number',
      key: 'lines',
      label: '代码行数',
      default: 20,
      min: 5,
      max: 100,
      required: true
    }
  ]
}
```

## 服务端处理

当用户点击快捷操作按钮并提交表单后，表单数据会作为 `context` 参数发送到服务端。后端可以根据这些数据提供更加定制化的响应。

```javascript
// 后端接收到的数据结构示例
{
  "property": {
    "extra": {
      "command": "translate", // 快捷操作ID
      "context": [
        { "key": "text", "value": "这是需要翻译的文本" },
        { "key": "targetLang", "value": "en" },
        { "key": "style", "value": "formal" }
      ]
    }
  }
}
```

> **重要：** 后端需要通过 `command` 识别快捷操作类型，并从 `context` 中获取表单数据进行处理。不再依赖前端拼接的 `prompt` 字符串。

## 与RequestOptions结合使用

您可以通过组件的 `requestOptions` 属性传递额外的上下文数据，这些数据会与快捷操作的表单数据合并：

```vue
<template>
  <AIBlueking
    :shortcuts="shortcuts"
    :request-options="{
      context: [{ key: 'language', value: 'typescript' }],
    }"
  />
</template>
```

## 快捷操作增强 (v1.2.4-beta.2)

v1.2.4-beta.2版本进一步增强了快捷操作的灵活性和用户体验，新增了以下功能：

### 自动提交

对于通过文本选中后弹出的快捷操作（`enablePopup: true`），现在支持自动提交。如果一个快捷指令只有一个表单项，并且该表单项通过 `fillBack: true` 自动填充了内容，那么该操作将自动执行，无需用户再次点击提交按钮。这大大简化了常见的单步操作，如“翻译”或“解释代码”。

### 显示数量限制

新增 `shortcutLimit` 属性，可以控制在弹出窗口中显示的快捷操作数量。当快捷操作较多时，可以避免列表过长。

```vue
<template>
  <AIBlueking :shortcuts="shortcuts" :shortcut-limit="3" />
</template>
```

### 动态过滤

新增 `shortcutFilter` 属性，它是一个函数，可以用来动态地过滤要显示的快捷操作。这个函数会在每次弹出快捷操作菜单时执行。

函数签名：`(shortcut: IShortcut, selectedText: string) => boolean`

当用户选中了页面上的文本时，每个快捷操作的组件（components）会自动获得一个 `selectedText` 属性，其中包含当前选中的文本内容。这使得您可以根据选中的文本内容来过滤快捷操作。

```vue
<template>
  <AIBlueking :shortcuts="shortcuts" :shortcut-filter="myFilter" />
</template>

<script setup>
  const myFilter = (shortcut, selectedText) => {
    // 只显示ID为 'translate' 或 'explain' 的快捷操作
    if (!["translate", "explain"].includes(shortcut.id)) {
      return false
    }

    // 如果选中的文本包含代码特征，只显示"解释代码"快捷操作
    if (shortcut.id === "explain" && selectedText?.includes("function")) {
      return true
    }

    // 对于翻译操作，只有当选中的文本长度在合理范围内时才显示
    if (shortcut.id === "translate" && selectedText && selectedText.length > 0 && selectedText.length < 1000) {
      return true
    }

    return false
  }
</script>
```

这些增强功能使快捷操作的管理更加强大和灵活，能够适应更多复杂的应用场景。

## 最佳实践

1. **简洁明了的名称**：为快捷操作设置简洁、明确的名称，让用户一目了然
2. **合理设置表单项**：只收集必要的信息，避免过多的表单项影响用户体验
3. **设置合理的默认值**：为常用选项设置合理的默认值，减少用户操作
4. **使用图标增强辨识度**：为快捷操作配置直观的图标，提高用户识别速度
5. **利用自动填充功能**：合理使用 `fillBack` 和 `fillRegx` 属性，减少用户输入
6. **配置必填字段**：使用 `required` 属性标记必填字段，确保收集到必要信息
7. **与后端协调**：确保前端配置的快捷操作ID和表单项与后端处理逻辑一致
