# 编程式控制

除了用户通过界面与 AI 小鲸交互外，您还可以通过调用组件实例的方法来编程式地控制其行为，例如主动发送消息。

## 主动发送消息 (`sendChat`)

`sendChat` 方法允许您从外部代码触发一次对话交互。这在实现自定义触发器或与其他组件联动时非常有用。

**方法签名:**

```typescript
sendChat(options: {
  message?: string; // 要发送的消息文本，可以为空
  cite?: string;    // 引用的文本内容
  shortcut?: {     // 模拟的快捷操作对象 (可选)
    label: string;
    key: string;
    prompt: string; // 包含 {{ SELECTED_TEXT }} 占位符的模板
    icon?: string;
  };
})
```

**参数说明:**

-   `message`: 用户输入的或您想模拟的用户消息。如果提供了 `shortcut` 且其 `prompt` 不为空，`message` 通常可以省略或用于显示目的。
-   `cite`: 您希望附加到本次提问的引用文本。如果提供了 `shortcut` 且其 `prompt` 包含 `{{ SELECTED_TEXT }}`，`cite` 会被用来替换这个占位符。
-   `shortcut`: 一个可选的对象，用于模拟用户点击了一个快捷操作。如果提供了 `shortcut`，组件会：
    1.  将 `cite` 的内容替换 `shortcut.prompt` 中的 `{{ SELECTED_TEXT }}`。
    2.  将处理后的 `prompt` 作为最终发送给 AI 的指令。
    3.  触发 `shortcut-click` 事件。

**使用场景:**

1.  **通过页面按钮触发特定带引用的提问:** (参见 [内容引用与快捷操作](/guide/core-features/content-referencing#快捷操作演示) 中的示例)
2.  **与其他组件联动:** 例如，在一个表单旁边放置 AI 按钮，点击后将表单的某个字段值作为 `cite`，并使用预设的 `shortcut` (如 "解释这个术语") 发送给 AI。

**示例 (联动场景):**

:::code-group
```vue [Vue 3]
<template>
  <div>
    <label>输入术语: <input type="text" v-model="term"></label>
    <button @click="explainTerm">让 AI 解释</button>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking, { type AIBluekingInstance } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<AIBluekingInstance | null>(null);
const apiUrl = '...';
const term = ref('');

const explainTerm = () => {
  if (!term.value) {
    alert('请输入术语');
    return;
  }
  aiBlueking.value?.handleShow();
  aiBlueking.value?.sendChat({
    // message: `解释术语: ${term.value}`, // 可以不传 message，依赖 shortcut.prompt
    cite: term.value, // 将输入框内容作为引用
    shortcut: {
      label: '解释术语',
      key: 'explain_term',
      prompt: '请用通俗易懂的语言解释以下术语：\n{{ SELECTED_TEXT }}'
    }
  });
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <label>输入术语: <input type="text" v-model="term"></label>
    <button @click="explainTerm">让 AI 解释</button>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: { AIBlueking },
  data() {
    return { apiUrl: '...', term: '' };
  },
  methods: {
    explainTerm() {
      if (!this.term) {
        alert('请输入术语');
        return;
      }
      this.$refs.aiBlueking.handleShow();
      this.$refs.aiBlueking.sendChat({
        // message: `解释术语: ${this.term}`, // 可以不传 message
        cite: this.term, // 将输入框内容作为引用
        shortcut: {
          label: '解释术语',
          key: 'explain_term',
          prompt: '请用通俗易懂的语言解释以下术语：\n{{ SELECTED_TEXT }}'
        }
      });
    }
  }
};
</script>
```
:::

这样，点击按钮后，AI 小鲸会弹出，并将输入框中的术语作为引用内容，发送“解释术语”的指令给 AI。