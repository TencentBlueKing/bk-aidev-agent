# 预设对话内容

:::warning
从 v1.0.0 版本开始，不再支持通过 `defaultMessages` 属性预设对话内容。请使用 Agent 配置中的开场白和预设问题功能来替代。最后一个支持此功能的版本为 v0.5.6。
:::

## 功能变更说明

在 v0.5.6 及之前的版本中，AI 小鲸组件支持通过 `defaultMessages` 属性预设初始对话内容。从 v1.0.0 开始，此功能已被移除，取而代之的是通过 Agent 配置内置的方式，小鲸内部集成，不需要额外配置任何内容。

这种基于 Agent 配置的方式带来以下优势：

- 配置集中管理，不需要在每个组件实例中重复定义
- 与后端保持同步，确保体验一致性
- 支持实时更新，无需重新部署前端应用

## 如何迁移

如果您之前使用了 `defaultMessages` 属性，请按照以下步骤迁移：

1. 移除组件中的 `:default-messages` 属性
2. 在 Agent 配置中设置开场白和预设问题
3. 确保您的 AI-SDK 版本与组件版本匹配

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

1. **开场白（`openingRemark`）**：智能体的首次问候语，显示在对话开始时
2. **预设问题（`predefinedQuestions`）**：用户可以快速选择的预设问题，会与前端配置的`prompts`属性合并显示

这些配置在 Agent 创建或编辑时在平台进行设置，无需在前端代码中指定。系统会在组件初始化时自动获取这些配置。

## 1.0版本初始化流程

在1.0版本中，组件的初始化流程如下：

1. 组件挂载后，通过`url`属性指定的地址获取智能体配置
2. 配置获取成功后，自动应用开场白（`openingRemark`）作为初始问候
3. 将智能体配置中的预设问题（`predefinedQuestions`）与前端的`prompts`属性合并显示
4. 组件完成初始化，用户可以开始对话

这种方式确保了前端组件与后端智能体配置的一致性，提供更加统一的用户体验。

## 如何获取和管理当前会话内容

从1.0版本开始，组件实例暴露了`sessionContents`属性，用于获取当前会话内容：

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
import { AIBlueking } from '@blueking/ai-blueking';

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

`sessionContents`属性返回一个包含当前会话所有消息的数组，每个消息对象的结构如下：

```typescript
interface Message {
  role: 'user' | 'assistant'; // 消息发送者角色
  content: string;           // 消息文本内容
  cite?: string;             // 可选，引用的文本内容
  time?: number;             // 消息时间戳
}
```

通过访问`sessionContents`属性，您可以实现以下功能：

- 保存当前会话状态
- 分析对话内容
- 导出对话记录
- 实现自定义的会话管理逻辑

请注意，`sessionContents`属性是只读的，不支持直接修改会话内容。如需管理会话，请使用组件提供的方法（如`handleSendMessage`等）。 