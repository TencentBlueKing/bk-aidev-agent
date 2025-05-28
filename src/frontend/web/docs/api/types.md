# 类型定义

本文档列出了 AI 小鲸组件使用的主要类型定义。

## IShortcut

快捷操作对象定义，用于配置 `shortcuts` 属性。

```typescript
interface IShortcut {
  id: string;       // 快捷操作的唯一标识符
  name: string;     // 显示的操作名称
  icon?: string;    // 按钮图标的类名
  // 组件配置，用于定义表单项
  components: Array<{
    type: string;    // 组件类型：'input', 'select', 'number', 'textarea' 等
    name?: string;   // 表单项名称（推荐使用，与 label 相同功能）
    key: string;     // 表单项键名
    placeholder?: string; // 占位文本
    default?: any;   // 默认值
    required?: boolean;   // 是否必填
    fillBack?: boolean;   // 是否自动填充选中文本
    fillRegx?: string | RegExp; // 填充的正则匹配表达式
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

### 组件类型

| 类型 | 描述 | 特有属性 |
| ---- | ---- | ------- |
| `text` | 单行文本输入框 | - |
| `textarea` | 多行文本输入框 | `rows`：文本框行数，默认为 3 |
| `number` | 数字输入框 | `min`, `max`：数值范围限制 |
| `select` | 下拉选择框 | `options`：选项列表 |

### 后端数据格式

当用户点击快捷操作按钮并提交表单后，组件会将表单数据发送到后端。**注意：v1.1.0版本不再使用前端拼接prompt的方式，改为将表单数据作为上下文发送到后端，这需要后端进行适配**。

```javascript
// 后端接收到的数据结构示例
{
  // ... 其他参数
  "property": {
    "extra": {
      "command": "translate", // 快捷操作ID，对应 IShortcut 的 id
      "context": [
        { "key": "text", "value": "这是需要翻译的文本" },
        { "key": "targetLang", "value": "en" },
        // 其他表单项...
      ]
    }
  }
}
```

后端需要根据 `command` 和 `context` 字段来处理对应的快捷操作。

## Message

消息对象定义，用于 `defaultMessages` 属性和会话内容。

```typescript
interface Message {
  role: 'user' | 'assistant';  // 消息发送者角色
  content: string;            // 消息内容
  cite?: string;              // (可选) 框选引用内容，用于预设引用的文本
}
```

## ISession

会话对象定义，用于内部会话管理。

```typescript
interface ISession {
  sessionCode: string;   // 会话唯一标识
  sessionName: string;   // 会话名称
  sessionDesc?: string;  // 会话描述
}
```

## RequestOptions

请求选项对象定义，用于 `requestOptions` 属性。

```typescript
interface IRequestOptions {
  headers?: Record<string, any>; // 请求头参数
  data?: Record<string, any>;    // 请求体附加数据
  context?: Array<Record<string, any>>; // 上下文参数数据，会合并到快捷操作的context中
}
``` 