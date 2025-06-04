# 编程式控制

除了用户通过界面与 AI 小鲸交互外，您还可以通过调用组件实例的方法来编程式地控制其行为，例如主动发送消息或控制窗口显示状态。

::: warning 版本变更提示
1.0版本中，`sendChat`方法已被替换为`handleSendMessage`方法，请注意更新您的代码。
:::

## 可用方法列表

AI小鲸组件实例提供以下方法用于编程式控制:

| 方法名 | 描述 |
| ------ | ---- |
| `handleShow()` | 显示AI小鲸窗口 |
| `handleClose()` | 关闭AI小鲸窗口 |
| `handleStop()` | 停止当前内容生成 |
| `handleSendMessage(options)` | 主动发送消息，详见下文 |
| `handleShortcutClick(shortcut)` | 模拟点击快捷操作 |

## 主动发送消息 (`handleSendMessage`)

`handleSendMessage` 方法允许您从外部代码触发一次对话交互。这在实现自定义触发器或与其他组件联动时非常有用。

**方法签名:**

```typescript
handleSendMessage(options: {
  message?: string; // 要发送的消息文本，可以为空
})
```

**参数说明:**

-   `message`: 用户输入的或您想模拟的用户消息。如果提供了 `shortcut` 且其 `prompt` 不为空，`message` 通常可以省略或用于显示目的。

**使用场景:**

1.  **需要通过编程控制直接发送信息与 AI小鲸交互**

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
import { AIBlueking } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/style.css';

const aiBlueking = ref(null);
const apiUrl = '...';
const term = ref('');

const explainTerm = () => {
  if (!term.value) {
    alert('请输入术语');
    return;
  }
  aiBlueking.value?.handleShow();
  aiBlueking.value?.handleSendMessage({
    message: `解释术语: ${term.value}`,
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
import { AIBlueking } from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/style.css';

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
      this.$refs.aiBlueking.handleSendMessage({
        message: `解释术语: ${this.term}`
      });
    }
  }
};
</script>
```
:::

这样，点击按钮后，AI 小鲸会弹出，并将输入框中的术语作为引用内容，发送"解释术语"的指令给 AI。