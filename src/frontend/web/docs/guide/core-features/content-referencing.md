# 内容引用与快捷操作

AI 小鲸的核心特性之一是能够方便地引用页面上的文本内容，并进行快速提问或执行预设操作。

## 启用选中文本弹出菜单

通过设置 `enablePopup` prop 为 `true` (默认值)，用户在页面上选中一段文本后，会自动在选中文本附近弹出一个小图标。点击该图标会展开快捷操作菜单（如果配置了 `shortcuts`）并自动将选中的文本作为引用内容。

```vue
<template>
  <AIBlueking :url="apiUrl" :enable-popup="true" />
</template>

<script setup> // 或 <script>
import AIBlueking from '@blueking/ai-blueking'; // 或 /vue2
import '@blueking/ai-blueking/dist/vue3/style.css'; // 或 /vue2
const apiUrl = '...';
</script>
```

如果设置为 `false`，则不会在选中文本后弹出菜单。

## 配置快捷操作 (Shortcuts)

您可以通过 `shortcuts` prop 定义一组快捷操作按钮，这些按钮会显示在选中文本弹出的菜单中，以及 AI 对话窗口的输入框上方。

`shortcuts` 是一个对象数组，每个对象代表一个快捷操作，包含以下字段：

-   `label` (String): 按钮上显示的文本。
-   `key` (String): 操作的唯一标识符。
-   `prompt` (String): 点击按钮后发送给 AI 的指令模板。可以使用 `{{ SELECTED_TEXT }}` 作为占位符，它会被用户选中的文本或当前引用的文本替换。
-   `icon` (String, 可选): 按钮的图标类名。

**格式示例:**

```javascript
const myShortcuts = [
  {
    label: '解释',
    key: 'explanation',
    prompt: '请用简洁的语言解释以下内容：\n{{ SELECTED_TEXT }}',
    icon: 'bk-icon icon-help-fill' // 示例图标，请替换为您项目中的图标类名
  },
  {
    label: '翻译成英文',
    key: 'translate_en',
    prompt: '将以下内容翻译成英文：\n{{ SELECTED_TEXT }}',
    icon: 'bk-icon icon-translate' // 示例图标
  },
  {
    label: '总结要点',
    key: 'summarize',
    prompt: '请总结以下内容的要点：\n{{ SELECTED_TEXT }}'
    // icon: '...'
  }
]
```

**在组件中使用:**

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking :url="apiUrl" :shortcuts="myShortcuts" />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '...';
const myShortcuts = [ /* ... 如上所示 ... */ ];
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking :url="apiUrl" :shortcuts="myShortcuts" />
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: { AIBlueking },
  data() {
    return {
      apiUrl: '...',
      myShortcuts: [ /* ... 如上所示 ... */ ]
    };
  }
};
</script>
```
:::

当用户点击快捷操作按钮时，组件会自动：
1.  显示 AI 小鲸窗口（如果尚未显示）。
2.  将 `prompt` 中的 `{{ SELECTED_TEXT }}` 替换为当前引用的文本。
3.  将处理后的 `prompt` 发送给 AI。
4.  触发 `shortcut-click` 事件，并传递被点击的 shortcut 对象。

## 快捷操作事件 (shortcut-click)

当用户点击快捷操作按钮时，会触发 `shortcut-click` 事件。您可以监听此事件以执行自定义逻辑。

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking :url="apiUrl" :shortcuts="myShortcuts" @shortcut-click="handleShortcut" />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '...';
const myShortcuts = [ /* ... */ ];

const handleShortcut = (shortcut) => {
  console.log('点击了快捷操作:', shortcut.key, shortcut.label);
  // 可以在这里做一些额外处理，比如打点上报
};
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking :url="apiUrl" :shortcuts="myShortcuts" @shortcut-click="handleShortcut" />
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: { AIBlueking },
  data() {
    return { apiUrl: '...', myShortcuts: [ /* ... */ ] };
  },
  methods: {
    handleShortcut(shortcut) {
      console.log('点击了快捷操作:', shortcut.key, shortcut.label);
      // 可以在这里做一些额外处理，比如打点上报
    }
  }
};
</script>
```
:::

## 快捷操作演示

以下示例展示了如何在页面上放置一些按钮，点击后主动调用 AI 小鲸的 `sendChat` 方法来模拟快捷操作的触发，并将特定文本（如文章标题）作为引用内容。

:::code-group
```vue [Vue 3]
<template>
  <div>
    <div class="article">
      <h3>AI 技术的发展与应用</h3>
      <p>{{ articleContent }}</p>
    </div>

    <div class="quick-actions">
      <button @click="quickAction('解释', '解释一下这段内容：', articleTitle)">
        解释标题
      </button>
      <button @click="quickAction('翻译', '翻译成英文：', articleTitle)">
        翻译标题
      </button>
    </div>

    <AIBlueking ref="aiBlueking" :url="apiUrl" />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
const articleTitle = 'AI 技术的发展与应用';
const articleContent = '人工智能技术在近年来取得了突飞猛进的发展...';

const quickAction = (label: string, promptPrefix: string, cite: string) => {
  aiBlueking.value?.handleShow(); // 确保窗口显示

  // 构造 shortcut 对象并调用 sendChat
  aiBlueking.value?.sendChat({
    message: label, // message 可以是按钮的文本或空的
    cite,          // 要引用的内容
    shortcut: {    // 模拟的 shortcut 对象
      label,
      key: label.toLowerCase(), // key 通常是唯一的标识
      prompt: `${promptPrefix} {{ SELECTED_TEXT }}`, // prompt 模板
      // icon: 'icon-xxx' // 可选 icon
    }
  });
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <div class="article">
      <h3>AI 技术的发展与应用</h3>
      <p>{{ articleContent }}</p>
    </div>

    <div class="quick-actions">
      <button @click="quickAction('解释', '解释一下这段内容：', articleTitle)">
        解释标题
      </button>
      <button @click="quickAction('翻译', '翻译成英文：', articleTitle)">
        翻译标题
      </button>
    </div>

    <AIBlueking ref="aiBlueking" :url="apiUrl" />
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      articleTitle: 'AI 技术的发展与应用',
      articleContent: '人工智能技术在近年来取得了突飞猛进的发展...'
    };
  },
  methods: {
    quickAction(label, promptPrefix, cite) {
      this.$refs.aiBlueking.handleShow(); // 确保窗口显示

      // 构造 shortcut 对象并调用 sendChat
      this.$refs.aiBlueking.sendChat({
        message: label, // message 可以是按钮的文本或空的
        cite,          // 要引用的内容
        shortcut: {    // 模拟的 shortcut 对象
          label,
          key: label.toLowerCase(), // key 通常是唯一的标识
          prompt: `${promptPrefix} {{ SELECTED_TEXT }}` // prompt 模板
          // icon: 'icon-xxx' // 可选 icon
        }
      });
    }
  }
};
</script>

:::