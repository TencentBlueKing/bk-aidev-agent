# 模型选择

::: tip 默认行为（≥ v2.2.2）
`enableModelSelect` 默认为 `true`。初始化时并行拉取 `GET llms/`；列表非空时在输入框发送按钮左侧展示 ModelSelector。拉取失败不阻断初始化。
:::

AI 小鲸支持在对话时热切换可用模型。选中态由 [`ModelSelectionManager`](/api/ai-blueking/managers#modelselectionmanager) 持有（`ChatBusinessManager` 委托），发送消息时通过 `agent.chat` 第 6 个参数传入 `llm_code`。

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
| 跟随 session | 切换历史会话时，用 `session.model` 同步 ModelSelector（命中可用列表时） |
| 写回 | 用户切换模型 → `ModelSelectionManager.persistSessionModel`（`session.model` 唯一写回出口） |
| 新建 | 所有建会话路径（含初始化 `loadRecentSession`）统一经 `resolveModelForSession`：优先当前选中 / preferred，校验落在可用列表内；`enableModelSelect=false` 时不强制写 `model` |
| 空列表 | 启用模型选择但无可用模型 → 抛 `ModelUnavailableError`，阻断建会话并上报 `sdk-error`（`apiName: session`） |
| 首次 / 兜底 | `session.model` 命中列表 → 选中；空/未知且无有效选中 → `property.default` / 首项 |
| 附件按钮 | 常驻开启；不再跟随选中模型 `property.support_vision` 或快捷指令 `supportUpload.vision` |

选中优先级：

```
1. 切换会话且 session.model 命中列表 → 采用
2. 已有有效选中 → 保持
3. property.default / 列表首项 → 采用
```

时序约束：若存在 `sessionModule` 但 `current` 尚未就绪，**不会**先落 default，避免挡住后续的 `session.model`。

## 数据流

```
[首次挂载]
runAgentBootstrap → getAgentInfo + getSessions + getLlms（可选）
loadRecentSession → current.model 可能就绪
ModelSelectionManager.loadModels / setModels
applySessionModel(session.model)
selectedModelName → ChatContainer ModelSelector

[运行时]
用户选模型 A → persistSessionModel 写回当前 session.model
  → 切历史会话 B → applySessionModel(B.model)
  → 新建会话 → resolveModelForSession 写入合法 model
  → chat_completion(model=当前 llm_code)
```

## Props

`AIBlueking` / `ChatBot` 均支持：

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enableModelSelect` | `boolean` | `true` | 是否启用模型选择；为 `true` 时 bootstrap 拉取 `GET llms/` |
| `models` | `ILlmItem[] \| IModelOption[]` | — | 外部模型列表；有值时跳过内部拉取 |

详见 [AIBlueking Props](/api/ai-blueking/aiblueking#功能开关)、[ChatBot Props](/api/ai-blueking/chatbot#功能开关)。

## ChatBusinessManager / ModelSelectionManager API

模型状态由 `ModelSelectionManager` 持有；`ChatBusinessManager` 仍暴露同名 getter / 方法并委托给它。

```typescript
// 响应式状态（ChatBusinessManager 与 ModelSelectionManager 相同）
chatBusinessManager.models;            // Ref<ILlmItem[]>
chatBusinessManager.selectedLlmCode;   // Ref<string | undefined>
chatBusinessManager.selectedModelName; // ComputedRef<string>
chatBusinessManager.isModelsLoading;   // Ref<boolean>

// 方法
await chatBusinessManager.loadModels();           // 拉取 / 复用 agent.models
chatBusinessManager.setModels(list);              // 外部注入
chatBusinessManager.setSelectedModel(item);       // 按 ILlmItem 选中并写回 session
chatBusinessManager.setSelectedModelByName(name); // 按 llm_name 选中并写回 session

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

- [会话管理](/guide/core-features/session-management) — `ISession.model` 跟随会话并写回
- [初始化生命周期](/guide/internals/chat-bootstrap) — bootstrap 并行拉取模型列表
- [ChatBusinessManager](/api/ai-blueking/managers#chatbusinessmanager) / [ModelSelectionManager](/api/ai-blueking/managers#modelselectionmanager)
- [Agent 模块](/api/chat-helper/sdk#agent-模块)
