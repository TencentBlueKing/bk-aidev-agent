# 常见问题

## 1. ChatBot 和 AIBlueking 有什么区别？

**ChatBot** 是纯聊天组件，只包含消息列表和输入框，适合嵌入到已有页面中。

**AIBlueking** 是包含悬浮球（Nimbus）、拖拽、划词选择等功能的完整面板，适合作为独立的 AI 助手窗口使用。

简单来说：ChatBot 是"聊天框"，AIBlueking 是"聊天面板 + 交互增强"。

---

## 2. 如何选择集成模式？

根据业务场景选择：

| 场景 | 推荐方案 |
| --- | --- |
| 快速嵌入现有页面 | ChatBot |
| 需要悬浮球、拖拽等完整交互 | AIBlueking |
| 深度定制 UI 和交互逻辑 | 原子组件（ChatInput + MessageContainer） |

---

## 3. protocol.injectMessageModule() 是什么？

`protocol.injectMessageModule()` 是原子模式下的必须调用，它将消息管理模块注入到 `AGUIProtocol` 中，让流式响应的消息数据能正确写入消息列表。

```ts
onMounted(() => {
  protocol.injectMessageModule(chatHelper.message);
});
```

如果忘记调用，流式消息将无法显示在界面上。ChatBot 和 AIBlueking 内部已自动处理，无需手动调用。

---

## 4. 为什么 receive-* 事件没有触发？

`receive-start`、`receive-end` 等事件**仅在独立模式**（不传 `chatHelper`）下触发。

在集成模式中，这些事件由 `useChatBootstrap` 的 `protocolCallbacks` 处理：

```ts
const { chatHelper, protocol } = useChatHelper({
  url: '/api/',
  protocolCallbacks: {
    onReceiveStart: () => console.log('开始接收'),
    onReceiveEnd: () => console.log('接收完成'),
    onError: (error) => console.error('错误:', error),
  },
});
```

---

## 5. 如何在 Vue 2 中使用？

需要先安装 `@vue/composition-api`：

```bash
npm install @vue/composition-api
```

然后在入口文件中注册：

```ts
import Vue from 'vue';
import VueCompositionAPI from '@vue/composition-api';
Vue.use(VueCompositionAPI);
```

组件导入方式与 Vue 3 相同，使用 Options API 或 Composition API 均可。

---

## 6. requestOptions 的 headers 为什么是函数？

函数形式确保**每次请求时获取最新的 token**，避免 token 过期问题。

```ts
// ✅ 推荐：函数形式，每次请求时调用
const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};

// ❌ 不推荐：对象形式，token 会被固定
const requestOptions = {
  headers: { Authorization: `Bearer ${token}` },
};
```

如果 token 有效期很长且不会变化，也可以使用对象形式。

---

## 7. 如何自定义消息工具栏？

通过 `MessageContainer` 的回调属性处理工具栏按钮逻辑：

- `onAgentAction(action, message)` — 处理 AI 消息的工具按钮（复制、重试等）
- `onAgentFeedback(type, message, reason)` — 处理 AI 消息的反馈（点赞/点踩）
- `onUserAction(action, message)` — 处理用户消息的工具按钮（编辑等）

```ts
const handleAgentAction = (action: string, message: IMessage) => {
  switch (action) {
    case 'copy':
      navigator.clipboard.writeText(message.content);
      break;
    case 'retry':
      chatHelper.message.retryMessage(message.id);
      break;
  }
};
```

---

## 8. 如何获取 chatHelper 实例？

两种方式：

**方式一**：通过 ChatBot 的 expose 方法：

```ts
const chatBotRef = ref<ChatBotExpose>();
const helper = chatBotRef.value?.getChatHelper();
```

**方式二**：监听 `agent-info-loaded` 事件：

```ts
const onReady = (chatHelper: IChatHelper) => {
  // chatHelper 已就绪，可以进行操作
  console.log('会话列表:', chatHelper.session.list.value);
};
```

```vue
<ChatBot @agent-info-loaded="onReady" />
```

---

## 9. 消息的 property.extra 有什么用？

`property.extra` 用于传递额外上下文信息到后端，常见用途：

- **cite** — 引用文本内容
- **command** — 快捷指令标识
- **context** — 快捷指令的上下文数据

```ts
await chatHelper.message.sendMessage({
  content: '请审查这段代码',
  property: {
    extra: {
      cite: '被引用的文本内容',
      command: 'code-review',
      context: { language: 'JavaScript' },
    },
  },
});
```

后端可根据 `extra` 中的信息执行不同的处理逻辑。

---

## 10. 如何处理流式错误？

根据使用模式选择对应的错误处理方式：

**ChatBot 模式**：监听 `error` 事件：

```vue
<ChatBot url="/api/" @error="handleError" />
```

```ts
const handleError = (error: Error) => {
  console.error('请求错误:', error.message);
  // 显示错误提示
};
```

**AIBlueking 模式**：监听 `sdk-error` 事件：

```vue
<AIBlueking url="/api/" @sdk-error="handleSdkError" />
```

```ts
const handleSdkError = (data: { apiName: string; code: number; message: string; data: unknown }) => {
  console.error('SDK 错误:', data.apiName, data.message);
  // 显示错误提示
};
```

**原子组件模式**：在 `AGUIProtocol` 的 `onError` 回调中处理：

```ts
const { protocol } = useChatHelper({
  url: '/api/',
  protocolCallbacks: {
    onError: (error) => {
      console.error('流式错误:', error);
      // 自定义错误处理逻辑
    },
  },
});
```

常见的流式错误包括：网络断开、token 过期、服务端异常等。建议在错误处理中提供用户友好的提示信息。

---

## 如何让 AI 回复显示红色标题、背景高亮？

v2.1.4-beta.6 起，消息区**不解析任意 HTML**。请在 AIDev Agent **系统提示词**中要求模型使用蓝鲸行内富文本语法，例如：

```text
::bk{color=red; bold}标题:/bk::
::bk{background-color=yellow}重点:/bk::
```

完整语法、属性表与「撤离通知」类 LLM 提示词模板见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)。用户侧的 `/` 提示词 prop 可放提问模板，格式约束建议写在系统提示词中。
