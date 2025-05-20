# 预设对话内容

:::warning
注意， 最后一个支持此功能的版本为 v0.5.6，在最新版本中被移除。从 v1.0.0-beta.9 开始，不再支持通过 `defaultMessages` 属性预设对话内容。请使用 Agent 配置中的开场白和预设问题功能来替代。
:::

## 功能变更说明

在之前的版本中，AI 小鲸组件支持通过 `defaultMessages` 属性预设初始对话内容。从 v1.0.0-beta.9 开始，此功能已被移除，取而代之的是通过 Agent 配置，小鲸内部集成，不需要额外配置任何内容。

这种基于 Agent 配置的方式带来以下优势：

- 配置集中管理，不需要在每个组件实例中重复定义
- 与后端保持同步，确保体验一致性

## 如何迁移

如果您之前使用了 `defaultMessages` 属性，请按照以下步骤迁移：

1. 移除组件中的 `:default-messages` 属性
2. 在 Agent 配置中设置开场白和预设问题

```diff
<template>
  <AIBlueking
    :url="apiUrl"
-   :default-messages="defaultMessages"
  />
</template>

<script>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-url.com/chat';
- const defaultMessages = ref([
-   { role: 'user', content: '请介绍蓝鲸平台' },
-   { role: 'ai', content: '蓝鲸（BlueKing）是腾讯推出的一站式...' },
-   // ...更多预设消息
- ]);
</script>
``` 



## 通过 Agent 配置设置对话内容

在 Agent 配置中，您可以设置以下内容来替代原有的预设对话功能：

1. **开场白**：智能体的首次问候语
2. **预设问题**：用户可以快速选择的预设问题

这些配置在 Agent 创建或编辑时进行设置，无需在前端代码中指定。

## 如何获取当前会话内容

如果您需要在外部访问当前会话内容，可以使用 `sessionContents` 属性：

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
  />
  <button @click="saveCurrentSession">保存当前会话</button>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const aiBlueking = ref();
const apiUrl = 'https://your-api-url.com/chat';

const saveCurrentSession = () => {
  // 获取当前会话内容
  const currentMessages = aiBlueking.value.sessionContents;
  // 保存到服务器或本地存储
  localStorage.setItem('saved-session', JSON.stringify(currentMessages));
};
</script>
```

通过以上方法，您可以继续灵活地管理AI对话会话的状态，并实现更丰富的用户体验。 