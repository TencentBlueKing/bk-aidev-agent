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
| 快速嵌入现有页面（Vue 3） | ChatBot |
| 需要悬浮球、拖拽等完整交互（Vue 3） | AIBlueking |
| **宿主不是 Vue**（React、Angular、纯 HTML 等） | [`/standalone`](/guide/integration-modes/standalone-bundle) 子入口 + `mountAIBlueking` |
| 深度定制 UI 和交互逻辑 | 原子组件（ChatInput + MessageContainer） |

---

## 2.1. 非 Vue 页面如何接入小鲸？

自 **v2.1.4-beta.8** 起，使用 `@blueking/ai-blueking/standalone`：

```typescript
import { mountAIBlueking } from '@blueking/ai-blueking/standalone';
import '@blueking/ai-blueking/dist/standalone/style.css';

mountAIBlueking('#ai-root', {
  props: { url: 'https://your-aidev-url.com/api/' },
});
```

自定义 `getSideRenderComponent` 时请从 **同一入口** 导入 `h`，勿混用外部 `vue` 包。详见 [Standalone 非 Vue 宿主集成](/guide/integration-modes/standalone-bundle)。

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

v2.1.4-beta.9+ 在每次请求前通过 `resolveRequestValue` 求值，除零参函数外，也支持 **`ref` / `computed`** 与普通对象。函数或 `computed` 可在 token、租户切换后让**下一次请求**自动带上新值，无需重建组件。

```ts
import { computed, ref } from 'vue';

const token = ref(getToken());

// ✅ 推荐：computed / 函数，随 token 变化
const requestOptions = computed(() => ({
  headers: { Authorization: `Bearer ${token.value}` },
}));

// ✅ 亦可：函数形式
const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};

// ⚠️ 纯对象且 token 为 ref 时，需在对象内读 .value，或改用 computed
const requestOptionsStatic = {
  headers: { Authorization: `Bearer ${token.value}` }, // 仅捕获当前快照
};
```

`data` 会按方法写入 body 或 query，详见 [自定义请求](/guide/advanced-usage/custom-requests)。

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

**推荐（≥ v2.1.4-beta.13）**：先 `await whenReady()`，再 `getChatHelper()`：

```ts
const chatBotRef = ref<ChatBotExpose>();
await chatBotRef.value?.whenReady();
const helper = chatBotRef.value?.getChatHelper();
```

**方式一**：直接通过 expose（需自行保证初始化已完成）：

```ts
const helper = chatBotRef.value?.getChatHelper();
```

**方式二**：监听 `agent-info-loaded` 事件（独立模式，与 `whenReady` 成功时机一致）：

```ts
const onReady = (chatHelper: IChatHelper) => {
  console.log('会话列表:', chatHelper.session.list.value);
};
```

```vue
<ChatBot @agent-info-loaded="onReady" />
```

嵌入页等待就绪也可用 `isReady` 做模板条件渲染。`AIBlueking` 场景请用 `await show()`，见 [编程式控制](/guide/advanced-usage/programmatic-control)。

---

## 8.1. 如何关闭或自定义模型选择？

默认 `enableModelSelect` 为 `true`，初始化会拉取 `GET llms/`，列表非空时展示 ModelSelector。

```vue
<!-- 关闭 -->
<AIBlueking url="/api/ai" :enable-model-select="false" />

<!-- 外部传入列表（跳过内部拉取） -->
<ChatBot url="/api/ai" :models="myModels" />
```

选中态跨 session 保持，切换 / 新建会话不会改变当前模型；发送时携带 `llm_code`。详见 [模型选择](/guide/core-features/model-selection)。

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
// ≥ v2.1.4-beta.25：payload 新增 source 和 action 字段
const handleSdkError = (data: { apiName: string; code: number; message: string; data: unknown; source?: string; action?: string }) => {
  console.error('SDK 错误:', data.apiName, data.message, data.source);
  // 显示错误提示
};

// 禁用默认 toast，自行处理 UI 反馈
<AIBlueking :error-toast="false" @sdk-error="handleSdkError" />

// 忽略特定接口的错误 toast
<AIBlueking :ignore-errors="['/api/health', /session\/upload/]"] />
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
