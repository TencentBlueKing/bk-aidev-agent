# Props

组件支持的属性列表。

::: warning 版本变更提示
部分属性在1.0版本中的行为有所变化，请注意查看相关说明。
:::

| 属性名          | 类型              | 默认值      | 描述                                                                                                   |
| --------------- | ----------------- | ----------- | ------------------------------------------------------------------------------------------------------ |
| `url`           | `String`          | `''`        | **必需**. AI 服务接口地址，1.0版本中用于获取智能体配置信息。                                            |
| `title`         | `String`          | `'AI 小鲸'`  | 在头部显示的标题文本。                                                                                |
| `helloText`     | `String`          | `'你好，我是小鲸'` | 初始欢迎页面显示的问候语。在1.0版本中，智能体配置的开场白(`openingRemark`)优先级高于此属性。         |
| `enablePopup`   | `Boolean`         | `true`      | 是否启用选中文本后的弹出操作窗口 (需要配合 `shortcuts` 使用)。                                            |
| `prompts`       | `Array<String>`   | `[]`        | 预设提示词列表。在1.0版本中，这些提示词会与智能体配置的预设问题(`predefinedQuestions`)合并展示。       |
| `shortcuts`     | `Array<IShortcut>` | `[]`        | 快捷操作列表。详细格式参见 [内容引用与快捷操作指南](/guide/core-features/content-referencing#配置快捷操作-shortcuts)。 |
| `requestOptions`| `Object`          | `{}`        | 自定义请求选项，可设置 `headers` 和 `data` 属性，分别合并到请求头和请求体，以及 `context` 属性，作为上下文参数传递给后端。详细说明参见 [自定义请求指南](/guide/advanced-usage/custom-requests)。 |
| `defaultMinimize`| `Boolean`         | `false`     | 控制 AI 小鲸窗口初始是否处于最小化状态。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#初始最小化状态)。 |
| `teleportTo`    | `String`          | `'body'`    | 控制组件内容传送到的 DOM 节点，可将组件内容渲染到任意 DOM 位置。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#自定义传送目标)。 |
| `hideHeader`    | `Boolean`         | `false`     | 设置为`true`时隐藏组件的头部栏。                                                                      |
| `hideNimbus`    | `Boolean`         | `false`     | 设置为`true`时隐藏Nimbus悬浮图标。                                                                     |
| `nimbusSize`    | `String`          | `'normal'`  | 设置 Nimbus 悬浮图标的尺寸。可选值为 `'small'`, `'normal'`, `'large'`。                               |
| `draggable`     | `Boolean`         | `true`      | 控制组件是否可拖拽。设置为 `false` 时，窗口将固定在位置上不可移动。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultWidth`  | `Number`          | `400` | 设置组件初始宽度，单位为像素。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultHeight` | `Number`          | `undefined` | 设置组件初始高度，单位为像素，不设置组件会动态计算，设置为视窗高度。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultTop`    | `Number`          | `0` | 设置组件初始顶部位置，单位为像素。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultLeft`   | `Number`          | `undefined` | 设置组件初始左侧位置，单位为像素。不设置会动态计算，设置为 `视窗宽度 - defaultWidth`。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `disabledInput` | `Boolean`        | `false`     | 控制输入框是否处于禁用状态。设置为 `true` 时，用户无法在输入框中输入文本。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#输入框禁用控制)。 |

::: danger 已废弃属性
以下属性在1.0版本中已被移除:
- `defaultMessages`: 预设对话内容属性已被移除，在1.0版本中改为从智能体配置获取。详情请参阅[预设对话内容指南](/guide/advanced-usage/default-messages)。
:::

## `IShortcut` 对象格式

`shortcuts` 数组中的每个对象应符合以下格式：

```typescript
interface IShortcut {
  id: string;       // 快捷操作的唯一标识符
  name: string;     // 显示的操作名称
  icon?: string;    // 按钮图标的类名
  // 组件配置，用于定义表单项
  components: Array<{
    type: string;    // 组件类型：'input', 'text', 'textarea', 'select', 'number' 等
    name?: string;   // 表单项名称
    label?: string;  // 表单项标签
    key: string;     // 表单项键名
    placeholder?: string; // 占位文本
    default?: any;   // 默认值
    required?: boolean;   // 是否必填
    fillBack?: boolean;   // 是否自动填充选中文本
    fillRegx?: string | RegExp;    // 填充的正则匹配表达式
    rows?: number;        // 输入框行数（仅 textarea 类型有效）
    min?: number;         // 最小值（仅 number 类型有效）
    max?: number;         // 最大值（仅 number 类型有效）
    options?: Array<{     // 下拉选项（仅select类型）
      label: string;
      value: string | number;
    }>;
  }>
}
```

### 组件类型

目前支持以下类型的表单组件：

| 组件类型 | 描述 | 特有属性 |
| ------- | ---- | ------- |
| `text` | 单行文本输入框 | `placeholder` |
| `textarea` | 多行文本输入框 | `placeholder`, `rows` |
| `number` | 数字输入框 | `min`, `max`, `default` |
| `select` | 下拉选择框 | `options`, `placeholder`, `default` |

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
      label: '待翻译文本',
      fillBack: true, // 启用自动填充
      fillRegx: '.*', // 可选，使用正则表达式匹配选中的文本
      placeholder: '请输入或选中需要翻译的文本'
    },
    {
      type: 'select',
      key: 'targetLang',
      label: '目标语言',
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
  headers?: Record<string, any>; // 请求头参数
  data?: Record<string, any>;    // 请求体附加数据
  context?: Array<{              // 上下文参数数据
    key: string;                 // 参数键名
    value: any;                  // 参数值
  }>; 
}
```

### 示例

```vue
<template>
  <AIBlueking 
    :request-options="{
      headers: {
        'X-Custom-Header': 'value'
      },
      data: {
        preset: 'QA'
      },
      context: [
        { key: 'language', value: 'javascript' },
        { key: 'scenario', value: 'code_review' }
      ]
    }"
  />
</template>
```

这些参数会在发送请求时与其他参数一起发送，其中 `context` 会被合并到快捷操作的表单数据中，作为上下文信息传递给后端。

## 会话内容访问

组件实例暴露了`sessionContents`属性，可用于获取当前会话内容：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="getContents">获取会话内容</button>
</template>

<script setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiBlueking = ref(null);

const getContents = () => {
  const contents = aiBlueking.value?.sessionContents;
  console.log('当前会话内容:', contents);
};
</script>
```