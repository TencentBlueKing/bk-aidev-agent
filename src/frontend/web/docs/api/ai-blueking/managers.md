# 业务管理器

AI 小鲸的业务逻辑通过多个 Manager 类进行管理，各 Manager 职责单一、协作明确。本文档介绍各管理器的 API。

## ComponentManager

中央事件协调器，负责组件间的事件通信。所有 Manager 和组件通过 `ComponentManager` 进行解耦通信。

### 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `on` | `(event: InternalEvent, handler: Function) => void` | 注册事件监听 |
| `off` | `(event: InternalEvent, handler: Function) => void` | 移除事件监听 |
| `emit` | `(event: InternalEvent, ...args: any[]) => void` | 触发事件 |

### 事件类型

通过 `InternalEvent` 枚举定义，常用事件包括：

```typescript
enum InternalEvent {
  // 消息相关
  SendMessage = 'send-message',
  StopGeneration = 'stop-generation',
  ReceiveStart = 'receive-start',
  ReceiveText = 'receive-text',
  ReceiveEnd = 'receive-end',

  // 会话相关
  SessionSwitched = 'session-switched',
  SessionCreated = 'session-created',
  SessionDeleted = 'session-deleted',

  // 快捷指令
  ShortcutClick = 'shortcut-click',
  ShortcutSelect = 'shortcut-select',

  // UI 状态
  SelectionModeChanged = 'selection-mode-changed',

  // 错误
  Error = 'error',
}
```

### 用法示例

```typescript
import { ComponentManager } from '@blueking/ai-blueking';

const manager = new ComponentManager();

// 监听消息发送
manager.on(InternalEvent.SendMessage, (message: string) => {
  console.log('消息已发送:', message);
});

// 触发事件
manager.emit(InternalEvent.SendMessage, '你好');
```

## ChatBusinessManager

聊天业务管理器，封装消息发送、停止生成、模型选择等核心聊天逻辑。

### 构造函数

```typescript
new ChatBusinessManager(agentModule, sessionModule, chatbotInit)
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `agentModule` | `AgentModule` | chat-helper 的 Agent 模块 |
| `sessionModule` | `SessionModule` | chat-helper 的 Session 模块 |
| `chatbotInit` | `ChatbotInit` | 聊天机器人初始化配置 |

### 响应式状态

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `models` | `Ref<ILlmItem[]>` | 可用模型列表（供 ChatContainer ModelSelector） |
| `isModelsLoading` | `Ref<boolean>` | 模型列表加载中 |
| `selectedLlmCode` | `Ref<string \| undefined>` | 当前选中模型的 `llm_code`（发送时透传） |
| `selectedModelName` | `ComputedRef<string>` | 当前选中模型的 `llm_name`（绑定 `v-model:selected-model`） |

### 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `sendMessage` | `(content: string, sessionCode: string, options?: SendMessageOptions) => void` | 发送消息；`options.model` 可覆盖本轮 `llm_code` |
| `stopGeneration` | `(sessionCode: string) => void` | 停止当前会话的生成 |
| `loadModels` | `(options?: { force?: boolean }) => Promise<void>` | 拉取可用模型；已有 `agent.models` 时复用；失败不抛出（空列表） |
| `setModels` | `(models: ILlmItem[]) => void` | 使用外部模型列表（跳过接口拉取） |
| `setSelectedModel` | `(model: ILlmItem \| null \| undefined) => void` | 按模型选项设置选中（`@model-change`） |
| `setSelectedModelByName` | `(llmName: string) => void` | 按展示名设置选中（ModelSelector `v-model` 为 `llm_name`） |

### 用法示例

```typescript
// 发送消息（自动携带当前选中模型）
chatBizManager.sendMessage('帮我写一个排序算法', currentSession.sessionCode);

// 覆盖本轮模型
chatBizManager.sendMessage('解释这段代码', sessionCode, {
  model: 'hy3-preview',
  property: { extra: { command: 'explain-code' } },
});

// 停止生成
chatBizManager.stopGeneration(currentSession.sessionCode);

// 模型列表与选中
await chatBizManager.loadModels();
chatBizManager.setSelectedModelByName('混元预览');
```

::: tip 模型选择语义
选中态跨 session 保持；仅在尚无有效选中时用 `session.model` / default 兜底。详见 [模型选择](/guide/core-features/model-selection)。
:::

## SessionBusinessManager

会话业务管理器，封装会话的增删改查及切换逻辑。

### 构造函数

```typescript
new SessionBusinessManager(sessionModule, messageModule, agentModule?, options?)
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `sessionModule` | `SessionModule` | chat-helper 的 Session 模块 |
| `messageModule` | `MessageModule` | chat-helper 的 Message 模块 |
| `agentModule` | `AgentModule` | chat-helper 的 Agent 模块（可选） |
| `options` | `object` | 配置选项（可选） |

### 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `createNewSession` | `() => Promise<ISession>` | 创建新会话 |
| `switchSession` | `(code: string) => Promise<void>` | 切换到指定会话 |
| `deleteSession` | `(code: string) => Promise<void>` | 删除指定会话 |
| `batchDeleteSessions` | `(codes: string[]) => Promise<void>` | 批量删除会话 |
| `renameSession` | `(code: string) => Promise<void>` | 重命名会话 |
| `loadRecentSession` | `(options?: object) => Promise<void>` | 加载最近会话 |

### 响应式属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `sessionList` | `Ref<ISession[]>` | 会话列表 |
| `currentSession` | `Ref<ISession \| null>` | 当前会话 |

### 用法示例

```typescript
// 创建新会话
const session = await sessionBizManager.createNewSession();

// 切换会话
await sessionBizManager.switchSession('session-abc-123');

// 删除会话
await sessionBizManager.deleteSession('session-abc-123');

// 批量删除
await sessionBizManager.batchDeleteSessions(['session-1', 'session-2']);

// 重命名
await sessionBizManager.renameSession('session-abc-123');

// 加载最近会话
await sessionBizManager.loadRecentSession({ autoSwitch: true });
```

## ShortcutManager

快捷指令管理器，负责快捷指令的获取、过滤和选择。

### 构造函数

```typescript
new ShortcutManager(agentModule)
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `agentModule` | `AgentModule` | chat-helper 的 Agent 模块 |

### 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `getShortcuts` | `() => IShortcut[]` | 获取全部快捷指令 |
| `filterShortcuts` | `(keyword: string) => IShortcut[]` | 根据关键词过滤快捷指令 |
| `selectShortcut` | `(shortcut: IShortcut, text?: string) => void` | 选择快捷指令并可选填充文本 |

### 响应式属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `shortcuts` | `Ref<IShortcut[]>` | 全部快捷指令列表 |
| `filteredShortcuts` | `Ref<IShortcut[]>` | 过滤后的快捷指令列表 |

### 用法示例

```typescript
const shortcutManager = new ShortcutManager(agentModule);

// 获取全部快捷指令
const allShortcuts = shortcutManager.getShortcuts();

// 过滤
const filtered = shortcutManager.filterShortcuts('代码');

// 选择快捷指令
shortcutManager.selectShortcut(shortcut, '请帮我优化这段代码');
```

## UIStateManager

UI 状态管理器，管理组件层面的全局 UI 状态，如多选模式。

### 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `enableSelectionMode` | `() => void` | 启用多选模式 |
| `disableSelectionMode` | `() => void` | 禁用多选模式 |

### 响应式属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `isSelectionMode` | `Ref<boolean>` | 当前是否处于多选模式 |

### 用法示例

```typescript
const uiManager = new UIStateManager();

// 进入多选模式（如分享场景）
uiManager.enableSelectionMode();

// 退出多选模式
uiManager.disableSelectionMode();

// 监听状态
watch(uiManager.isSelectionMode, (val) => {
  console.log('多选模式:', val);
});
```

## ShareBusinessManager

分享业务管理器，负责消息分享相关的业务逻辑。

### 构造函数

```typescript
new ShareBusinessManager(messageModule, sessionModule)
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `messageModule` | `MessageModule` | chat-helper 的 Message 模块 |
| `sessionModule` | `SessionModule` | chat-helper 的 Session 模块 |

### 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `shareMessages` | `(messages: Message[]) => Promise<{ shareUrl: string; userMessageIds: string[] }>` | 分享选中的消息，返回分享链接和用户消息 ID 列表 |

### 用法示例

```typescript
const shareManager = new ShareBusinessManager(messageModule, sessionModule);

// 分享消息
const { shareUrl, userMessageIds } = await shareManager.shareMessages(selectedMessages);
console.log('分享链接:', shareUrl);
```
