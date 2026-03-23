# 原子组件组装

当 `ChatBot` 或 `AIBlueking` 无法满足定制化需求时，可以直接使用 `@blueking/chat-x` 的原子 UI 与 `@blueking/chat-helper` 的 SDK 组装业务，获得最大的布局与交互自由度。

## 适用场景

- 需要非标准布局（左右分栏、嵌入复杂页面等）
- 需要替换默认输入区、消息气泡、工具栏等行为
- 需要将对话能力与现有状态管理深度整合

## 何时不应使用

原子模式需要**自行**完成初始化、生命周期与状态映射，复杂度高。若只需嵌入聊天窗口或完整面板，优先：

- [ChatBot 页面嵌入模式](./chatbot-embedded.md)
- [AIBlueking 浮窗模式](./aiblueking-floating.md)

## 组装步骤（与 chat-helper 当前 API 对齐）

### 1. 创建 `AGUIProtocol` 与 `useChatHelper`

[`AGUIProtocol`](/guide/core-features/chat-interaction#流式响应) 构造函数**仅**接收可选回调（`onStart` / `onMessage` / `onDone` / `onError`），**不要**传入 `baseURL`。HTTP 基址放在 `requestData.urlPrefix`。

```ts
import { AGUIProtocol, useChatHelper } from '@blueking/chat-helper';

const protocol = new AGUIProtocol({
  onError: (err) => console.error(err),
});

const chatHelper = useChatHelper({
  requestData: {
    urlPrefix: 'https://your-api.example/api/',
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  },
  protocol,
});
```

### 2. 注入消息模块（必须）

在首次发起流式请求前调用（建议在 `onMounted` 内、`getAgentInfo` 之前亦可）：

```ts
protocol.injectMessageModule(chatHelper.message);
```

`AGUIProtocol` 依赖 `IMessageModule` 将 `TEXT_MESSAGE_*` 等事件落到消息列表；遗漏会导致流式内容无法显示。

### 3. 初始化会话

```ts
await chatHelper.agent.getAgentInfo();
await chatHelper.session.getSessions();

const first = chatHelper.session.list.value[0];
if (first?.sessionCode) {
  await chatHelper.session.chooseSession(first.sessionCode);
} else {
  await chatHelper.session.createSession(
    { sessionCode: `new_${Date.now()}`, sessionName: '新会话' },
    { loadMessages: false },
  );
}
```

注意：会话列表字段为 `session.list`，切换会话为 `chooseSession`，**不是** `sessions` / `switchSession`。

### 4. 连接 chat-x 组件

- 使用 `chatHelper.message.list` 作为 `MessageContainer` 的 `messages`
- 用 `chatHelper.agent.isChatting` 映射 `MessageStatus` / `MessageToolsStatus`（与 ChatBot 内部 composable 逻辑一致）
- 发送消息使用 **`chatHelper.agent.chat(content, sessionCode, ...)`**，由 SDK 负责创建用户消息并打开 SSE；不要与旧文档中的 `message.sendMessage` 混淆

`MessageContainer`、`ChatInput` 的交互以 **props 回调** 为准（如 `onAgentAction`、`onSendMessage`），不是早期示例里的 `@cite` / `@send` 等自定义事件。

### 5. 卸载清理

```ts
import { onBeforeUnmount } from 'vue';

onBeforeUnmount(() => {
  const code = chatHelper.session.current.value?.sessionCode;
  chatHelper.agent.abortChat();
  if (code) void chatHelper.agent.stopChat(code);
});
```

当前 `AGUIProtocol` **没有** `destroy()` 方法；以中止请求 + 可选 `stopChat` 为主。

## 可运行示例与 Mock

[原子组件组装示例](/demos/atomic-assembly) 内嵌演示**不模拟**小鲸初始化接口，仅 Mock `session_content` + `chat_completion`（AG-UI SSE），用于验证流式解析与 chat-x 渲染；真实 `urlPrefix` 请对接网关（如 `BK_API_GATEWAY_NAME` 等环境变量）。

## 延伸阅读

- [架构概览](/guide/architecture) — chat-x / chat-helper / ai-blueking 边界
- [自定义请求](/guide/advanced-usage/custom-requests) — `requestData`、拦截器
- [聊天交互](/guide/core-features/chat-interaction) — `AGUIProtocol`、AG-UI 事件类型、流式响应
- [chat-helper SDK API](/api/chat-helper/sdk) — [`useChatHelper`](/api/chat-helper/sdk)、`EventType` 等完整接口
