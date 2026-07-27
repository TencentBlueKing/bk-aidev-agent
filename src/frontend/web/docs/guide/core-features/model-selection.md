# 模型选择

::: tip 默认行为
`enableModelSelect` 默认为 `true`。初始化时并行拉取 `GET llms/`；列表非空时在输入框发送按钮左侧展示 ModelSelector。拉取失败不阻断初始化。
:::

AI 小鲸支持在对话时热切换可用模型。选中态由 [`ChatBusinessManager`](/api/ai-blueking/managers#chatbusinessmanager) 持有，发送消息时通过 `agent.chat` 第 6 个参数传入 `llm_code`。

## 快速使用

默认开启，无需额外配置：

```vue
<template>
  <AIBlueking url="/api/ai" />
  <!-- 或 -->
  <ChatBot url="/api/ai" />
</template>
```

关闭模型选择：

```vue
<AIBlueking url="/api/ai" :enable-model-select="false" />
```

使用外部模型列表（有值时跳过内部 `GET llms/`）：

```vue
<script setup lang="ts">
import type { ILlmItem } from '@blueking/ai-blueking';

const models: ILlmItem[] = [
  {
    id: 1,
    llm_code: 'hy3-preview',
    llm_name: '混元预览',
    llm_type: 'chat.completion',
    max_token_size: 128000,
    property: { default: true },
    space_auth_mode: '',
    user_auth_mode: '',
  },
];
</script>

<template>
  <ChatBot url="/api/ai" :models="models" />
</template>
```

## 行为约定

| 行为 | 说明 |
| --- | --- |
| 展示条件 | `enableModelSelect !== false` 且模型列表非空 |
| 选中值展示 | ModelSelector 绑定 `llm_name`；发送使用 `llm_code` |
| 跨 session | 选中态在组件实例生命周期内跨会话保持；切历史 / 新建 / 复用空会话**不会**改变当前选中 |
| 首次兜底 | 仅在尚无有效选中时：`session.model`（且在列表中）→ `property.default` → 列表首项 |
| 写回 | 用户切换模型**不**写回 session；创建会话请求也不带 `model` |
| 刷新 | 重新挂载后实例重置，可再次走首次兜底 |

选中优先级（仅「当前无有效选中」时解析）：

```
1. 已有有效 _selectedLlmCode → 保持
2. current?.model 且在 models 中 → 采用
3. property.default / 列表首项 → 采用
```

时序约束：若存在 `sessionModule` 但 `current` 尚未就绪，**不会**先落 default，避免挡住后续的 `session.model`。

## 数据流

```
[首次挂载]
runAgentBootstrap → getAgentInfo + getSessions + getLlms（可选）
loadRecentSession → current.model 可能就绪
ChatBusinessManager.loadModels / setModels
resolveInitialSelection()
  → session.model | default
selectedModelName → ChatContainer ModelSelector

[运行时]
用户选模型 A
  → 切历史会话 / 新建 / 复用空会话 → 仍为 A
  → chat_completion(model=A)
```

## Props

`AIBlueking` / `ChatBot` 均支持：

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enableModelSelect` | `boolean` | `true` | 是否启用模型选择；为 `true` 时 bootstrap 拉取 `GET llms/` |
| `models` | `ILlmItem[] \| IModelOption[]` | — | 外部模型列表；有值时跳过内部拉取 |

详见 [AIBlueking Props](/api/ai-blueking/aiblueking#功能开关)、[ChatBot Props](/api/ai-blueking/chatbot#功能开关)。

## ChatBusinessManager API

```typescript
// 响应式状态
chatBusinessManager.models;            // Ref<ILlmItem[]>
chatBusinessManager.selectedLlmCode;   // Ref<string | undefined>
chatBusinessManager.selectedModelName; // ComputedRef<string>
chatBusinessManager.isModelsLoading;   // Ref<boolean>

// 方法
await chatBusinessManager.loadModels();           // 拉取 / 复用 agent.models
chatBusinessManager.setModels(list);              // 外部注入
chatBusinessManager.setSelectedModel(item);       // 按 ILlmItem 选中
chatBusinessManager.setSelectedModelByName(name); // 按 llm_name 选中

// 发送时可覆盖本轮模型
await chatBusinessManager.sendMessage(content, sessionCode, {
  model: 'hy3-preview', // llm_code
});
```

## chat-helper：拉取与热切换

```typescript
const { agent } = chatHelper;

// 拉取可用模型（默认 llm_type=chat.completion），写入 agent.models
const list = await agent.getLlms({ llm_type: 'chat.completion' });

// 热切换：第 6 个参数为 llm_code（须在 GET llms/ 列表内）
await agent.chat(userInput, sessionCode, undefined, undefined, property, 'hy3-preview');
```

自定义请求参数请走第 4 个参数 `config.data`（如 `temperature`），**不要**再把 `model` 塞进 `config.data`。

类型见 [`ILlmItem`](/api/chat-helper/types#illmitem)、[`IModelOption`](/api/chat-x/types#imodeloption)。

## UI 层（chat-x）

`ChatContainer` / `ChatInput` 透传：

- `:models` — 可选模型列表
- `v-model:selected-model` — 当前选中的 `llm_name`
- `@model-change` — `(model: IModelOption) => void`

原子组装时可直接使用 [`ModelSelector`](/api/chat-x/components#modelselector)。

## 相关文档

- [会话管理](/guide/core-features/session-management) — `ISession.model` 仅作首次兜底
- [初始化生命周期](/guide/internals/chat-bootstrap) — bootstrap 并行拉取模型列表
- [ChatBusinessManager](/api/ai-blueking/managers#chatbusinessmanager)
- [Agent 模块](/api/chat-helper/sdk#agent-模块)
