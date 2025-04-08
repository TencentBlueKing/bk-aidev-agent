# Methods

可以通过组件实例调用的方法列表。

| 方法名                | 参数                                         | 返回值   | 描述                                                                                                                             |
| --------------------- | -------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `handleShow()`        | -                                            | `void`   | 主动显示 AI 小鲸窗口。                                                                                                           |
| `handleStop()`        | -                                            | `void`   | 停止当前正在进行的 AI 内容生成（流式输出）。                                                                                      |
| `sendChat(options)`   | `options: ChatOptions`                       | `void`   | 发送消息到 AI 小鲸，可用于编程式触发对话或模拟快捷操作。详细参数及用法参见 [编程式控制指南](/guide/advanced-usage/programmatic-control#主动发送消息-sendchat)。 |
| `handleShortcutClick` | `shortcut: ShortCut`                         | `void`   | (内部方法，通常由组件内部调用) 处理快捷操作点击的逻辑，但也可被外部调用以模拟点击。                                                 |

## `ChatOptions` 类型 (用于 `sendChat`)

```typescript
interface ChatOptions {
  message?: string;   // 发送的消息文本
  cite?: string;      // 引用的文本内容
  shortcut?: ShortCut; // (可选) 模拟的快捷操作对象，ShortCut 类型定义见 [Props](./props.md#shortcut-对象格式)
}
```

## 调用示例

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="show">Show</button>
  <button @click="stop">Stop</button>
  <button @click="send">Send Custom Message</button>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking, { type AIBluekingInstance } from '@blueking/ai-blueking';

const aiBlueking = ref<AIBluekingInstance | null>(null);
const apiUrl = '...';

const show = () => aiBlueking.value?.handleShow();
const stop = () => aiBlueking.value?.handleStop();
const send = () => {
  aiBlueking.value?.sendChat({ message: 'Hello from code!' });
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="show">Show</button>
    <button @click="stop">Stop</button>
    <button @click="send">Send Custom Message</button>
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';

export default {
  components: { AIBlueking },
  data: () => ({ apiUrl: '...' }),
  methods: {
    show() { this.$refs.aiBlueking.handleShow(); },
    stop() { this.$refs.aiBlueking.handleStop(); },
    send() {
      this.$refs.aiBlueking.sendChat({ message: 'Hello from code!' });
    }
  }
};
</script>
```
:::