# 架构设计原则

## 分层架构

AI 小鲸组件采用严格的分层架构，开发时必须遵循各层职责边界。

```
┌─────────────────────────────────────────────────────────────────┐
│                        应用层 (Application)                       │
│  ai-blueking.vue - 组装各子组件、门面模式                          │
├─────────────────────────────────────────────────────────────────┤
│                        组件层 (Components)                        │
│  ChatBot（composable 组装层）、AIHeader - UI 渲染、用户交互响应     │
├─────────────────────────────────────────────────────────────────┤
│                  ChatBot Composables (ChatBot 内部拆分)            │
│  useChatbotInit / useInterruptResume / useChatbotState           │
│  useMessageSender / useShortcuts / useToolActions / useShareSelection │
├─────────────────────────────────────────────────────────────────┤
│                     业务管理层 (Business Managers)                 │
│  SessionBusinessManager、ChatBusinessManager、ModelSelectionManager、ShareBusinessManager│
├─────────────────────────────────────────────────────────────────┤
│                      Composables (可复用逻辑)                      │
│  useChatBootstrap、useEventBridge - 组合式函数                     │
├─────────────────────────────────────────────────────────────────┤
│                         SDK 层 (SDK)                              │
│  @blueking/chat-helper - 数据管理、API 调用                        │
├─────────────────────────────────────────────────────────────────┤
│                         UI 组件层 (UI)                            │
│  @blueking/chat-x - 纯 UI 组件                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 层级职责

| 层级 | 位置 | 职责 | 禁止 |
|-----|------|------|------|
| **应用层** | `ai-blueking.vue` | 组装各子组件、门面模式 | 包含业务逻辑 |
| **组件层** | `components/` | UI 渲染、用户交互响应 | 直接调用 SDK API |
| **ChatBot Composables** | `components/composables/` | ChatBot 内部逻辑拆分，单一职责 | 跨 composable 隐式依赖 |
| **业务管理层** | `manager/business/` | 业务流程编排、副作用处理 | 管理 UI 状态 |
| **Composables** | `composables/` | 可复用的组合式逻辑 | 包含 UI 渲染 |
| **SDK 层** | `@blueking/chat-helper` | 数据管理、API 调用 | - |
| **UI 层** | `@blueking/chat-x` | 纯 UI 渲染 | 包含业务逻辑 |

## 数据流向

```
用户操作 → 组件层 → 业务管理层 → SDK 层 → 后端 API
              ↑                              ↓
              ←────── 响应式状态自动更新 ←──────
```

### 具体示例

**发送消息流程**：

```
1. 用户点击发送 → ChatInput.onSendMessage
2. ChatBot 调用 chatBusinessManager.sendMessage()
3. ChatBusinessManager 调用 agent.chat(..., property, selectedLlmCode)
4. chat-helper 发起 API 请求（chat_completion 携带 model=llm_code）
5. 流式响应 → Protocol 处理 → message.list 更新
6. MessageContainer 自动响应渲染
```

**会话切换流程**：

```
1. 用户选择会话 → AIHeader 触发事件
2. ai-blueking.vue 调用 sessionBusinessManager.switchSession()
3. SessionBusinessManager 调用 session.chooseSession()
4. chat-helper 停止当前聊天、加载新会话消息
5. ChatBot 自动更新显示
6. 模型选中：已有有效选中则保持；无有效选中时才 resolveInitialSelection()
```

**模型选择流程（≥ v2.2.2）**：

```
1. bootstrap：getLlms() 并行拉取（失败不阻断）
1. AIBlueking / ChatBot 初始化：ModelSelectionManager.ensureLoaded（复用 bootstrap 的 getLlms）
2. loadRecentSession / createNewSession → SessionBusinessManager.createSession
   → resolveModelForSession（保证落在可用列表；空列表抛 ModelUnavailableError）
3. ChatBusinessManager 委托同一 ModelSelectionManager；切换模型写回 persistSessionModel
4. ChatBot 绑定 models + v-model:selected-model → ChatContainer ModelSelector
5. 切 session → applySessionModel（仅 sessionCode 变化时）
6. chat(..., property, selectedLlmCode) 热切换
```

## 职责分离原则

### UI 逻辑 vs 业务逻辑

```typescript
// ✅ 正确：UI 逻辑在组件层
const doSendMessage = async (message: string) => {
  // UI 操作
  userInput.value = [[]];  // 清空输入框
  emit('send-message', message);  // 通知外部
  
  // 委托业务层
  await chatBusinessManager.sendMessage(message, sessionCode);
  
  // UI 操作
  scrollToBottom();
};

// ❌ 错误：业务逻辑泄露到组件层
const doSendMessage = async (message: string) => {
  await chatBusinessManager.sendMessage(message, sessionCode);
  
  // ❌ 自动重命名是业务逻辑，不应在组件层
  if (chatHelper.message.list.value.length === 1) {
    await chatHelper.session.renameSession(sessionCode);
  }
};
```

### 判断代码归属

| 代码行为 | 归属层级 |
|---------|---------|
| 清空输入框、滚动视图 | 组件层 |
| emit 事件通知父组件 | 组件层 |
| 发送消息、创建会话 | 业务管理层 |
| 消息发送后自动重命名 | 业务管理层 |
| API 调用、数据缓存 | SDK 层 |

## Business Manager 设计

### 依赖注入原则

Manager 通过构造函数注入所需的 SDK 模块，保持松耦合。

```typescript
// ✅ 正确：通过构造函数注入依赖
class ChatBusinessManager {
  constructor(
    agentModule: IAgentModule,
    messageModule: IMessageModule,
    sessionModule: ISessionModule | null = null,  // 可选依赖
    eventEmitter: IEventEmitter | null = null,
    config: ChatBusinessConfig = {},
  ) {
    this.agentModule = agentModule;
    this.messageModule = messageModule;
    this.sessionModule = sessionModule;
  }
}

// 实例化时注入
const chatBusinessManager = new ChatBusinessManager(
  chatHelper.agent,
  chatHelper.message,
  chatHelper.session,
  null,
  { openingRemark: props.helloText }
);
```

### 副作用处理

消息发送后的副作用（如自动重命名）应在 Manager 内部处理：

```typescript
class ChatBusinessManager {
  async sendMessage(content: string, sessionCode: string) {
    await this.agentModule.chat(content, sessionCode);
    
    // 副作用：自动重命名（异步执行，不阻塞）
    this.autoRenameSessionIfNeeded(sessionCode);
  }
  
  private autoRenameSessionIfNeeded(sessionCode: string): void {
    if (!this.sessionModule) return;
    if (this.messageModule.list.value.length !== 1) return;
    
    // 必须用 renameSession 的返回值（ai_rename 接口新名），不能只读 list/current：
    // current 常由 getSession 单独写入且不在分页 list 中，旧逻辑会 emit 改名前的名字
    this.sessionModule.renameSession(sessionCode)
      .then(renamed => {
        const newName = renamed?.sessionName;
        if (newName) {
          // 始终抛出含 sessionCode：切会话后业务仍可按 id 更新自己的列表；
          // AIBlueking Header 仅在 current 匹配时刷新标题
          this.config.onSessionRenamed?.(newName, sessionCode);
        }
      })
      .catch(error => {
        console.error('[ChatBusinessManager] Auto rename failed:', error);
      });
  }
}
```

## 跨包协作

### chat-x 与 chat-helper 的关系

| 包 | 职责 | 依赖关系 |
|---|-----|---------|
| `@blueking/chat-x` | 纯 UI 组件 | 不依赖 chat-helper |
| `@blueking/chat-helper` | 业务逻辑 SDK | 不依赖 chat-x |
| `ai-blueking` | 完整解决方案 | 依赖两者 |

### 修改优先级

```
1. 优先在 ai-blueking 层处理 → 业务逻辑、特定功能
2. 必要时修改 chat-x → 通用能力、类型扩展
3. 必要时修改 chat-helper → API 调用、状态管理
```

### 回调扩展模式

当需要从底层组件获取更多信息时，扩展回调签名：

```typescript
// chat-x: MessageContainer 扩展回调，传递 messages；点赞/点踩可返回 string[] 作为反馈原因列表
type AgentActionCallback = (tool: IToolBtn, messages: Message[]) => Promise<string[] | void>;

// ai-blueking: ChatBot 处理具体业务
const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
  if (tool.id === 'cite') {
    // 业务逻辑在 ai-blueking 层
    cite.value = messages.map(m => m.content).join('\n');
    focusInput();
    return;
  }
};
```

### 工具操作分层

| 操作 | 处理位置 | 原因 |
|-----|---------|------|
| copy | MessageContainer (chat-x) | 通用能力，无业务依赖 |
| cite | ChatBot (ai-blueking) | 需要操作输入框状态 |
| like/unlike | ChatBot (ai-blueking) | 需要调用业务 API |
| rebuild | ChatBot (ai-blueking) | 需要重新发送消息 |

## ChatBot 内部 Composable 架构

ChatBot (`chat-bot.vue`) 采用 composable 拆分模式：模板只组装 `ChatContainer`，`<script setup>` 负责接线（约 350 行），业务逻辑在 composable 中。

### 8 个 Composable 及职责

| Composable | 文件 | 职责 |
|------------|------|------|
| `useErrorReporter` | `components/composables/use-error-reporter.ts` | 统一错误出口：`toError` 归一化 + 按 Error 实例去重 + emit `error`；同时提供注入业务管理器的 `managerErrorBridge` |
| `useChatbotInit` | `components/composables/use-chatbot-init.ts` | Props 校验、chatHelper 创建/复用、Manager 实例化、onMounted/onBeforeUnmount 生命周期 |
| `useInterruptResume` | `components/composables/use-interrupt-resume.ts` | HITL 中断恢复编排（`handleInterruptResume`）：审批取消 / 用户提问作答 / 流程节点重试跳过，翻译成 `agent.streamRequest` / `agent.userOperationStreamRequest` |
| `useChatbotState` | `components/composables/use-chatbot-state.ts` | 所有 computed 属性（messageStatus、isWelcomeState、effectiveResources 等） |
| `useMessageSender` | `components/composables/use-message-sender.ts` | 输入状态 + 消息发送编排（doSendMessage、handleUpload、stopGeneration；发送时携带活跃 UserQuestion 中断的恢复负载） |
| `useShortcuts` | `components/composables/use-shortcuts.ts` | 快捷指令选择、fillBack、property 构建、表单提交、直接发送 |
| `useToolActions` | `components/composables/use-tool-actions.ts` | 所有消息工具栏交互（cite、rebuild、delete、share、like/unlike、编辑确认） |
| `useShareSelection` | `components/composables/use-share-selection.ts` | 选择模式状态 + 分享流程（独立模式用 ShareBusinessManager） |

### Composable 依赖关系

```
chat-bot.vue（组装层 — 创建共享 ref，按拓扑顺序组装）
│
│  共享 ref: selectedShortcut, internalEnableSelection, selectedResources
│  辅助函数: scrollToBottom(), focusInput()
│
├─ 0. useErrorReporter ───→ reportError, managerErrorBridge
│      (必须最先组装：其余所有 composable 都以 reportError 作为唯一错误出口)
│
├─ 1. useChatbotInit ─────→ chatHelper, chatBusinessManager, sessionBusinessManager, shortcutManager
│                             (创建/复用 chatHelper，实例化 Managers，管理生命周期，
│                              把 managerErrorBridge 注入两个业务管理器)
│
├─ 2. useInterruptResume ─→ handleInterruptResume
│      (HITL 恢复：翻译为 agent.streamRequest / userOperationStreamRequest)
│
├─ 3. useMessageSender ──→ userInput, cite, doSendMessage, stopGeneration
│      ↑ 接收 selectedShortcut ref
│
├─ 4. useShortcuts ───────→ selectShortcutWithText, buildShortcutProperty, getShortcutFromMessage, sendShortcutDirectly
│      ↑ 接收 doSendMessage 回调 + selectedShortcut ref（解决循环依赖）
│
├─ 5. useChatbotState ────→ messageStatus, messages, isWelcomeState, effectiveResources, ...
│      (纯 computed，无副作用)
│
├─ 6. useToolActions ─────→ handleAgentAction, handleUserAction, handleUserInputConfirm, ...
│      ↑ 接收 cite, focusInput, scrollToBottom, internalEnableSelection,
│        getShortcutFromMessage, buildShortcutProperty
│
└─ 7. useShareSelection ─→ selectedMessages, effectiveEnableSelection, handleConfirmShare, ...
       ↑ 接收 internalEnableSelection, messageContainerRef
       (独立模式内部使用 ShareBusinessManager 编排分享流程)
```

### 新增功能的归属判断

| 功能类型 | 归属 Composable | 示例 |
|---------|----------------|------|
| 初始化/生命周期 | `useChatbotInit` | 新的初始化步骤、清理逻辑 |
| 计算属性/派生状态 | `useChatbotState` | 新的 effectiveXxx 属性 |
| 消息发送/输入 | `useMessageSender` | 新的发送选项、输入变换 |
| 快捷指令 | `useShortcuts` | 新的 fillBack 逻辑、property 构建、直接发送 |
| 工具栏操作 | `useToolActions` | 新的 tool.id 处理分支 |
| 分享/选择模式 | `useShareSelection` | 新的分享渠道、选择策略 |
| HITL 中断恢复 | `useInterruptResume` | 新的中断类型、恢复操作映射 |
| 错误上报 | `useErrorReporter` | 新的错误来源接入、归一化规则 |
| 跨 composable | `chat-bot.vue` 组装层 | 新的共享 ref、辅助函数 |

> **错误处理约定**：composable 里的 `catch` 一律调用注入的 `reportError(error, '上下文描述')`，不要写 `console.error` + `emit('error', error as Error)`。`reportError` 已包含日志、`toError` 归一化、去重，以及（`errorToast !== false` 时）Message toast。

### 关键设计决策

1. **共享 ref 由组装层创建并注入**：`selectedShortcut` 被 `useMessageSender`（读 id 构建 extra）和 `useShortcuts`（写入选中状态）共同使用，由 `chat-bot.vue` 创建后传给两者。

2. **循环依赖解法**：`useShortcuts` 需要 `doSendMessage`（来自 `useMessageSender`），`useMessageSender` 需要 `selectedShortcut`。解法：先创建 `selectedShortcut` ref，传给 `useMessageSender`（ref 在赋值前即可传递），再将 `doSendMessage` 传给 `useShortcuts`。

3. **两条 resend 路径不合并**：
   - `handleUserInputConfirm` → `chatHelper.agent.resendMessage`（自动保留原 property）
   - `handleUserShortcutConfirm` → `chatBusinessManager.resendMessageWithProperty`（替换 property）

## 开发检查清单

### 开发新功能前

- [ ] 确认代码应该放在哪个层级
- [ ] 业务逻辑是否在 Manager 层
- [ ] UI 逻辑是否在组件层
- [ ] Manager 依赖是否通过构造函数注入
- [ ] 副作用是否在 Manager 内部处理

### 修改现有代码时

- [ ] 阅读相关架构文档了解整体设计
- [ ] 检查相关 Manager 是否已有类似功能
- [ ] 避免在组件层添加业务逻辑
- [ ] 新增依赖时使用依赖注入模式

### 修改 ChatBot 功能时

- [ ] 确认功能归属哪个 composable（参考"归属判断"表）
- [ ] 需要跨 composable 共享的 ref 必须在 `chat-bot.vue` 创建并注入
- [ ] 不在 composable 之间直接 import（通过参数注入解耦）
- [ ] 新增 composable 需更新 barrel export (`composables/index.ts`)
- [ ] 编写对应的单元测试

### 涉及 chat-x 修改时

- [ ] 优先考虑能否在 ai-blueking 层解决
- [ ] chat-x 修改需保持通用性和向后兼容
- [ ] 扩展回调签名时使用可选参数
- [ ] 需要暴露的方法通过 `defineExpose` 导出

### 运行时最佳实践

#### 初始化

- [ ] ChatBot 独立模式：确保 `url` 正确传入
- [ ] AIBlueking 模式：`useChatBootstrap` + `watch(isReady)` 初始化会话
- [ ] 处理初始化错误：ChatBot 独立模式监听 `@error`，AIBlueking 集成模式监听 `@sdk-error`（`apiName: 'init'`）

#### 清理

- [ ] `onBeforeUnmount` / URL 变化时调用 `agent.abortChat()`（只断前端 SSE）
- [ ] **不要**在自动清理路径调用 `stopChat`；`stopChat` 仅用户主动停止时使用

#### 状态管理

- [ ] 使用 `computed` 映射 `messageStatus`
- [ ] 流式响应时设置 `messageToolsStatus` 为 `MessageToolsStatus.Disabled`
- [ ] 使用枚举而非字符串

#### 架构分层

- [ ] UI 逻辑在组件层
- [ ] 业务逻辑在 Manager 层
- [ ] 不在组件中直接调用多步 SDK API
