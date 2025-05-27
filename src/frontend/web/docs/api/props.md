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
| `shortcuts`     | `Array<ShortCut>` | `[]`        | 快捷操作列表。详细格式参见 [内容引用与快捷操作指南](/guide/core-features/content-referencing#配置快捷操作-shortcuts)。 |
| `prompts`       | `Array<String>`   | `[]`        | 预设提示词列表。在1.0版本中，这些提示词会与智能体配置的预设问题(`predefinedQuestions`)合并展示。       |
| `requestOptions`| `Object`          | `{}`        | 自定义请求选项，可设置 `headers` 和 `data` 属性，分别合并到请求头和请求体。详细说明参见 [自定义请求指南](/guide/advanced-usage/custom-requests)。 |
| `defaultMinimize`| `Boolean`         | `false`     | 控制 AI 小鲸窗口初始是否处于最小化状态。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#初始最小化状态)。 |
| `teleportTo`    | `String`          | `'body'`    | 控制组件内容传送到的 DOM 节点，可将组件内容渲染到任意 DOM 位置。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#自定义传送目标)。 |
| `hideHeader`    | `Boolean`         | `false`     | 设置为`true`时隐藏组件的头部栏。                                                                      |
| `hideNimbus`    | `Boolean`         | `false`     | 设置为`true`时隐藏Nimbus悬浮图标。                                                                     |
| `draggable`     | `Boolean`         | `true`      | 控制组件是否可拖拽。设置为 `false` 时，窗口将固定在位置上不可移动。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultWidth`  | `Number`          | `400` | 设置组件初始宽度，单位为像素。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultHeight` | `Number`          | `undefined` | 设置组件初始高度，单位为像素，不设置组件会动态计算，设置为视窗高度。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultTop`    | `Number`          | `0` | 设置组件初始顶部位置，单位为像素。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |
| `defaultLeft`   | `Number`          | `undefined` | 设置组件初始左侧位置，单位为像素。不设置会动态计算，设置为 `视窗宽度 - defaultWidth`。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#拖拽功能控制与初始位置设置)。 |

::: danger 已废弃属性
以下属性在1.0版本中已被移除:
- `defaultMessages`: 预设对话内容属性已被移除，在1.0版本中改为从智能体配置获取。详情请参阅[预设对话内容指南](/guide/advanced-usage/default-messages)。
:::

## `ShortCut` 对象格式

`shortcuts` 数组中的每个对象应符合以下格式：

```typescript
interface ShortCut {
  type: string;        // 操作类型，作为操作的唯一标识符
  label: string;       // 按钮上显示的文本
  cite?: boolean;      // (可选) 是否需要引用文本，默认为false
  prompt?: string;     // (可选) 指令模板，可包含 {{cite}} 占位符
  icon?: string;       // (可选) 按钮图标的类名
}
```

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