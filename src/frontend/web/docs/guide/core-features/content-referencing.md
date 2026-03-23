# 内容引用

AI 小鲸 v2.0 支持将外部内容作为引用附加到对话消息中，让 AI 可以基于引用的上下文进行回答。内容引用通过消息的 `property` 系统传递给后端。

## 简单文本引用

最常用的引用方式是将一段文本作为引用内容附加到消息中。通过 `setCiteText()` 方法设置引用文本。

### 使用方法

```vue
<template>
  <div>
    <p ref="contentRef">这是一段需要引用的内容...</p>
    <button @click="citeContent">引用此段落</button>

    <ChatBot ref="chatBotRef" url="/api/ai/assistant/" />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';

const chatBotRef = ref<InstanceType<typeof ChatBot> | null>(null);
const contentRef = ref<HTMLElement | null>(null);

const citeContent = () => {
  const text = contentRef.value?.textContent ?? '';
  // 设置引用文本，会显示在输入框上方
  chatBotRef.value?.setCiteText(text);
  // 聚焦输入框
  chatBotRef.value?.focusInput();
};
</script>
```

### 数据流

调用 `setCiteText(text)` 后，引用文本会绑定到 `ChatInput` 的 `v-model:cite`。当用户发送消息时，引用内容会以简单字符串的形式写入 `property`：

```typescript
// 发送到后端的 property 结构
{
  extra: {
    cite: '用户引用的文本内容'
  }
}
```

## 结构化引用

结构化引用用于传递更复杂的引用数据，通常与快捷指令配合使用。引用数据包含标题和键值对列表。

### 数据结构

```typescript
// 结构化引用的 property 格式
{
  extra: {
    cite: {
      type: 'structured',
      title: '日志分析',                    // 引用标题
      data: [
        { key: '日志内容', value: '...' },   // 键值对形式的结构化数据
        { key: '日志 ID', value: '12345' },
      ],
    },
    command: 'log_analysis',               // 快捷指令 ID
    context: [
      {
        log: '...',                         // 原始字段键值
        context_type: 'textarea',           // 组件类型
        __label: '日志内容',                 // 元数据
        __key: 'log',
        __value: '...',
      },
    ],
  }
}
```

### 使用场景

结构化引用通常由快捷指令表单自动构建。当用户填写快捷指令表单并提交时，`ChatBot` 内部会调用 `buildShortcutProperty()` 将表单数据转换为结构化 `property`：

```
用户填写快捷指令表单
  → handleShortcutSubmit()
    → buildShortcutProperty(shortcut, formData)
      → 构建 { extra: { cite, command, context } }
    → doSendMessage(message, { property })
      → ChatBusinessManager.sendMessage(content, sessionCode, { property })
```

## AiSelection 划词弹窗

AI 小鲸提供了划词弹窗功能，用户在页面上选中文本后会自动弹出快捷操作菜单。

### 启用划词弹窗

通过 `enablePopup` prop 启用（`AIBlueking` 组件，默认为 `true`）：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :enable-popup="true"
    :shortcuts="shortcuts"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '/api/ai/assistant/';

const shortcuts = [
  {
    id: 'explain',
    name: '解释',
    icon: 'bkai-icon bkai-explain',
    enable_fill_back: true,
    fill_back_component_key: 'text',
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '内容',
        fillBack: true,
      },
    ],
  },
  {
    id: 'translate',
    name: '翻译',
    icon: 'bkai-icon bkai-translate',
    enable_fill_back: true,
    fill_back_component_key: 'text',
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '待翻译文本',
        fillBack: true,
      },
      {
        type: 'select',
        key: 'targetLang',
        name: '目标语言',
        options: [
          { label: '英文', value: 'en' },
          { label: '日文', value: 'jp' },
        ],
        default: 'en',
      },
    ],
  },
];
</script>
```

### 工作流程

![AiSelection 划词工作流](/images/guide/ai-selection-workflow.png)

### 禁用特定区域

在不希望弹出划词菜单的 HTML 元素上添加 `ai-blueking-hide` 属性：

```html
<div ai-blueking-hide>
  <p>在此区域内选中文本不会触发划词弹窗</p>
  <pre>
    // 代码区域也不会触发
    const x = 10;
  </pre>
</div>
```

AI 小鲸会从选中文本所在元素向上遍历 DOM 树，如果发现 `ai-blueking-hide` 属性则不弹出菜单。

## 引用数据流总结

![引用数据流总结](/images/guide/content-reference-flow.png)

## 编程式触发引用

```vue
<template>
  <div>
    <button @click="citeAndAsk">引用并提问</button>
    <AIBlueking ref="aiRef" :url="apiUrl" />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiRef = ref<InstanceType<typeof AIBlueking> | null>(null);
const apiUrl = '/api/ai/assistant/';

const citeAndAsk = async () => {
  if (!aiRef.value) return;

  // 1. 打开面板
  await aiRef.value.handleShow();

  // 2. 设置引用文本
  aiRef.value.setCiteText('这是需要分析的日志内容...');

  // 3. 聚焦输入框，等待用户输入
  aiRef.value.focusInput();
};
</script>
```
