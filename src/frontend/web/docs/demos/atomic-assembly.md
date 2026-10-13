---
aside: false
---

# 原子组件组装

当 **ChatBot**、**AIBlueking** 等封装形态不满足产品形态时，可以直接用 **`@blueking/chat-x`**（界面与交互）与 **`@blueking/chat-helper`**（会话、消息、流式协议）自行拼装。这一层与「小鲸」产品解耦，更适合深度定制：

- **协议导向**：流式侧采用 **AG-UI** 事件模型（与 `chat-helper` 内置的 `AGUIProtocol` 一致），网关按约定提供 REST + SSE 即可驱动 `MessageContainer`。
- **按需集成**：智能体信息、会话列表等初始化由你决定要不要；可以只做「单会话 + 发消息 + 流式回复」，再逐步加上会话管理、分享、反馈。
- **行为可扩展**：引用、重新生成、删除、分享、反馈等工具栏行为通过 `MessageContainer` 的 props 回调交给业务实现。

## 最小闭环

下面的对话区就是 `AtomicAssemblyDemo.vue` 本身：`useChatHelper` + `AGUIProtocol` + `agent.chat` → 写入用户消息 → `chat_completion` 按 AG-UI 推流。工具栏已接好引用、重新生成、成对删除、反馈；分享只演示进入多选模式。示例连接文档站内置的 Mock，你在业务里把 `requestData.urlPrefix` 指到自己的网关即可。

<ClientOnly>
  <RecipeAtomicAssembly />
</ClientOnly>

## 推荐集成思路

1. **`useChatHelper({ requestData: { urlPrefix, headers? }, protocol })`**，`protocol` 使用 **`AGUIProtocol`**。
2. **`protocol.injectMessageModule(chatHelper.message)`**，再绑定 **`MessageContainer`** / **`ChatInput`**。
3. 网关满足 REST / SSE 约定后，自行决定是否实现会话列表；发送使用 **`agent.chat(content, sessionCode, ...)`**（先写用户消息，再建立流式连接）。

## 相关文档

- [原子组件组装指南](/guide/integration-modes/atomic-composition)：组装步骤、网关接口清单、工具栏回调对照、分享多选、AG-UI 事件顺序
- [聊天交互](/guide/core-features/chat-interaction)：AG-UI 事件类型与流式响应
- [chat-x 组件 API](/api/chat-x/components) · [chat-helper SDK](/api/chat-helper/sdk)
