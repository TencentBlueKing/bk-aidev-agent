# 界面定制

AI 小鲸提供了一些选项来定制其外观和行为。

## 窗口拖拽与缩放

AI 小鲸的对话窗口默认支持拖拽移动位置和调整大小。用户可以通过拖动窗口标题栏来移动窗口，通过拖动窗口的边缘或右下角来改变窗口尺寸。这是组件的内置功能，无需额外配置。

## 初始最小化状态

您可以通过 `defaultMinimize` prop 控制 AI 小鲸窗口在首次加载或通过 `handleShow` 方法显示时是否处于最小化状态。

-   `defaultMinimize` (Boolean): 默认值为 `false`。如果设置为 `true`，窗口初始将是最小化状态。

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :default-minimize="true"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :default-minimize="true"
  />
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
      apiUrl: 'https://your-api-endpoint.com/assistant/'
    };
  }
};
</script>
```
:::
