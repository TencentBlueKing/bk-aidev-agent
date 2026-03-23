# 原子组件组装

当 **ChatBot**、**AIBlueking** 等封装形态不满足产品形态时，可以直接使用 **`@blueking/chat-x`**（界面与交互）与 **`@blueking/chat-helper`**（会话、消息、流式协议）自行拼装。这一层与具体「小鲸」产品解耦，更适合做深度定制。

## 为什么原子层更适合二次开发

- **协议导向**：流式侧采用 **AG-UI** 事件模型（与 `chat-helper` 内置的 `AGUIProtocol` 一致）。只要网关按约定提供 **REST + SSE**，即可驱动 `MessageContainer` 渲染，不绑定某一种固定产品后台。
- **按需集成**：`ChatBot` / `AIBlueking` 会在初始化阶段拉取智能体信息、会话列表等；原子组装则**由你决定**要不要这些能力——可以只做「单会话 + 发消息 + 流式回复」，也可以逐步加上会话管理、分享、反馈等。
- **行为可扩展**：消息工具栏（引用、重新生成、删除、分享、反馈等）通过 **`MessageContainer` 的 props 回调**交给业务实现，便于对接自有网关字段与权限模型。

下面的**在线示例**展示一条常见路径：[`useChatHelper`](/api/chat-helper/sdk) + [`AGUIProtocol`](/guide/core-features/chat-interaction#流式响应) + `agent.chat` → 用户消息落库 → `chat_completion` **SSE 按 AG-UI 推流**。你在业务里把 `requestData.urlPrefix` 指到自己的网关即可；示例页面在文档站内会走一套 **Mock 前缀**（仅用于演示，npm 包本身不包含该 Mock）。示例采用与文中 **`::: code-group`**（Vue 2 / Vue 3）相同的 **Tab 切换**：默认在 **「在线演示」**，点击 **「源码 (Vue)」** 即可在同一块区域内查看经 **Shiki** 高亮的 **`AtomicAssemblyDemo.vue`** 全文，并支持一键复制。主题内提供可复用组件 **`DemoCodeGroup`**，其他演示页也可按需套用。

### 与 chat-helper 对齐时需准备的接口（按能力选用）

接入下列能力时，网关需提供与 SDK 路径、字段约定一致的接口（具体前缀由 `urlPrefix` 拼接）：

- `POST session_content/`：发送前写入用户消息（`createAndPlusMessage`）
- `POST session_content/batch_delete/`：批量删除（body `{ ids: string[] }`，**仅 user 消息 id**；SDK 会乐观更新并移除对应轮次）
- `POST chat_completion/`：流式通道（SSE，事件格式见下文）
- `POST session_content/stop/`：停止生成（`stopChat`）
- `GET session_feedback/reasons/?rate=`、`POST session_feedback/`：点赞 / 点踩反馈（可选）
- 分享：`POST share/`（由你在多选确认后调用 `message.shareMessages`，见下节）

**分享**不在此做端到端 Mock：示例里点击「分享」只进入**多选模式**，便于你对照实现；真正发请求在业务侧完成。

### 分享（多选模式）怎么接

与 **ChatBot 独立模式**一致：用户点助手条「分享」后，先进入 **selection mode**，勾选多轮对话，再携带选中的 **user 消息**调用分享接口。

1. **`MessageContainer`**：`enable-selection` 置为 `true`（示例在 `onAgentAction` 且 `tool.id === 'share'` 时打开）。
2. **选中数据**：`v-model:selected-user-messages="selectedUserMessages"`（用户消息数组；组件会将同一轮的助手区域与用户勾选联动高亮）。
3. **退出多选**：将 `enable-selection` 置回 `false` 并清空 `selectedUserMessages`（示例提供「退出多选」）。
4. **发起分享**：在用户确认后调用 **`chatHelper.message.shareMessages(sessionCode, selectedUserMessages)`**（底层为 `POST share/`，body 含 `session_code`、`content_ids` 等，由 SDK 从 user 消息提取 `id`）。若使用蓝鲸 **AI 小鲸**完整封装，还可配合头部按钮、`request-share` 等与宿主页协作。

### 工具栏二次开发：MessageContainer 回调 ↔ HTTP ↔ chat-helper

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

<ClientOnly>
  <AtomicAssemblyDemo />
</ClientOnly>

## AG-UI 流式（与 chat-helper 一致）

SSE 每行 `data: <json>\n\n`，`type` 为字符串（如 `TEXT_MESSAGE_CHUNK`）。AG-UI 事件由 `AGUIProtocol` 自动解析，详见 [聊天交互](/guide/core-features/chat-interaction)。

### 单轮普通文本回复：推荐事件顺序

| 顺序 | `type`               | 必填字段                                | `AGUIProtocol` 侧行为（摘要）                          |
| ---- | -------------------- | --------------------------------------- | ------------------------------------------------------ |
| 1    | `RUN_STARTED`        | `runId`（number）、`threadId`（string） | 默认可忽略                                             |
| 2    | `TEXT_MESSAGE_START` | `messageId`、`role`（如 `assistant`）   | 新建一条流式中的助手消息                               |
| 3    | `TEXT_MESSAGE_CHUNK` | `messageId`、`delta`                    | 追加文本；可多条                                       |
| 4    | `TEXT_MESSAGE_END`   | `messageId`                             | 将该条标为完成                                         |
| 5    | `RUN_FINISHED`       | `runId`、`threadId`                     | 收尾仍在 loading 的助手消息（双保险）                  |

说明：仅发 **`TEXT_MESSAGE_START` + `TEXT_MESSAGE_CHUNK` × N + `RUN_FINISHED`** 也可工作；加上 **`TEXT_MESSAGE_END`** 语义更清晰。更多事件类型详见 [聊天交互 - AG-UI 事件类型](/guide/core-features/chat-interaction#ag-ui-事件类型)。

生产环境实现 SSE 时，请注意**逐块写出**与**背压**（连接中断、慢客户端），避免一次性缓冲整段再推送导致首字延迟过大。

## 推荐集成思路

1. **`useChatHelper({ requestData: { urlPrefix, headers? }, protocol })`**，`protocol` 使用 **`AGUIProtocol`**。
2. **`protocol.injectMessageModule(chatHelper.message)`**，再绑定 **`MessageContainer`** / **`ChatInput`**。
3. 若使用 **ChatBot / AIBlueking**：按产品说明完成智能体信息、会话列表等初始化。
4. 若采用 **原子组装 + 自有 Agent**：只要网关满足上述 REST/SSE 约定，可自行决定是否实现会话列表；发送侧使用 **`agent.chat(content, sessionCode, ...)`**（先写用户消息，再建立流式连接）。

```ts
const protocol = new AGUIProtocol({ onError: (e) => console.error(e) })
const chatHelper = useChatHelper({
  requestData: { urlPrefix: `${import.meta.env.VITE_YOUR_API_PREFIX}/` },
  protocol,
})

onMounted(() => {
  protocol.injectMessageModule(chatHelper.message)
  // 按需：getAgentInfo / getSessions / chooseSession …
})
```

## 与旧文档的常见差异

| 误区                                      | 说明                                                        |
| ----------------------------------------- | ----------------------------------------------------------- |
| `useChatHelper({ url })`                  | 应为 `requestData: { urlPrefix, ... }`                      |
| `new AGUIProtocol({ baseURL })`           | 构造函数只有 `onStart` / `onMessage` / `onDone` / `onError` |
| `chatHelper.message.sendMessage` 直接聊天 | 标准路径是 `agent.chat`（用户消息 + SSE）                   |
| `MessageContainer` 的 `@cite`             | 使用 `onAgentAction` 等 **props 回调**（见 chat-x）         |

更完整的模式说明见 [指南：原子组件组装](/guide/integration-modes/atomic-composition)。
