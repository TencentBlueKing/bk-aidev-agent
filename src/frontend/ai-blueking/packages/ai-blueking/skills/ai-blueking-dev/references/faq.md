# 常见问题与解决方案

## 初始化问题

### Q: 如何正确初始化 chatHelper？

**A**: 使用 `useChatHelper` 创建实例，确保在 `onMounted` 中初始化：

```typescript
const chatHelper = useChatHelper({
  requestData: {
    urlPrefix: '/api/',
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  },
  protocol: new AGUIProtocol({
    onStart: () => { isStreaming.value = true; },
    onDone: () => { isStreaming.value = false; },
    onError: (error) => { handleError(error); },
  }),
});

onMounted(async () => {
  await chatHelper.agent.getAgentInfo();
  await chatHelper.session.getSessions();
  // 选择或创建会话
});
```

### Q: 为什么消息列表没有更新？

**A**: 检查以下几点：

1. 确保使用 `computed` 包装响应式数据：
```typescript
// ✅ 正确
const messages = computed(() => message.list.value);

// ❌ 错误
const messages = message.list.value;
```

2. 确保在模板中正确绑定：
```vue
<MessageContainer :messages="messages" />
```

---

## 状态管理问题

### Q: messageStatus 应该怎么设置？

**A**: 基于 `agent.isChatting` 或流式状态计算：

```typescript
const isStreaming = ref(false);

// 在 Protocol 中更新
protocol: new AGUIProtocol({
  onStart: () => { isStreaming.value = true; },
  onDone: () => { isStreaming.value = false; },
});

// 计算 messageStatus
const messageStatus = computed(() =>
  isStreaming.value ? MessageStatus.Streaming : MessageStatus.Complete
);
```

### Q: 为什么发送按钮一直是禁用状态？

**A**: 检查 `messageStatus` 是否正确传递给 `ChatInput`：

```vue
<ChatInput
  :message-status="messageStatus"
  :on-send-message="handleSend"
/>
```

当 `messageStatus` 为 `Streaming` 时，发送按钮会变成停止按钮。

---

## 嵌入模式 / 侧栏

### Q: 为什么嵌入式 ChatBot 没有展开/收起侧栏的按钮？

**A**: 这是刻意的。浮窗（`AIBlueking`）的开关在 `AIHeader`；`ChatBot` 只负责聊天区，避免和业务布局抢 Header。嵌入页面时：

1. 自己画 Header：左侧会话名，右侧开关
2. `v-model:asideCollapsed`（不要只写 `:aside-collapsed`，否则文件卡片 / 自定义 Tab 的内部展开会失效）
3. 图标用 `@blueking/chat-x` 的 `CollapsedAsideIcon`（VNode，需 `cloneVNode`）

可运行样例：`playground/views/EmbeddedHeaderView.vue`。生产级：`publish-template/src/views/ChatWindow.vue`。详见 [集成模式](integration-patterns.md#嵌入式-chatbot业务-header--侧栏开关)。

### Q: `placement="left"` 为什么不生效？

**A**: 侧栏已固定从右侧展开，`ChatBot` / `AIBlueking` **已移除 `placement`**。请改用 `v-model:asideCollapsed`。

---

## 会话管理问题

### Q: 切换会话时消息没有清空？

**A**: 使用 `session.chooseSession` 而不是直接修改 `session.current`：

```typescript
// ✅ 正确：自动停止聊天、加载消息
await session.chooseSession(sessionCode);

// ❌ 错误：手动操作
session.current.value = newSession;
```

### Q: 如何判断会话是否有内容？

**A**: 使用 `sessionContentCount` 字段：

```typescript
const hasContent = (session.sessionContentCount ?? 0) > 0;

// 优化：空会话跳过消息加载
await session.chooseSession(sessionCode, { loadMessages: hasContent });
```

### Q: 创建会话后为什么消息列表不是空的？

**A**: `createSession` 默认 `loadMessages: false`，但如果之前有消息，需要手动清空：

```typescript
await session.createSession({ sessionCode, sessionName });
// message.list.value 会自动更新
```

---

## 工具操作问题

### Q: 如何区分不同的工具操作？

**A**: `IToolBtn` 为单一接口，`id` 为 `ToolIconsMap` 的 key（如 `copy`、`cite`、`delete`、`edit`、`like` 等）。按 `tool.id` 分支处理即可；**包内不再导出** `isBuiltinTool` / `isEditConfirmTool`。用户消息编辑确认由 `MessageContainer` 的 `onUserInputConfirm` / `onUserShortcutConfirm` 承接，而非通过带 `payload` 的 tool 类型。

```typescript
import { type IToolBtn } from '@blueking/chat-x';

const handleUserAction = async (tool: IToolBtn, message: Message) => {
  switch (tool.id) {
    case 'delete':
      await message.deleteMessages([message]);
      break;
    case 'edit':
      // 点击编辑后，组件内进入编辑态；确认时走 onUserInputConfirm / onUserShortcutConfirm
      break;
    case 'cite':
      // ...
      break;
    default:
      break;
  }
};
```

### Q: 点赞/点踩返回的原因列表怎么使用？

**A**: 在 `onAgentAction` 中返回字符串数组：

```typescript
const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
  if (tool.id === 'like') {
    // 返回点赞原因列表，组件会显示选择弹窗
    return ['回答准确', '信息全面', '解决了问题'];
  }
  if (tool.id === 'unlike') {
    return ['信息错误', '回答不相关', '内容重复'];
  }
};
```

---

## 引用功能问题

### Q: 如何实现引用功能？

**A**: 使用 `v-model:cite` 双向绑定：

```vue
<ChatInput
  v-model="userInput"
  v-model:cite="citeContent"
  :on-send-message="handleSend"
/>
```

在 `onAgentAction` 中设置引用内容：

```typescript
const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
  if (tool.id === 'cite') {
    citeContent.value = messages
      .filter(m => m.role !== 'reasoning')
      .map(m => m.content)
      .join('\n');
  }
};
```

---

## 快捷指令问题

### Q: 如何配置快捷指令？

**A**: 快捷指令可以从 Agent 信息获取或手动配置：

```typescript
// 从 Agent 获取
const shortcuts = computed(() => 
  agent.info.value?.conversationSettings?.commands || []
);

// 手动配置
const shortcuts = ref<Shortcut[]>([
  { id: 'translate', name: '翻译' },
  {
    id: 'explain',
    name: '解释',
    components: [
      {
        type: 'textarea',
        key: 'content',
        name: '内容',
        fillBack: true, // 自动填充选中文本
      },
    ],
  },
]);
```

### Q: 快捷指令表单的 fillBack 是什么？

**A**: `fillBack: true` 表示该字段会自动填充用户选中的文本：

```typescript
{
  type: 'textarea',
  key: 'content',
  name: '翻译内容',
  fillBack: true,  // 划词选择时自动填充
}
```

### Q: selectShortcut 和 sendShortcut 有什么区别？

**A**: `selectShortcut` 只显示表单，用户可编辑后再手动提交；`sendShortcut` 跳过表单直接发送消息。

```typescript
// 方式 1：显示表单，用户手动确认
chatBotRef.value.selectShortcut(command, selectedText);

// 方式 2：跳过表单，直接用默认值发送（等价旧版 handleShortcutClick(_, true)）
await chatBotRef.value.sendShortcut(command, selectedText);
```

`sendShortcut` 内部自动从 `command.components` 的 `default` 值构建 `formModel`，填充 `fillBack` 字段后直接发送。

---

## 执行情况侧面板问题

### Q: 如何关闭或自定义模型选择？

默认 `enableModelSelect: true`，初始化拉取 `GET llms/`，列表非空时展示 ModelSelector。

```vue
<!-- 关闭 -->
<AIBlueking url="/api/" :enable-model-select="false" />

<!-- 外部列表（跳过内部拉取） -->
<ChatBot url="/api/" :models="myModels" />
```

选中态跟随 session（切换写回 `updateSession`）；发送时 `agent.chat` 第 6 参传 `llm_code`。SDK 也可直接：

```typescript
await agent.getLlms();
await agent.chat(input, sessionCode, undefined, undefined, property, 'hy3-preview');
```

### Q: 如何控制执行情况侧面板的拖拽行为？

**A**: 通过 `resizeProps` 配置，该属性从 `AIBlueking` → `ChatBot` → `ChatContainer` 全链路透传至 `ResizeLayout`：

```vue
<AIBlueking
  :resize-props="{ min: 300, max: 600, initialDivide: 350 }"
  url="/api/"
/>

<!-- 或 ChatBot 独立模式 -->
<ChatBot
  :resize-props="{ disabled: true }"
  url="/api/"
/>
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `disabled` | `boolean` | 禁用拖拽调整 |
| `initialDivide` | `number` | 初始分割位置（px） |
| `max` | `number` | 最大宽度（px） |
| `min` | `number` | 最小宽度（px） |

### Q: 如何调整对话区域字号？

**A**: 通过 `size` 配置，该属性从 `AIBlueking` → `ChatBot` → `ChatContainer` 全链路透传：

```vue
<!-- 默认 small（12px）；normal 为 14px -->
<AIBlueking url="/api/" size="normal" />

<ChatBot url="/api/" size="normal" />
```

| 值 | 说明 |
|------|------|
| `small`（默认） | 12px 基准字号 |
| `normal` | 14px 基准字号 |

容器根节点设置 `data-ai-size`，并通过 `useGlobalConfig` 注入；浮层会同步到 `document.body.dataset.aiSize`。详见 [chat-x 字号主题](chat-x-api.md#字号主题size-theme)。

---

## ChatBot Composable 问题

### Q: 新增 ChatBot 功能应该放在哪个 composable？

**A**: 根据功能类型判断归属：

| 功能类型 | 归属 Composable |
|---------|----------------|
| 初始化/生命周期/Manager 创建 | `useChatbotInit` |
| HITL 中断恢复（审批/提问/节点重试跳过） | `useInterruptResume` |
| 计算属性/派生状态（effectiveXxx） | `useChatbotState` |
| 消息发送/输入框状态/上传 | `useMessageSender` |
| 快捷指令选择/fillBack/property 构建/直接发送 | `useShortcuts` |
| 工具栏操作（cite/rebuild/delete/like） | `useToolActions` |
| 分享/选择模式 | `useShareSelection` |
| 需要跨 composable 共享的 ref | `chat-bot.vue` 组装层创建并注入 |

### Q: 如何运行和编写测试？

**A**: 项目使用 vitest + happy-dom：

```bash
pnpm test          # 运行所有测试
pnpm test:watch    # 监听模式
```

测试 composable 时使用 mock 工厂和 `withSetup` 模式：

```typescript
import { createMockChatHelper, createMockEmit } from '../../../__tests__/helpers';
import { defineComponent } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';

function withSetup(fn: () => any) {
  let result: any;
  const wrapper = mount(defineComponent({
    setup() { result = fn(); return () => null; },
  }));
  return { result, wrapper };
}

it('should initialize', async () => {
  const { result, wrapper } = withSetup(() =>
    useChatbotInit({ props: { url: '/api/' }, emit: createMockEmit(), scrollToBottom: vi.fn() })
  );
  await flushPromises();
  expect(result.isInitialized.value).toBe(true);
  wrapper.unmount();
});
```

### Q: chat-bot.vue 的逻辑都在哪里？

**A**: 模板只组装 `ChatContainer`；业务拆到 8 个 composable，`chat-bot.vue` 的 `<script setup>` 负责接线：
1. 创建共享 ref（`selectedShortcut`、`internalEnableSelection`、`selectedResources`）
2. 定义辅助函数（`scrollToBottom`、`focusInput`）
3. 按依赖拓扑顺序调用 composable
4. 保留 `switchSession`、`setCiteText` 等简单辅助方法
5. `defineExpose` 暴露接口

组装顺序（依赖拓扑）：`useErrorReporter` → `useChatbotInit` → `useInterruptResume` → `useMessageSender` → `useShortcuts` → `useChatbotState` → `useToolActions` → `useShareSelection`

---

## 性能优化问题

### Q: 消息很多时页面卡顿怎么办？

**A**: 考虑以下优化：

1. **消息分页加载**：
```typescript
const loadMoreMessages = async () => {
  const oldestMsg = message.list.value[0];
  await message.getMessages(sessionCode, { before: oldestMsg?.messageId });
};
```

2. **虚拟滚动**：使用虚拟列表组件

3. **避免不必要的重渲染**：使用 `shallowRef`

### Q: Protocol 钩子中能做异步操作吗？

**A**: 不建议在钩子中 await，会阻塞后续事件处理：

```typescript
// ✅ 推荐：不阻塞
onMessage: (event) => {
  asyncOperation(); // 不 await
}

// ❌ 不推荐：阻塞
onMessage: async (event) => {
  await someAsyncOperation(); // 会阻塞
}
```

---

## 清理问题

### Q: 组件卸载时需要做什么清理？

**A**: 断开前端 SSE 即可，**不要**自动调 `stopChat`（会杀掉后台 agent）：

```typescript
onUnmounted(() => {
  agent.abortChat();
  agent.clearLongPollTimer?.();
});
```

用户主动点「停止」才走 `stopChat` / `stopGeneration`（只通知后端，不断开 SSE）。

---

## 调试技巧

### Q: 如何调试流式响应？

**A**: 在 Protocol 钩子中添加日志：

```typescript
protocol: new AGUIProtocol({
  onMessage: (event) => {
    console.log('Event:', event.type, event);
  },
  onError: (error) => {
    console.error('Stream Error:', error);
  },
});
```

### Q: 如何查看 API 请求详情？

**A**: 使用拦截器：

```typescript
interceptors: {
  request: (config) => {
    console.log('Request:', config.url, config.data);
    return config;
  },
  response: (response) => {
    console.log('Response:', response.data);
    return response;
  },
},
```

---

## 最佳实践检查清单

### 初始化

- [ ] 在 `onMounted` 中初始化 agent 和 session
- [ ] 有会话则选择第一个，无则创建
- [ ] 处理初始化错误

### 清理

- [ ] 在 `onUnmounted` 中调用 `agent.abortChat()`（勿自动 `stopChat`）
- [ ] 清理定时器和事件监听

### 状态管理

- [ ] 使用 `computed` 包装响应式数据
- [ ] 正确映射 `messageStatus`
- [ ] 使用枚举而非硬编码字符串

### 架构分层

- [ ] UI 逻辑在组件层
- [ ] 业务逻辑在 Manager 层
- [ ] 不在组件中直接调用 SDK API（通过 Manager）

### 错误处理

- [ ] 配置拦截器处理 API 错误
- [ ] 配置 `Protocol.onError` 处理流式错误
- [ ] 提供友好的错误提示

### 用户体验

- [ ] 发送后清空输入框
- [ ] 流式响应时显示停止按钮
- [ ] 自动滚动到最新消息
- [ ] 空会话显示快捷指令
