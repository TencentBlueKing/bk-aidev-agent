# 编程交互基础

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
| `focusInput()` | <Badge type="tip" text="v1.1.1" /> 程序式聚焦输入框 |

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

## 程序式聚焦输入框 (`focusInput`)

<Badge type="tip" text="v1.1.1" /> `focusInput` 方法允许您在特定时机主动聚焦到输入框，提升用户体验。

**方法签名:**

```typescript
focusInput(): void
```

**使用场景:**

1.  **在特定操作后自动聚焦到输入框**：例如在关闭快捷操作面板后自动聚焦到输入框
2.  **引导用户输入**：在页面加载或特定交互后引导用户进行输入

**示例:**

:::code-group
```vue [Vue 3]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="focusInput">聚焦输入框</button>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiBlueking = ref(null);
const apiUrl = '...';

const focusInput = () => {
  aiBlueking.value?.focusInput();
};
</script>
```
:::

## 访问会话内容

有时您可能需要从外部访问或记录 AI 小鲸当前的对话历史记录。AI 小鲸通过 `sessionContents` 属性将当前的会话内容暴露出来。

`sessionContents` 是一个数组，包含了当前对话的所有消息记录。每个消息对象通常包含角色（如 'user', 'assistant'）和内容（`content`）等信息。具体的结构取决于您的后端 AI 服务返回的数据格式以及组件内部的处理逻辑。

::: tip 提示
`sessionContents` 是一个响应式属性，它会随着对话的进行而更新。在多会话环境下，它始终反映当前活跃会话的内容。
:::

### 会话内容访问示例

:::code-group
```vue [Vue 3]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <div class="controls">
      <button @click="showSessionContents">显示当前会话内容</button>
      <button @click="checkLoadingState">检查加载状态</button>
      <button @click="getCurrentSessionInfo">获取会话信息</button>
    </div>
    <div v-if="sessionInfo" class="session-info">
      <h3>当前会话信息</h3>
      <p>加载状态: {{ sessionInfo.isLoading ? '加载中' : '已完成' }}</p>
      <p>消息数量: {{ sessionInfo.messageCount }}</p>
    </div>
    <pre v-if="sessionLog.length" class="session-log">{{ sessionLog }}</pre>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking, { type AIBluekingInstance } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<AIBluekingInstance | null>(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
const sessionLog = ref<any[]>([]);
const sessionInfo = ref<any>(null);

const showSessionContents = () => {
  if (aiBlueking.value?.sessionContents) {
    // 直接访问组件实例上的 sessionContents
    sessionLog.value = JSON.parse(JSON.stringify(aiBlueking.value.sessionContents)); // 深拷贝以显示快照
    console.log('当前会话内容:', aiBlueking.value.sessionContents);
    // 在这里可以将内容发送到日志服务或进行其他处理
  }
};

const checkLoadingState = () => {
  if (aiBlueking.value) {
    const isLoading = aiBlueking.value.isLoadingSessionContents;
    console.log('会话内容加载状态:', isLoading);
  }
};

const getCurrentSessionInfo = () => {
  if (aiBlueking.value) {
    sessionInfo.value = {
      isLoading: aiBlueking.value.isLoadingSessionContents || false,
      messageCount: aiBlueking.value.sessionContents?.length || 0,
      currentSessionLoading: aiBlueking.value.currentSessionLoading || false
    };
  }
};
</script>

<style scoped>
.controls {
  margin: 10px 0;
  display: flex;
  gap: 10px;
}

.session-info {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.session-log {
  background: #f8f8f8;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <div class="controls">
      <button @click="showSessionContents">显示当前会话内容</button>
      <button @click="checkLoadingState">检查加载状态</button>
      <button @click="getCurrentSessionInfo">获取会话信息</button>
    </div>
    <div v-if="sessionInfo" class="session-info">
      <h3>当前会话信息</h3>
      <p>加载状态: {{ sessionInfo.isLoading ? '加载中' : '已完成' }}</p>
      <p>消息数量: {{ sessionInfo.messageCount }}</p>
    </div>
    <pre v-if="sessionLog.length" class="session-log">{{ sessionLog }}</pre>
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
      sessionLog: [],
      sessionInfo: null
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
    },
    checkLoadingState() {
      if (this.$refs.aiBlueking) {
        const isLoading = this.$refs.aiBlueking.isLoadingSessionContents;
        console.log('会话内容加载状态:', isLoading);
      }
    },
    getCurrentSessionInfo() {
      if (this.$refs.aiBlueking) {
        this.sessionInfo = {
          isLoading: this.$refs.aiBlueking.isLoadingSessionContents || false,
          messageCount: this.$refs.aiBlueking.sessionContents?.length || 0,
          currentSessionLoading: this.$refs.aiBlueking.currentSessionLoading || false
        };
      }
    }
  }
};
</script>

<style scoped>
.controls {
  margin: 10px 0;
  display: flex;
  gap: 10px;
}

.session-info {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.session-log {
  background: #f8f8f8;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
```
:::

### 暴露的属性和方法

组件实例暴露的会话相关属性：

- `sessionContents`: 当前会话的消息内容数组
- `isLoadingSessionContents`: 会话内容是否正在加载
- `currentSessionLoading`: 当前是否有消息正在生成