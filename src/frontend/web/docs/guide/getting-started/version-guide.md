# 版本升级指南

本指南提供了各版本间的主要变化和迁移方法，帮助您顺利升级 AI 小鲸组件。

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
    label: '解释',
    key: 'explanation',
    prompt: '请解释以下内容：\n{{ SELECTED_TEXT }}',
    icon: 'icon-help'
  }
]
```

**新版格式:**

```javascript
const shortcuts = [
  {
    id: 'explanation', // 原 key 改为 id
    name: '解释',      // 原 label 改为 name
    icon: 'bkai-help', // 图标前缀由 icon- 变为 bkai-
    components: [      // 新增 components 数组
      {
        type: 'input',
        key: 'text',
        label: '内容',
        fillBack: true, // 自动填充选中文本
        placeholder: '请输入或选中需要解释的内容'
      }
    ]
  }
]
```

#### 2. 更新事件处理

**旧版处理方式:**

```javascript
const handleShortcutClick = (shortcut) => {
  console.log('操作:', shortcut.label);
  console.log('提示词:', shortcut.prompt);
}
```

**新版处理方式:**

```javascript
const handleShortcutClick = (data) => {
  console.log('操作:', data.shortcut.name);
  console.log('表单数据:', data.formData);
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
<AIBlueking
  :default-top="50"
  :draggable="true"
/>
```

## v0.5.4 更新指南

v0.5.4 版本增强了组件的可拖拽功能和初始位置设置能力。

### 主要变更

- 新增 `draggable` 属性，控制组件是否可拖拽
- 新增 `defaultWidth`、`defaultHeight`、`defaultTop`、`defaultLeft` 属性，用于设置组件初始位置和大小

### 使用示例

```html
<AIBlueking
  :draggable="false"
  :default-width="600"
  :default-height="400"
  :default-top="100"
  :default-left="200"
/>
``` 