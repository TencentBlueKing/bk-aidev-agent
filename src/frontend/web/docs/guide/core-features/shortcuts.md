# 快捷操作

快捷操作是 AI 小鲸的核心功能之一，可以帮助用户快速执行常见任务，提高使用效率。v1.1.0 版本对快捷操作进行了重大升级，引入了自定义表单能力，使交互更加灵活和强大。

## 快捷操作的新特性

新版快捷操作支持：

1. **自定义表单输入**：不再局限于预设提示词，可以通过表单收集用户输入
2. **多种组件类型**：支持文本输入框、下拉选择框、数字输入框和多行文本域等多种组件类型
3. **自动填充选中文本**：可以智能地将用户选中的文本填充到指定表单项中
4. **正则表达式匹配**：支持使用正则表达式匹配选中文本的特定部分
5. **后端处理逻辑**：表单数据不再拼接为前端prompt，而是作为结构化数据发送到后端处理

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
    id: 'explain',
    name: '解释代码',
    icon: 'bkai-code',
    components: [
      {
        type: 'textarea',
        key: 'code',
        label: '代码内容',
        fillBack: true,
        placeholder: '请输入或选中需要解释的代码',
        rows: 5
      }
    ]
  }
];
</script>
```

### 处理快捷操作事件

```vue
<template>
  <AIBlueking 
    :shortcuts="shortcuts" 
    @shortcut-click="handleShortcutClick" 
  />
</template>

<script setup>
const handleShortcutClick = (data) => {
  console.log('执行了快捷操作:', data.shortcut.name);
  console.log('表单数据:', data.formData);
};
</script>
```

## 快捷操作配置详解

### IShortcut 接口

快捷操作配置对象的完整接口定义：

```typescript
interface IShortcut {
  id: string;       // 快捷操作的唯一标识符
  name: string;     // 显示的操作名称
  icon?: string;    // 按钮图标的类名
  components: Array<{
    type: string;    // 组件类型
    name?: string;   // 表单项名称
    key: string;     // 表单项键名
    placeholder?: string; // 占位文本
    default?: any;   // 默认值
    required?: boolean;   // 是否必填
    fillBack?: boolean;   // 是否自动填充选中文本
    fillRegx?: string | RegExp;    // 填充的正则匹配表达式
    rows?: number;        // 输入框行数（仅 textarea 类型有效）
    min?: number;         // 最小值（仅 number 类型有效）
    max?: number;         // 最大值（仅 number 类型有效）
    options?: Array<{     // 下拉选项（仅 select 类型有效）
      label: string;
      value: string | number;
    }>;
  }>
}
```

### 支持的组件类型

目前支持以下组件类型：

| 类型 | 描述 | 特有属性 |
| ---- | ---- | ------- |
| `text` | 单行文本输入框 | - |
| `textarea` | 多行文本输入框 | `rows`：文本框行数，默认为 3 |
| `number` | 数字输入框 | `min`, `max`：数值范围限制 |
| `select` | 下拉选择框 | `options`：选项列表 |

## 高级用法

### 组合多种表单组件

```javascript
{
  id: 'translate',
  name: '翻译',
  icon: 'bkai-translate',
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
  icon: 'bkai-bug',
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

### 配置数字输入

```javascript
{
  id: 'generate_code',
  name: '生成代码',
  icon: 'bkai-code',
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
      context: [
        { key: 'language', value: 'typescript' }
      ]
    }"
  />
</template>
```

## 最佳实践

1. **简洁明了的名称**：为快捷操作设置简洁、明确的名称，让用户一目了然
2. **合理设置表单项**：只收集必要的信息，避免过多的表单项影响用户体验
3. **设置合理的默认值**：为常用选项设置合理的默认值，减少用户操作
4. **使用图标增强辨识度**：为快捷操作配置直观的图标，提高用户识别速度
5. **利用自动填充功能**：合理使用 `fillBack` 和 `fillRegx` 属性，减少用户输入
6. **配置必填字段**：使用 `required` 属性标记必填字段，确保收集到必要信息
7. **与后端协调**：确保前端配置的快捷操作ID和表单项与后端处理逻辑一致 