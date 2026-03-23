# 快捷指令

::: warning 重要：快捷指令由 AIDev 后台配置
标准流程中，快捷指令通过 `agent/info` 接口自动加载，**无需前端定义**。
前端 `shortcuts` prop 仅用于特殊场景下的覆盖或补充。
:::

快捷指令是 AI 小鲸的核心功能之一，允许用户通过预设的指令快速执行常见任务。v2.0 版本中，快捷操作由 [`ShortcutManager`](/guide/core-features/shortcuts#shortcutmanager) 统一管理，支持自定义表单、自动填充、正则匹配等能力。

## 默认行为（零配置）

当你在 AIDev 平台配置好 Agent 的快捷指令后，组件初始化时会自动完成：

1. 调用 `agent/info` 接口获取 Agent 配置
2. 从 `conversationSettings.commands` 字段中解析快捷指令列表
3. 自动渲染到欢迎页和对话窗口中

**无需在前端传入任何 `shortcuts` prop**，一切由后台配置驱动。

## 快捷指令数据结构

快捷指令通过 [`IShortcut`](/api/ai-blueking/types) 接口定义，扩展自 AG-UI SDK 的 `IAgentCommand`：

```typescript
interface IShortcut {
  // === 基础属性 ===
  id: string;                    // 唯一标识符
  name: string;                  // 指令名称
  alias?: string;                // 显示别名，优先于 name 显示
  icon?: string;                 // 图标类名（如 'bkai-icon bkai-translate'）
  iconRender?: (h) => VNode;     // 自定义 icon 渲染函数
  description?: string;          // 描述信息

  // === 表单配置 ===
  components: IShortcutComponent[];  // 表单组件列表
  formModel?: Record<string, any>;   // 表单数据模型

  // === 行为控制 ===
  mode?: 'simple' | 'advanced';       // 指令模式，默认 'advanced'
  enable_fill_back?: boolean;          // 是否启用自动回填
  fill_back_component_key?: string;    // 自动回填的目标字段 key
  hideFooter?: boolean;                // 是否隐藏底部按钮区域
  bindKey?: string;                    // 强制重新渲染的唯一键值
}
```

### IShortcutComponent 表单组件

```typescript
interface IShortcutComponent {
  type: string;               // 组件类型: 'input' | 'textarea' | 'select' | 'number' | 'checkbox'
  key: string;                // 表单项键名
  name?: string;              // 表单项名称/标签
  placeholder?: string;       // 占位文本
  default?: any;              // 默认值
  required?: boolean;         // 是否必填
  hide?: boolean;             // 是否隐藏
  fillBack?: boolean;         // 是否将选中文本填充到该组件
  fillRegx?: string | RegExp; // 从选中文本提取内容的正则表达式
  rows?: number;              // 文本框行数（仅 textarea 有效）
  min?: number;               // 最小值（仅 number 有效）
  max?: number;               // 最大值（仅 number 有效）
  options?: Array<{           // 选项列表（仅 select 有效）
    label: string;
    value: string | number;
  }>;
  // === v2.0 扩展 ===
  mode?: 'simple' | 'advanced';    // 单个组件展示模式
  selectedText?: string | null;    // 选中的文本内容
  showSendButton?: boolean;        // 是否显示发送按钮
}
```

## 前端覆盖（特殊场景）

::: details 何时需要前端传入 shortcuts？
仅在以下特殊场景中，才需要通过 `shortcuts` prop 传入快捷指令：
- 需要在前端**覆盖**后端配置的指令
- 需要**临时补充**额外的指令
- 开发/调试阶段，后端尚未配置指令

前端传入的 `shortcuts` 优先级高于接口返回值。
:::

通过 `shortcuts` prop 传入快捷指令列表：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="shortcuts"
    :shortcut-limit="5"
    @shortcut-click="handleShortcutClick"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';
import type { IShortcut } from '@blueking/ai-blueking';

const apiUrl = '/api/ai/assistant/';

const shortcuts: IShortcut[] = [
  {
    id: 'explain',
    name: '解释代码',
    icon: 'bkai-icon bkai-code',
    enable_fill_back: true,
    fill_back_component_key: 'code',
    components: [
      {
        type: 'textarea',
        key: 'code',
        name: '代码内容',
        fillBack: true,
        placeholder: '请输入或选中需要解释的代码',
        rows: 5,
      },
      {
        type: 'select',
        key: 'language',
        name: '编程语言',
        options: [
          { label: '自动检测', value: 'auto' },
          { label: 'Python', value: 'python' },
          { label: 'JavaScript', value: 'javascript' },
          { label: 'Go', value: 'go' },
        ],
        default: 'auto',
      },
    ],
  },
  {
    id: 'translate',
    name: '翻译',
    alias: '智能翻译',
    icon: 'bkai-icon bkai-translate',
    enable_fill_back: true,
    fill_back_component_key: 'text',
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '待翻译文本',
        fillBack: true,
        placeholder: '请输入或选中需要翻译的文本',
      },
      {
        type: 'select',
        key: 'targetLang',
        name: '目标语言',
        options: [
          { label: '中文', value: 'zh' },
          { label: '英文', value: 'en' },
          { label: '日文', value: 'jp' },
        ],
        default: 'en',
      },
    ],
  },
];

const handleShortcutClick = (data: { shortcut: IShortcut; source: 'main' | 'popup' }) => {
  console.log('执行快捷操作:', data.shortcut.name, '来源:', data.source);
};
</script>
```

## ShortcutManager

`ShortcutManager` 是 v2.0 新增的快捷指令管理器，负责快捷指令的筛选和选择逻辑。

### 快捷指令过滤

通过 `shortcutFilter` prop 自定义过滤逻辑：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="shortcuts"
    :shortcut-filter="customFilter"
  />
</template>

<script setup>
// 根据选中文本动态过滤快捷指令
const customFilter = (shortcut, selectedText) => {
  // 如果选中的文本包含代码特征，只显示代码相关快捷操作
  if (selectedText?.includes('function') || selectedText?.includes('const')) {
    return shortcut.id === 'explain' || shortcut.id === 'review';
  }
  return true;
};
</script>
```

## ShortcutRender 表单渲染

快捷指令的表单由 `ShortcutRender` 组件负责渲染。支持以下组件类型：

| 类型 | 描述 | 特有属性 |
|------|------|---------|
| `input` | 单行文本输入框 | — |
| `textarea` | 多行文本输入框 | `rows`（行数，默认 3） |
| `select` | 下拉选择框 | `options`（选项列表） |
| `number` | 数字输入框 | `min`、`max`（范围限制） |
| `checkbox` | 复选框 | — |

### simple 和 advanced 模式

快捷指令支持两种展示模式：

- **advanced 模式**（默认）：展示完整表单，包含标题栏（header）、表单区域和底部按钮（footer）
- **simple 模式**：直接展示表单组件，没有外层包装

```typescript
const simpleShortcut: IShortcut = {
  id: 'quick_ask',
  name: '快速提问',
  mode: 'simple',         // 简单模式
  hideFooter: true,        // 隐藏底部按钮
  components: [
    {
      type: 'textarea',
      key: 'question',
      mode: 'simple',     // 组件也使用简单模式（无 label）
      showSendButton: true, // 显示发送按钮
    },
  ],
};
```

## ShortcutBtns 快捷按钮

快捷按钮组显示在对话窗口中，用户可以点击快速发起操作。

### shortcutLimit

通过 `shortcutLimit` prop 控制显示数量：

```vue
<template>
  <!-- 最多显示 3 个快捷按钮 -->
  <AIBlueking :url="apiUrl" :shortcuts="shortcuts" :shortcut-limit="3" />
</template>
```

### shortcut-click 事件

当用户点击快捷操作按钮时触发，包含快捷指令对象和触发来源：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="shortcuts"
    @shortcut-click="handleClick"
  />
</template>

<script setup>
const handleClick = (data) => {
  console.log('指令:', data.shortcut.name);
  console.log('来源:', data.source);  // 'main'（主菜单）或 'popup'（划词弹窗）
};
</script>
```

## fillBack 自动回填机制

`fillBack` 机制允许将用户选中的文本自动回填到指定的表单字段中：

1. 用户在页面上选中一段文本
2. 划词弹窗展示快捷操作列表
3. 用户点击快捷操作
4. 组件查找 `fillBack: true` 的表单字段
5. 将选中文本填充到该字段的 `default` 值

### 结合 fillRegx 精准提取

`fillRegx` 允许使用正则表达式从选中文本中提取特定内容：

```typescript
const shortcuts: IShortcut[] = [
  {
    id: 'extract_url',
    name: 'URL 分析',
    enable_fill_back: true,
    fill_back_component_key: 'url',
    components: [
      {
        type: 'textarea',
        key: 'url',
        name: 'URL 地址',
        fillBack: true,
        fillRegx: 'https?://[^\\s]+',      // 只提取 URL 部分
        placeholder: '自动提取选中文本中的 URL',
      },
    ],
  },
  {
    id: 'extract_contact',
    name: '提取联系方式',
    enable_fill_back: true,
    components: [
      {
        type: 'input',
        key: 'phone',
        name: '电话',
        fillBack: true,
        fillRegx: '1[3-9]\\d{9}',         // 提取手机号
      },
      {
        type: 'input',
        key: 'email',
        name: '邮箱',
        fillBack: true,
        fillRegx: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}',  // 提取邮箱
      },
    ],
  },
];
```

## 代码示例：完整快捷指令配置

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="shortcuts"
    :shortcut-limit="5"
    :shortcut-filter="smartFilter"
    :enable-popup="true"
    @shortcut-click="onShortcutClick"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';
import type { IShortcut } from '@blueking/ai-blueking';

const apiUrl = '/api/ai/assistant/';

const shortcuts: IShortcut[] = [
  {
    id: 'code_review',
    name: '代码审查',
    alias: 'Code Review',
    icon: 'bkai-icon bkai-code',
    enable_fill_back: true,
    fill_back_component_key: 'code',
    components: [
      {
        type: 'textarea',
        key: 'code',
        name: '代码',
        fillBack: true,
        rows: 8,
        required: true,
        placeholder: '粘贴或选中需要审查的代码',
      },
      {
        type: 'select',
        key: 'focus',
        name: '关注点',
        options: [
          { label: '安全性', value: 'security' },
          { label: '性能', value: 'performance' },
          { label: '可读性', value: 'readability' },
          { label: '全面审查', value: 'all' },
        ],
        default: 'all',
      },
    ],
  },
  {
    id: 'summarize',
    name: '总结',
    icon: 'bkai-icon bkai-summary',
    enable_fill_back: true,
    fill_back_component_key: 'text',
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '内容',
        fillBack: true,
        placeholder: '输入需要总结的内容',
      },
      {
        type: 'number',
        key: 'maxWords',
        name: '字数上限',
        default: 200,
        min: 50,
        max: 1000,
      },
    ],
  },
];

// 智能过滤：根据选中文本内容动态显示快捷操作
const smartFilter = (shortcut: IShortcut, selectedText: string) => {
  if (!selectedText) return true;

  // 代码审查只在选中代码时显示
  if (shortcut.id === 'code_review') {
    return /function|const|let|var|class|import|def|func/.test(selectedText);
  }
  return true;
};

const onShortcutClick = (data: { shortcut: IShortcut; source: 'main' | 'popup' }) => {
  console.log(`执行 [${data.shortcut.name}]，来源: ${data.source}`);
};
</script>
```

## 服务端处理

快捷指令提交的表单数据以结构化方式发送到后端：

```javascript
// 后端接收到的请求体（property 部分）
{
  "property": {
    "extra": {
      "command": "code_review",             // 快捷指令 ID
      "context": [
        { "key": "code", "value": "..." },   // 表单数据
        { "key": "focus", "value": "all" }
      ],
      "cite": {
        "type": "structured",
        "title": "代码审查",
        "data": [
          { "key": "代码", "value": "..." },
          { "key": "关注点", "value": "全面审查" }
        ]
      }
    }
  }
}
```

> **注意**：后端需要通过 `command` 识别快捷操作类型，从 `context` 中获取表单数据进行处理。表单数据不再由前端拼接为 prompt 字符串。
