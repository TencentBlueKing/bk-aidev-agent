---
name: AiSelection AI 划词选择弹窗
slug: ai-selection
category: molecular
description: AI 划词选择组件，监听用户在页面中的文本选区，在选区附近弹出快捷操作菜单。支持自定义快捷指令列表、数量限制、垂直偏移以及完全自定义插槽内容。
aiSummary: >
  AiSelection 在 document 级监听文本选区，在选区附近弹出快捷操作菜单；每页建议只挂载一个实例。
  通过 shortcuts、maxShortcutCount、offset 等配置菜单内容与布局，支持完全自定义 default 插槽与 Shadow DOM 场景。
  常与 ChatInput 或业务侧联动，将选中文本作为追问上下文。
relatedComponents:
  - slug: shortcut-btn
    relation: 弹窗内快捷指令按钮/菜单项由该原子组件渲染
  - slug: chat-input
    relation: 划词结果常回填或触发与输入框联动的快捷指令
sinceVersion: 1.0.0
domain: input
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import AiSelectionComp from '../../../src/components/ai-selection/ai-selection.vue'

  const selectionVisible = ref(false);
  const selectedInfo = ref({ shortcut: '', text: '' });
  const activeConfig = ref('basic');

  const configs = {
    basic: {
      shortcuts: [{ id: 'ai-chat', name: '问问小鲸' }],
      maxShortcutCount: 3,
    },
    three: {
      shortcuts: [
        { id: 'ai-chat', name: '问问小鲸' },
        { id: 'translate', name: '翻译' },
        { id: 'explain', name: '解释' },
      ],
      maxShortcutCount: 3,
    },
    overflow3: {
      shortcuts: [
        { id: 'ai-chat', name: '问问小鲸' },
        { id: 'translate', name: '翻译' },
        { id: 'explain', name: '解释' },
        { id: 'summarize', name: '总结' },
        { id: 'improve', name: '改进' },
        { id: 'code', name: '生成代码' },
      ],
      maxShortcutCount: 3,
    },
    overflow5: {
      shortcuts: [
        { id: 'ai-chat', name: '问问小鲸' },
        { id: 'translate', name: '翻译' },
        { id: 'explain', name: '解释' },
        { id: 'summarize', name: '总结' },
        { id: 'improve', name: '改进' },
        { id: 'code', name: '生成代码' },
      ],
      maxShortcutCount: 5,
    },
    callback: {
      shortcuts: [
        { id: 'ai-chat', name: '问问小鲸' },
        { id: 'translate', name: '翻译' },
        { id: 'explain', name: '解释' },
      ],
      maxShortcutCount: 3,
    },
  };

  const currentConfig = ref(configs.basic);

  const switchConfig = (key) => {
    activeConfig.value = key;
    currentConfig.value = configs[key];
    selectedInfo.value = { shortcut: '', text: '' };
  };

  const handleSelectShortcut = (shortcut, text) => {
    selectedInfo.value = { shortcut: shortcut.name, text };
  };
</script>

# AiSelection AI 划词选择弹窗

> **层级**：分子组件 · **功能域**：输入交互

AI 划词选择组件，监听用户在页面中的文本选区，在选区附近弹出快捷操作菜单。支持自定义快捷指令列表、数量限制、垂直偏移以及完全自定义插槽内容。

> **注意**：`AiSelection` 通过 `document.addEventListener` 监听全局事件（`selectionchange`、`mouseup`、`mousedown`、`scroll`），**同一页面中只应挂载一个实例**，避免多实例同时响应导致事件重复和弹窗叠加。

## 工作原理

```
用户选中文本
   ↓  mouseup（200ms 防抖）/ selectionchange（300ms 防抖）
获取选区文本 & 坐标 → 计算弹窗位置
   ↓
通过 <Teleport to="body"> 将弹窗渲染到 <body> 末尾
   ↓
用户点击快捷指令 → 触发 selectShortcut 事件 → 关闭弹窗
```

弹窗渲染在 `<body>` 顶层，不受父级 `overflow: hidden` / `z-index` 影响，定位坐标基于视口（`position: fixed`）。

## 弹窗关闭时机

| 触发条件           | 说明                             |
| ------------------ | -------------------------------- |
| 点击弹窗外部区域   | `mousedown` 事件，弹窗外任意位置 |
| 滚动包含选区的容器 | `scroll` 事件捕获阶段            |
| 窗口大小改变       | `window.resize`                  |
| 窗口失去焦点       | `window.blur`                    |
| 点击快捷指令       | 触发后立即关闭并清除选区         |

## 基础用法

不传 `shortcuts` 时，使用内置默认快捷指令"问问小鲸"（`id: 'ai-chat'`）：

```vue
<template>
  <AiSelection v-model:visible="selectionVisible" />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection } from '@blueking/chat-x';

  const selectionVisible = ref(false);
</script>
```

**渲染效果**（选中下方文字后弹出快捷操作菜单）

<div class="demo">
  <div
    @mousedown="switchConfig('basic')"
    style="padding: 16px; background: #f5f7fa; border-radius: 8px; user-select: text; line-height: 1.8;"
  >
    <p style="margin: 0;">这是一段使用默认快捷指令的示例文本。选中这段文字后，会出现「问问小鲸」按钮。</p>
  </div>
</div>

## 自定义快捷指令

通过 `shortcuts` 属性传入自定义快捷指令列表：

```vue
<template>
  <AiSelection
    v-model:visible="selectionVisible"
    :shortcuts="shortcuts"
    @select-shortcut="handleSelectShortcut"
    @selection-change="handleSelectionChange"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection, type Shortcut } from '@blueking/chat-x';

  const selectionVisible = ref(false);

  const shortcuts: Shortcut[] = [
    { id: 'ai-chat', name: '问问小鲸' },
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释' },
  ];

  const handleSelectShortcut = (shortcut: Shortcut, selectedText: string) => {
    console.log('触发指令:', shortcut.name, '选中文本:', selectedText);
  };

  const handleSelectionChange = (text: string) => {
    console.log('选区变化:', text);
  };
</script>
```

**渲染效果**（选中文字后弹出 3 个快捷操作按钮）

<div class="demo">
  <div
    @mousedown="switchConfig('three')"
    style="padding: 16px; background: #f5f7fa; border-radius: 8px; user-select: text; line-height: 1.8;"
  >
    <p style="margin: 0 0 8px;">Vue 3 是一个渐进式 JavaScript 框架，它提供了组合式 API、更好的 TypeScript 支持以及更高效的虚拟 DOM。</p>
    <p style="margin: 0;">选中上方文字，弹窗会展示「问问小鲸」「翻译」「解释」三个快捷按钮。</p>
  </div>
</div>

## 快捷指令数量限制

当快捷指令数量超过 `maxShortcutCount`（默认 `3`）时，多余的指令会收起到「更多」菜单（点击 `›` 箭头展开）。

### `maxShortcutCount = 3`（默认）

6 个指令中前 3 个直接展示，其余 3 个收起：

```vue
<template>
  <AiSelection
    v-model:visible="selectionVisible"
    :shortcuts="shortcuts"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection, type Shortcut } from '@blueking/chat-x';

  const selectionVisible = ref(false);

  const shortcuts: Shortcut[] = [
    { id: 'ai-chat', name: '问问小鲸' },
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释' },
    { id: 'summarize', name: '总结' },
    { id: 'improve', name: '改进' },
    { id: 'code', name: '生成代码' },
  ];
</script>
```

**渲染效果**（展示 3 个，其余 3 个收起到「更多」菜单）

<div class="demo">
  <div
    @mousedown="switchConfig('overflow3')"
    style="padding: 16px; background: #f5f7fa; border-radius: 8px; user-select: text; line-height: 1.8;"
  >
    <p style="margin: 0;">选中这段文本，弹窗仅显示前 3 个指令（问问小鲸、翻译、解释），其余 3 个（总结、改进、生成代码）收起到「更多」菜单中。</p>
  </div>
</div>

### `maxShortcutCount = 5`

前 5 个直接展示，仅最后 1 个收起：

```vue
<AiSelection v-model:visible="selectionVisible" :shortcuts="shortcuts" :max-shortcut-count="5" />
```

**渲染效果**（展示 5 个，仅「生成代码」收起）

<div class="demo">
  <div
    @mousedown="switchConfig('overflow5')"
    style="padding: 16px; background: #f5f7fa; border-radius: 8px; user-select: text; line-height: 1.8;"
  >
    <p style="margin: 0;">选中这段文本，弹窗展示前 5 个指令，仅「生成代码」被收起到更多菜单中。</p>
  </div>
</div>

## 带图标的快捷指令

`icon` 属性支持三种形式：

| 类型                              | 说明            | 示例                             |
| --------------------------------- | --------------- | -------------------------------- |
| `string`（emoji）                 | 直接渲染文本    | `'🌐'`                           |
| `string`（HTTP URL）              | 渲染为 `<img>`  | `'https://example.com/icon.svg'` |
| `VNode \| (c: typeof h) => VNode` | 渲染为 Vue 组件 | `ThinkingIcon`（内置图标组件）   |

```vue
<script setup lang="ts">
  import { h } from 'vue';
  import { AiSelection, type Shortcut } from '@blueking/chat-x';

  const shortcuts: Shortcut[] = [
    {
      id: 'ai-chat',
      name: '问问小鲸',
      // VNode 渲染函数
      icon: c => c('span', { style: 'font-size: 14px;' }, '🐳'),
    },
    {
      id: 'translate',
      name: '翻译',
      icon: '🌐', // Emoji 字符串
    },
    {
      id: 'search',
      name: '搜索',
      icon: 'https://example.com/search-icon.svg', // URL（渲染为 img）
    },
  ];
</script>
```

## 事件回调

`selectShortcut` 在用户点击快捷指令后触发，携带指令对象和选中文本；`selectionChange` 在选区文字内容变化时触发：

```vue
<template>
  <div>
    <p>选中文字后点击快捷指令，观察下方回调信息。</p>

    <AiSelection
      v-model:visible="selectionVisible"
      :shortcuts="shortcuts"
      @select-shortcut="handleSelectShortcut"
      @selection-change="handleSelectionChange"
    />

    <div
      v-if="selectedInfo.shortcut"
      class="callback-info"
    >
      <p>触发指令：{{ selectedInfo.shortcut }}</p>
      <p>选中文本：{{ selectedInfo.text }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection, type Shortcut } from '@blueking/chat-x';

  const selectionVisible = ref(false);
  const selectedInfo = ref({ shortcut: '', text: '' });

  const shortcuts: Shortcut[] = [
    { id: 'ai-chat', name: '问问小鲸' },
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释' },
  ];

  const handleSelectShortcut = (shortcut: Shortcut, selectedText: string) => {
    selectedInfo.value = { shortcut: shortcut.name, text: selectedText };
  };

  const handleSelectionChange = (text: string) => {
    console.log('选区变化:', text);
  };
</script>
```

**渲染效果**（点击快捷指令后下方显示回调信息）

<div class="demo">
  <div
    @mousedown="switchConfig('callback')"
    style="padding: 16px; background: #f5f7fa; border-radius: 8px; user-select: text; line-height: 1.8;"
  >
    <p style="margin: 0;">选中这段文字，然后点击弹窗中的快捷指令按钮，观察下方回调信息的变化。</p>
  </div>
  <div v-if="selectedInfo.shortcut" style="margin-top: 12px; padding: 12px; background: #e1ecff; border-radius: 4px; font-size: 13px;">
    <p style="margin: 0 0 4px;">触发指令：<strong>{{ selectedInfo.shortcut }}</strong></p>
    <p style="margin: 0;">选中文本：<code>{{ selectedInfo.text }}</code></p>
  </div>
</div>

## 自定义垂直偏移

`offset` 控制弹窗与选区之间的垂直距离（单位 px），默认 `10`。弹窗优先显示在选区**上方**，空间不足时自动显示在**下方**：

```vue
<!-- 间距 20px -->
<AiSelection v-model:visible="selectionVisible" :offset="20" />

<!-- 紧贴选区（间距 0） -->
<AiSelection v-model:visible="selectionVisible" :offset="0" />
```

## 自定义插槽

默认插槽替换整个弹窗内容区，插槽参数 `shortcuts` 为**完整**快捷指令列表（未经 `maxShortcutCount` 截断）：

```vue
<template>
  <AiSelection
    v-model:visible="selectionVisible"
    :shortcuts="shortcuts"
  >
    <template #default="{ shortcuts }">
      <div class="my-menu">
        <button
          v-for="shortcut in shortcuts"
          :key="shortcut.id"
          @click="handleClick(shortcut)"
        >
          {{ shortcut.name }}
        </button>
      </div>
    </template>
  </AiSelection>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection, type Shortcut } from '@blueking/chat-x';

  const selectionVisible = ref(false);

  const shortcuts: Shortcut[] = [
    { id: 'ai-chat', name: '问问小鲸' },
    { id: 'translate', name: '翻译' },
  ];

  const handleClick = (shortcut: Shortcut) => {
    const text = window.getSelection()?.toString() || '';
    console.log(shortcut.name, text);
  };
</script>
```

> **注意**：使用默认插槽后，`maxShortcutCount` 不再生效，「更多」菜单也不会出现，需要自行处理超出逻辑。

## 排除区域

通过 `excludeSelectors` 指定 CSS 选择器列表，当选区位于这些选择器匹配的元素内部时，弹窗不会弹出。适用于代码块、表单输入等不需要划词弹窗的区域：

```vue
<template>
  <AiSelection
    v-model:visible="selectionVisible"
    :exclude-selectors="['.code-block', '.no-selection']"
  />

  <div class="code-block">这里选中文字不会弹出操作菜单</div>
  <div class="no-selection">这里也不会弹出</div>
  <p>这里选中文字正常弹出操作菜单</p>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection } from '@blueking/chat-x';

  const selectionVisible = ref(false);
</script>
```

## Input / Textarea 支持

组件对 `<input>` 和 `<textarea>` 中的选区进行了特殊处理：原生 Range 在这两类元素中无法获取准确坐标，组件会降级使用**输入框自身的 `getBoundingClientRect()`** 作为弹窗位置参考。

## 与 ChatBot 联动

选中文本后触发快捷指令，自动将选中内容作为上下文发送到聊天窗口：

```vue
<template>
  <div class="page">
    <article>文章内容...</article>

    <AiSelection
      v-model:visible="selectionVisible"
      :shortcuts="shortcuts"
      @select-shortcut="handleSelectShortcut"
    />

    <ChatBot ref="chatBotRef" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiSelection, ChatBot, type Shortcut } from '@blueking/chat-x';

  const selectionVisible = ref(false);
  const chatBotRef = ref();

  const shortcuts: Shortcut[] = [
    { id: 'ai-chat', name: '问问小鲸' },
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释' },
  ];

  const handleSelectShortcut = (shortcut: Shortcut, selectedText: string) => {
    const prompts: Record<string, string> = {
      translate: `请翻译以下内容：\n${selectedText}`,
      explain: `请解释以下内容：\n${selectedText}`,
    };
    chatBotRef.value?.sendMessage(prompts[shortcut.id] ?? selectedText);
  };
</script>
```

<!-- 全页唯一的 AiSelection 实例，通过各演示区的 mousedown 切换当前配置 -->

<AiSelectionComp
v-model:visible="selectionVisible"
:shortcuts="currentConfig.shortcuts"
:max-shortcut-count="currentConfig.maxShortcutCount"
@select-shortcut="handleSelectShortcut"
/>

## API

### Props

| 属性名           | 类型         | 默认值              | 必填 | 说明                                                    |
| ---------------- | ------------ | ------------------- | ---- | ------------------------------------------------------- |
| visible          | `boolean`    | -                   | ✅   | 控制弹窗显示，必须使用 `v-model:visible`                |
| shortcuts        | `Shortcut[]` | `DEFAULT_SHORTCUTS` | -    | 快捷指令列表，默认为内置「问问小鲸」                    |
| maxShortcutCount | `number`     | `3`                 | -    | 直接展示的最大指令数，超出收起到「更多」菜单            |
| offset           | `number`     | `10`                | -    | 弹窗与选区的垂直间距（px）                              |
| excludeSelectors | `string[]`   | `[]`                | -    | 排除的 CSS 选择器数组，选区在这些选择器内部时不显示弹窗 |

### Events

| 事件名          | 参数                                 | 说明                                    |
| --------------- | ------------------------------------ | --------------------------------------- |
| selectShortcut  | `(shortcut: Shortcut, text: string)` | 点击快捷指令时触发，`text` 为选中的文本 |
| selectionChange | `(text: string)`                     | 选区文本内容发生变化时触发              |

### Slots

| 插槽名  | 参数                        | 说明                                           |
| ------- | --------------------------- | ---------------------------------------------- |
| default | `{ shortcuts: Shortcut[] }` | 自定义弹窗内容，`shortcuts` 为完整快捷指令列表 |

## 定位逻辑

| 方向     | 规则                                                                                 |
| -------- | ------------------------------------------------------------------------------------ |
| 水平方向 | 弹窗居中对齐选区，超出视口左/右边界时自动贴边（保留 8px 间距）                       |
| 垂直方向 | 优先显示在选区**上方**，上方空间不足时显示在**下方**；两侧均不足时选择空间较大的一侧 |

## 默认快捷指令

```typescript
const DEFAULT_SHORTCUTS: Shortcut[] = [{ id: 'ai-chat', name: '问问小鲸' }];
```

## Shadow DOM 支持

组件会递归查找当前 `document.activeElement` 下的 Shadow DOM，兼容 Web Components 场景。若 Shadow DOM 中存在有效文本选区，弹窗同样会正常弹出并定位。

## 类型定义

```typescript
import { type Component, type VNode, h } from 'vue';

interface Shortcut {
  id: string;
  name: string;
  key?: string;
  icon?: ((c: typeof h) => Component | VNode) | string | VNode;
  components?: ShortcutComponent[];
  // ... 其余字段参见 ShortcutRender 文档
}
```

## 使用场景

- **文章阅读划词**：选中内容后弹出「问问小鲸」「翻译」「解释」等快捷入口
- **代码解释**：在代码区块中选中代码片段，触发「解释代码」「优化建议」等操作
- **文本处理**：对选中内容进行翻译、总结、改写等 AI 增强处理
- **与 ChatBot 联动**：选中文本后将内容作为上下文自动填入聊天输入框

## 关联组件

- [ShortcutBtn](../atomic/shortcut-btn.md) — 弹窗内快捷指令按钮单元
- [ChatInput](./chat-input.md) — 选区文本常回填到聊天输入框
