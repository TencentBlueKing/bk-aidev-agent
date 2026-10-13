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
  // 仅断开前端 SSE；stopChat 会通知后端停止生成，勿在卸载时调用
  chatHelper.agent.abortChat();
});
```

当前 `AGUIProtocol` **没有** `destroy()` 方法；卸载以 `abortChat` 中止请求为主。

## 可运行示例

[示例 · 原子组件组装](/demos/atomic-assembly) 内嵌一个完整的原子组装对话区：代码页签展示组件全文，请求页签可以看到 `session_content/` 与 `chat_completion/`（AG-UI SSE）。示例连接文档站内置的 Mock，真实 `urlPrefix` 请对接网关。

## 网关需要提供的接口（按能力选用）

接入下列能力时，网关需提供与 SDK 路径、字段约定一致的接口（具体前缀由 `urlPrefix` 拼接）：

- `POST session_content/`：发送前写入用户消息（`createAndPlusMessage`）
- `POST session_content/batch_delete/`：批量删除（body `{ ids: string[] }`，**仅 user 消息 id**；SDK 会乐观更新并移除对应轮次）
- `POST chat_completion/`：流式通道（SSE，事件格式见 [AG-UI 流式](#ag-ui-流式单轮回复的事件顺序)）
- `POST session_content/stop/`：停止生成（`stopChat`）
- `GET session_feedback/reasons/?rate=`、`POST session_feedback/`：点赞 / 点踩反馈（可选）
- 分享：`POST share/`（由你在多选确认后调用 `message.shareMessages`，见 [分享（多选模式）](#分享多选模式)）

分享的端到端请求由业务侧发起：示例中点击「分享」只进入**多选模式**，便于对照实现。

## 工具栏二次开发：MessageContainer 回调 ↔ HTTP ↔ chat-helper

`MessageContainer` 通过 **props 回调**处理「复制 / 引用 / 重新生成 / 删除 / 分享 / 点赞点踩」；**不要**再使用已废弃的 `@cite` 等事件。

| 工具 `tool.id` | 回调 | 推荐实现（可与内置 ChatBot 行为对齐） | 后端接口（路径以网关为准） |
| -------------- | ---- | -------------------------------------- | -------------------------- |
| `cite` | `onAgentAction` / `onUserAction` | 拼文本写入输入区 `v-model:cite`，`ChatInput` `ref.focus()` | 无（纯前端） |
| `rebuild` | `onAgentAction` | `agent.abortChat()` 后 **`agent.resendMessage(userMessageId, sessionCode)`** | `session_content/batch_delete/`、`session_content/`、`chat_completion/` |
| `delete`（助手条） | `onAgentAction` | 找到本轮 user 后 **`message.deleteMessages([user, ...aiGroup])`** | `session_content/batch_delete/` |
| `delete`（用户气泡） | `onUserAction` | 从该 user 起到下一条 user 前 **`message.deleteMessages([user, ...ai])`** | 同上 |
| `share` | `onAgentAction` | **`enable-selection`** + **`v-model:selected-user-messages`**，确认后 **`message.shareMessages(...)`** | `POST share/` |
| `like` / `unlike` | `onAgentAction` 返回原因；`onAgentFeedback` 提交 | `getSessionFeedbackReasons(rate)`；`postSessionFeedback({ sessionCode, sessionContentIds, rate, labels, comment })`，userId 可用 **`findLastUserMessageIdBefore(list, aiGroup[0])`** | `session_feedback/reasons/`、`session_feedback/` |

`postSessionFeedback` 经 SDK 转为 snake_case（如 `session_code`、`session_content_ids`、`rate`、`labels`、`comment`）；若网关字段与蓝鲸标准不一致，可用请求拦截器或自建 HTTP 层适配。

## 分享（多选模式）

与 **ChatBot 独立模式**一致：用户点助手条「分享」后，先进入 **selection mode**，勾选多轮对话，再携带选中的 **user 消息**调用分享接口。

1. **`MessageContainer`**：`enable-selection` 置为 `true`（示例在 `onAgentAction` 且 `tool.id === 'share'` 时打开）。
2. **选中数据**：`v-model:selected-user-messages="selectedUserMessages"`（用户消息数组；组件会将同一轮的助手区域与用户勾选联动高亮）。
3. **退出多选**：将 `enable-selection` 置回 `false` 并清空 `selectedUserMessages`（示例提供「退出多选」）。
4. **发起分享**：在用户确认后调用 **`chatHelper.message.shareMessages(sessionCode, selectedUserMessages)`**（底层为 `POST share/`，body 含 `session_code`、`content_ids` 等，由 SDK 从 user 消息提取 `id`）。若使用蓝鲸 **AI 小鲸**完整封装，还可配合头部按钮、`request-share` 等与宿主页协作。

## AG-UI 流式：单轮回复的事件顺序

SSE 每行 `data: <json>\n\n`，`type` 为字符串（如 `TEXT_MESSAGE_CHUNK`）。AG-UI 事件由 `AGUIProtocol` 自动解析，详见 [聊天交互](/guide/core-features/chat-interaction)。

| 顺序 | `type`               | 必填字段                                | `AGUIProtocol` 侧行为（摘要）                          |
| ---- | -------------------- | --------------------------------------- | ------------------------------------------------------ |
| 1    | `RUN_STARTED`        | `runId`（number）、`threadId`（string） | 默认可忽略                                             |
| 2    | `TEXT_MESSAGE_START` | `messageId`、`role`（如 `assistant`）   | 新建一条流式中的助手消息                               |
| 3    | `TEXT_MESSAGE_CHUNK` | `messageId`、`delta`                    | 追加文本；可多条                                       |
| 4    | `TEXT_MESSAGE_END`   | `messageId`                             | 将该条标为完成                                         |
| 5    | `RUN_FINISHED`       | `runId`、`threadId`                     | 收尾仍在 loading 的助手消息（双保险）                  |

说明：仅发 **`TEXT_MESSAGE_START` + `TEXT_MESSAGE_CHUNK` × N + `RUN_FINISHED`** 也可工作；加上 **`TEXT_MESSAGE_END`** 语义更清晰。更多事件类型详见 [聊天交互 - AG-UI 事件类型](/guide/core-features/chat-interaction#ag-ui-事件类型)。

生产环境实现 SSE 时，请注意**逐块写出**与**背压**（连接中断、慢客户端），避免一次性缓冲整段再推送导致首字延迟过大。

## 与旧文档的常见差异

| 误区                                      | 说明                                                        |
| ----------------------------------------- | ----------------------------------------------------------- |
| `useChatHelper({ url })`                  | 应为 `requestData: { urlPrefix, ... }`                      |
| `new AGUIProtocol({ baseURL })`           | 构造函数只有 `onStart` / `onMessage` / `onDone` / `onError` |
| `chatHelper.message.sendMessage` 直接聊天 | 标准路径是 `agent.chat`（用户消息 + SSE）                   |
| `MessageContainer` 的 `@cite`             | 使用 `onAgentAction` 等 **props 回调**（见 chat-x）         |

## 延伸阅读

- [架构概览](/guide/architecture) — chat-x / chat-helper / ai-blueking 边界
- [自定义请求](/guide/advanced-usage/custom-requests) — `requestData`、拦截器
- [聊天交互](/guide/core-features/chat-interaction) — `AGUIProtocol`、AG-UI 事件类型、流式响应
- [chat-helper SDK API](/api/chat-helper/sdk) — [`useChatHelper`](/api/chat-helper/sdk)、`EventType` 等完整接口
