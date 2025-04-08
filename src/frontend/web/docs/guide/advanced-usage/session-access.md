# 访问会话内容

有时您可能需要从外部访问或记录 AI 小鲸当前的对话历史记录。AI 小鲸通过 `sessionContents` prop 将当前的会话内容暴露出来。

`sessionContents` 是一个数组，包含了当前对话的所有消息记录。每个消息对象通常包含角色（如 'user', 'assistant'）和内容（`content`）等信息。具体的结构取决于您的后端 AI 服务返回的数据格式以及组件内部的处理逻辑。

::: tip 提示
`sessionContents` 是一个响应式属性，它会随着对话的进行而更新。
:::

**示例：**

:::code-group
```vue [Vue 3]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="showSessionContents">显示/记录会话内容</button>
    <pre v-if="sessionLog.length">{{ sessionLog }}</pre>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking, { type AIBluekingInstance } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<AIBluekingInstance | null>(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
const sessionLog = ref<any[]>([]);

const showSessionContents = () => {
  if (aiBlueking.value?.sessionContents) {
    // 直接访问组件实例上的 sessionContents
    sessionLog.value = JSON.parse(JSON.stringify(aiBlueking.value.sessionContents)); // 深拷贝以显示快照
    console.log('当前会话内容:', aiBlueking.value.sessionContents);
    // 在这里可以将内容发送到日志服务或进行其他处理
  }
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="showSessionContents">显示/记录会话内容</button>
    <pre v-if="sessionLog.length">{{ sessionLog }}</pre>
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
      sessionLog: []
    };
  },
  methods: {
    showSessionContents() {
      if (this.$refs.aiBlueking?.sessionContents) {
        // 直接访问组件实例上的 sessionContents
        this.sessionLog = JSON.parse(JSON.stringify(this.$refs.aiBlueking.sessionContents)); // 深拷贝以显示快照
        console.log('当前会话内容:', this.$refs.aiBlueking.sessionContents);
        // 在这里可以将内容发送到日志服务或进行其他处理
      }
    }
  }
};
</script>
```
:::
