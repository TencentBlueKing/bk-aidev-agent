# AI-Blueking V2 架构设计文档

## 1. 概述

### 1.1 背景

AI-Blueking（小鲸）V2 版本是对原有组件的完全重构，旨在解决 V1 版本存在的高度耦合、难以复用、维护困难等问题。

### 1.2 设计目标

| 目标         | 描述                                           |
| ------------ | ---------------------------------------------- |
| **低耦合**   | 各模块职责单一，通过事件系统通信，减少直接依赖 |
| **高内聚**   | 相关逻辑集中在同一模块，便于理解和维护         |
| **可复用**   | 核心组件（如 ChatBot）可独立使用，也可组合使用 |
| **易扩展**   | 通过 Manager 模式和事件系统便于添加新功能      |
| **类型安全** | 完整的 TypeScript 类型定义，编译时检查         |

### 1.3 技术栈

- **框架**: Vue 3 + Composition API
- **语言**: TypeScript
- **状态管理**: Vue Reactivity（ref/computed）
- **SDK**: @blueking/chat-helper（AG-UI SDK）
- **UI 组件**: @blueking/chat-x

---

## 2. 整体架构

### 2.1 分层架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              应用层 (Application Layer)                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         ai-blueking.vue                                │  │
│  │                    (主组件 - 组装层/门面模式)                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                              组件层 (Component Layer)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│
│  │ ChatBot     │  │ AIHeader    │  │ Draggable   │  │ Nimbus / Popup      ││
│  │ (核心聊天)   │  │ (头部组件)   │  │ Container   │  │ (悬浮球/选中弹窗)    ││
│  │             │  │             │  │ (拖拽容器)   │  │                     ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘│
├─────────────────────────────────────────────────────────────────────────────┤
│                              管理层 (Manager Layer)                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        ComponentManager                                  ││
│  │              (组件协调器 - UI 状态管理 + 统一事件系统)                      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐│
│  │ SessionBusiness   │  │ ChatBusiness      │  │ ShortcutManager           ││
│  │ Manager           │  │ Manager           │  │ (快捷方式管理)              ││
│  │ (会话业务管理)     │  │ (聊天业务管理)     │  │                           ││
│  └───────────────────┘  └───────────────────┘  └───────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        UIStateManager                                    ││
│  │                    (UI 状态管理 - 选择模式等)                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────────┤
│                            Composables 层                                    │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────────┐│
│  │     useChatBootstrap        │  │           useEventBridge                ││
│  │  (初始化流程编排)            │  │      (内部事件 → Vue emit 桥接)          ││
│  └─────────────────────────────┘  └─────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────────┤
│                              SDK 层 (SDK Layer)                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      @blueking/chat-helper                               ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │ AgentModule │  │SessionModule│  │MessageModule│  │  AGUIProtocol   │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
src/frontend/ai-blueking/src/v2/
├── index.ts                     # 统一导出入口
├── ai-blueking.vue              # 主组件（组装层）
├── types.ts                     # 全局类型定义
│
├── manager/                     # 管理器层
│   ├── index.ts                 # 管理器导出入口
│   ├── component-manager.ts     # 组件管理器（核心协调器）
│   ├── event-types.ts           # 统一事件类型系统
│   ├── types.ts                 # 管理器类型定义
│   │
│   ├── business/                # 业务管理器
│   │   ├── index.ts
│   │   ├── chat-business-manager.ts     # 聊天业务管理器
│   │   ├── session-business-manager.ts  # 会话业务管理器
│   │   ├── shortcut-manager.ts          # 快捷方式管理器
│   │   └── types.ts
│   │
│   └── ui/                      # UI 状态管理器
│       ├── index.ts
│       └── ui-state-manager.ts
│
├── composables/                 # Vue Composables
│   ├── index.ts
│   ├── use-chat-bootstrap.ts    # 聊天初始化 Composable
│   └── use-event-bridge.ts      # 事件桥接 Composable
│
├── components/                  # UI 组件
│   ├── index.ts
│   ├── types.ts
│   ├── chat-bot.vue             # ChatBot 核心聊天组件
│   └── ai-header/
│       └── index.vue            # AI Header 组件
│
├── containers/                  # 容器组件
│   ├── index.ts
│   ├── types.ts
│   ├── draggable-container.vue  # 可拖拽容器组件
│   └── use-draggable.ts         # 拖拽逻辑 Composable
│
├── config/                      # 配置
│   ├── index.ts
│   ├── prop-defaults.ts         # Props 默认值
│   └── protocol-config.ts       # Protocol 配置
│
├── examples/                    # 使用示例
│   ├── basic-usage.vue
│   ├── advanced-usage.vue
│   └── chatbot-embedded.vue
│
└── __tests__/                   # 单元测试
    ├── README.md
    ├── chat-business-manager.spec.ts
    ├── session-business-manager.spec.ts
    ├── ui-state-manager.spec.ts
    └── event-bridge.spec.ts
```

---

## 3. 核心模块设计

### 3.1 ComponentManager（组件管理器）

**职责**：

- UI 状态管理（面板可见性、Nimbus 最小化、拖拽状态、压缩状态）
- 统一事件系统（on/off/emit/once）
- 组件协调（协调各子组件之间的交互）

**核心 API**：

```typescript
class ComponentManager {
  // ==================== 状态访问器 ====================
  get panelVisible(): Ref<boolean>;
  get nimbusMinimized(): Ref<boolean>;
  get isCompressed(): Ref<boolean>;
  get isDraggingOrResizing(): Ref<boolean>;

  // ==================== 控制器 ====================
  get panel(): PanelController; // showPanel/hidePanel/togglePanel
  get nimbus(): NimbusController; // minimize/restore/toggle
  get container(): ContainerController; // updatePosition/updateSize/toggleCompression

  // ==================== 事件系统 ====================
  on<T extends InternalEvent>(event: T, callback: EventCallback<T>): () => void;
  once<T extends InternalEvent>(event: T, callback: EventCallback<T>): () => void;
  emit<T extends InternalEvent>(event: T, data: InternalEventData[T]): void;
  off<T extends InternalEvent>(event: T, callback?: EventCallback<T>): void;

  // ==================== 生命周期 ====================
  destroy(): void;
}
```

**设计原则**：

- 单一职责：只负责 UI 状态和事件协调，不处理业务逻辑
- 观察者模式：通过事件系统实现组件间松耦合通信
- 控制器模式：通过 panel/nimbus/container 控制器提供语义化 API

### 3.2 useChatBootstrap（初始化 Composable）

**职责**：

- 封装 ChatHelper 的完整初始化流程
- 管理初始化阶段状态
- 提供 Agent 信息、会话数据的响应式访问

**初始化阶段**：

```typescript
enum BootstrapPhase {
  IDLE = 'idle', // 未开始
  LOADING_AGENT = 'loading_agent', // 正在获取 Agent 信息
  LOADING_SESSION = 'loading_session', // 正在加载会话
  READY = 'ready', // 初始化完成
  ERROR = 'error', // 初始化失败
}
```

**核心 API**：

```typescript
function useChatBootstrap(options: ChatBootstrapOptions): {
  // 核心实例
  chatHelper: IChatHelper;
  protocol: AGUIProtocol;

  // 状态
  phase: Ref<BootstrapPhase>;
  isReady: ComputedRef<boolean>;
  error: Ref<Error | null>;

  // 数据
  agentInfo: ComputedRef<IAgentInfo | null>;
  agentName: ComputedRef<string>;
  currentSession: ComputedRef<ISession | null>;
  sessionList: ComputedRef<ISession[]>;

  // 方法
  initialize: () => Promise<void>;
  retry: () => Promise<void>;
  updateConfig: (newUrl: string) => Promise<void>;
};
```

**设计原则**：

- 同步创建 ChatHelper：生命周期内实例不变，避免响应式复杂性
- 阶段状态机：清晰的初始化状态转换
- 响应式 URL：支持 URL 变化时自动重新初始化

### 3.3 useEventBridge（事件桥接 Composable）

**职责**：

- 自动将 ComponentManager 的内部事件桥接到 Vue emit
- 提供事件转发方法（子组件事件 → Manager）
- 组件卸载时自动清理事件监听

**核心 API**：

```typescript
function useEventBridge(options: UseEventBridgeOptions): {
  forwardToManager: <T extends InternalEvent>(event: T, data: InternalEventData[T]) => void;
  emitDirect: (event: string, ...args: unknown[]) => void;
  cleanup: () => void;
};

// 辅助函数：创建预配置的事件转发器
function createEventForwarders(forwardToManager): EventForwarders;
```

**事件桥接映射**：

```typescript
const EVENT_BRIDGE_MAP = {
  // 内部事件 → Vue emit 事件（null 表示不对外暴露）
  'panel-show': 'show',
  'panel-hide': 'close',
  'send-message': 'send-message',
  'nimbus-click': null, // 内部事件，不对外暴露
  // ...
};
```

### 3.4 ChatBot（核心聊天组件）

**职责**：

- 渲染聊天消息列表
- 处理用户输入和消息发送
- 管理快捷方式选择
- 支持两种使用模式

**使用模式**：

| 模式         | 说明                    | 配置              |
| ------------ | ----------------------- | ----------------- |
| **独立模式** | 组件内部创建 chatHelper | 传入 `url`        |
| **集成模式** | 复用父组件的 chatHelper | 传入 `chatHelper` |

**Props 定义**：

```typescript
interface ChatBotProps {
  // 集成模式
  chatHelper?: IChatHelper;
  // 独立模式
  url?: string;
  // 通用配置
  placeholder?: string;
  sessionCode?: string;
  autoLoad?: boolean;
  shortcuts?: IShortcut[];
  shortcutLimit?: number;
  requestOptions?: IRequestOptions;
  height?: string | number;
  helloText?: string;
  prompts?: string[];
}
```

**Expose 方法**：

```typescript
interface ChatBotExpose {
  sendMessage(message: string): Promise<void>;
  stopGeneration(): void;
  switchSession(sessionCode: string): Promise<void>;
  messages: Ref<IMessage[]>;
  currentSession: Ref<ISession | null>;
  isGenerating: Ref<boolean>;
  getChatHelper(): IChatHelper | null;
  setCiteText(text: string): void;
  focusInput(): void;
}
```

### 3.5 业务管理器（Business Managers）

#### SessionBusinessManager

**职责**：封装会话业务流程，使用 AG-UI SDK 的 session 模块

```typescript
class SessionBusinessManager {
  // 响应式状态（来自 SDK）
  get sessionList(): Ref<ISession[]>;
  get currentSession(): Ref<ISession | null>;
  get isCurrentLoading(): Ref<boolean>;

  // 业务方法
  async createSession(options: CreateSessionOptions): Promise<void>;
  async switchSession(sessionCode: string): Promise<void>;
  async deleteSession(sessionCode: string): Promise<void>;
  async updateSessionName(sessionCode: string, name: string): Promise<void>;
  async loadSessions(): Promise<void>;
  async loadRecentSession(): Promise<void>;
}
```

#### ChatBusinessManager

**职责**：封装聊天业务流程，使用 AG-UI SDK 的 agent/message 模块

```typescript
class ChatBusinessManager {
  // 响应式状态
  get messages(): Ref<IMessage[]>;
  get isGenerating(): Ref<boolean>;
  get isMessagesLoading(): Ref<boolean>;

  // 业务方法
  async sendMessage(content: IUserMessage['content'], sessionCode: string, options?: SendMessageOptions): Promise<void>;
  stopGeneration(): void;
  async deleteMessage(messageId: number): Promise<void>;
}
```

---

## 4. 数据流设计

### 4.1 整体数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户操作                                        │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        子组件 (ChatBot/AIHeader/etc.)                    ││
│  │                                 │                                        ││
│  │                    emit event / call expose method                       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        ai-blueking.vue (主组件)                          ││
│  │                                 │                                        ││
│  │              forwardToManager() / componentManager.emit()                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        ComponentManager                                  ││
│  │                    (统一事件系统 + UI 状态管理)                            ││
│  │                                 │                                        ││
│  │              emit internal event / update UI state                       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                 │                                           │
│                    ┌────────────┴────────────┐                              │
│                    │                         │                              │
│                    ▼                         ▼                              │
│  ┌─────────────────────────┐   ┌─────────────────────────────────────────┐  │
│  │     useEventBridge      │   │        Business Managers                │  │
│  │  (内部事件 → Vue emit)   │   │   (SessionBusiness/ChatBusiness)       │  │
│  └─────────────────────────┘   └─────────────────────────────────────────┘  │
│                    │                         │                              │
│                    ▼                         ▼                              │
│  ┌─────────────────────────┐   ┌─────────────────────────────────────────┐  │
│  │    外部事件 (Vue emit)   │   │      AG-UI SDK (chat-helper)           │  │
│  │    供父组件监听          │   │   (agent/session/message modules)      │  │
│  └─────────────────────────┘   └─────────────────────────────────────────┘  │
│                                              │                              │
│                                              ▼                              │
│                              ┌─────────────────────────────────────────┐    │
│                              │         响应式状态更新                    │    │
│                              │    (Ref/Computed → UI 自动更新)          │    │
│                              └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 事件分类

| 类型             | 事件示例                                 | 说明                |
| ---------------- | ---------------------------------------- | ------------------- |
| **UI 事件**      | `panel-show`, `nimbus-click`, `dragging` | 界面交互产生的事件  |
| **业务事件**     | `send-message`, `session-switched`       | 业务操作产生的事件  |
| **Header 事件**  | `new-chat`, `history-click`, `rename`    | Header 组件特有事件 |
| **消息选择事件** | `transfer-messages`, `share-messages`    | 消息选择相关事件    |

### 4.3 事件桥接规则

- **对外暴露的事件**：通过 `EVENT_BRIDGE_MAP` 映射到 Vue emit
- **内部事件**：映射值为 `null`，仅在组件内部流转
- **事件数据转换**：通过 `transformEventDataToEmitArgs` 转换数据格式

---

## 5. 组件使用模式

### 5.1 完整模式（AIBlueking）

适用于需要完整功能（悬浮球、拖拽、弹窗等）的场景：

```vue
<template>
  <AIBlueking
    url="/api/ai"
    title="AI 助手"
    :shortcuts="shortcuts"
    :enable-popup="true"
    :draggable="true"
    @show="handleShow"
    @send-message="handleSendMessage"
  />
</template>

<script setup>
  import { AIBlueking } from '@/v2';

  const shortcuts = [{ id: 'explain', name: '解释代码', icon: 'bkai-icon bkai-code' }];
</script>
```

### 5.2 嵌入模式（ChatBot 独立使用）

适用于嵌入到其他页面的场景：

```vue
<template>
  <div class="chat-container">
    <ChatBot
      url="/api/ai"
      :shortcuts="shortcuts"
      :height="500"
      @send-message="handleSendMessage"
    />
  </div>
</template>

<script setup>
  import { ChatBot } from '@/v2';
</script>
```

### 5.3 集成模式（共享 ChatHelper）

适用于需要在多个组件间共享 ChatHelper 的场景：

```vue
<template>
  <AIBlueking
    :chat-helper="chatHelper"
    :enable-popup="true"
  />
</template>

<script setup>
  import { useChatBootstrap } from '@/v2';

  const { chatHelper, isReady } = useChatBootstrap({
    url: '/api/ai',
    autoInit: true,
  });
</script>
```

---

## 6. 扩展指南

### 6.1 添加新的业务管理器

1. 在 `manager/business/` 下创建新文件
2. 继承或实现 `IEventEmitter` 接口（可选）
3. 在 `manager/business/index.ts` 中导出
4. 在需要的组件中实例化使用

```typescript
// manager/business/new-feature-manager.ts
export class NewFeatureManager {
  private eventEmitter: IEventEmitter | null;

  constructor(eventEmitter: IEventEmitter | null = null) {
    this.eventEmitter = eventEmitter;
  }

  private emit(event: string, data: any): void {
    this.eventEmitter?.emit(event, data);
  }

  // 业务方法...
}
```

### 6.2 添加新的事件类型

1. 在 `manager/event-types.ts` 中定义事件类型
2. 添加到 `InternalEvent` 联合类型
3. 在 `InternalEventData` 中定义事件数据
4. 在 `EVENT_BRIDGE_MAP` 中配置桥接映射

```typescript
// 1. 定义事件名称
export type NewFeatureEvent = 'feature-action' | 'feature-complete';

// 2. 定义事件数据
export interface NewFeatureEventData {
  'feature-action': { actionId: string };
  'feature-complete': { result: unknown };
}

// 3. 添加到联合类型
export type InternalEvent = UIEvent | BusinessEvent | NewFeatureEvent;

// 4. 配置桥接映射
export const EVENT_BRIDGE_MAP = {
  // ...
  'feature-action': 'feature-action', // 对外暴露
  'feature-complete': null, // 内部事件
};
```

### 6.3 添加新的 Composable

1. 在 `composables/` 下创建新文件
2. 遵循 Vue Composable 命名规范（use 前缀）
3. 在 `composables/index.ts` 中导出

```typescript
// composables/use-new-feature.ts
export interface UseNewFeatureOptions {
  // 配置选项
}

export interface UseNewFeatureReturn {
  // 返回值类型
}

export function useNewFeature(options: UseNewFeatureOptions): UseNewFeatureReturn {
  // 实现...
}
```

---

## 7. 最佳实践

### 7.1 状态管理

- **使用 SDK 状态**：优先使用 AG-UI SDK 提供的响应式状态
- **避免重复状态**：不要在组件中重复维护 SDK 已有的状态
- **计算属性**：使用 `computed` 派生状态，避免手动同步

### 7.2 事件处理

- **统一事件系统**：所有跨组件事件通过 ComponentManager 流转
- **事件转发**：使用 `forwardToManager` 转发子组件事件
- **清理监听**：组件卸载时自动清理（useEventBridge 已处理）

### 7.3 类型安全

- **完整类型定义**：所有 Props、Emits、Expose 都有类型定义
- **避免 any**：使用具体类型，必要时使用 `unknown`
- **泛型约束**：事件系统使用泛型确保类型安全

### 7.4 性能优化

- **shallowRef**：大对象使用 `shallowRef` 减少响应式开销
- **computed 缓存**：使用 `computed` 缓存计算结果
- **避免模板复杂表达式**：将复杂逻辑移到 `computed` 或方法中

---

## 8. 消息属性（Property）系统

### 8.1 Property 概述

`property` 是消息的扩展属性，用于传递引用内容、快捷指令等额外信息。它与 `content` 同层，在消息发送时传递给后端。

### 8.2 数据结构

**引用内容**:

```typescript
{
  extra: {
    cite: '引用的文本内容'; // 简单字符串
  }
}
```

**快捷指令**:

```typescript
{
  extra: {
    cite: {
      type: "structured",
      title: "日志分析",           // 指令名称
      data: [
        { key: "日志内容", value: "..." },  // 字段标签 → 字段值
        { key: "日志 ID", value: "..." }
      ]
    },
    command: "log",                // 指令 ID
    context: [
      {
        log: "...",                // 原始字段键值
        context_type: "textarea",  // 组件类型
        __label: "日志内容",        // 元数据
        __key: "log",
        __value: "..."
      }
    ]
  }
}
```

### 8.3 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                       UI 层 (chat-bot.vue)                       │
│                                                                   │
│  handleSendMessage()          handleShortcutSubmit()              │
│        │                              │                           │
│        ▼                              ▼                           │
│  构建简单 property              buildShortcutProperty()           │
│  { extra: { cite } }           构建结构化 property                 │
│        │                              │                           │
│        └──────────────┬───────────────┘                           │
│                       ▼                                           │
│                doSendMessage(message, { property })               │
└───────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│                  业务管理层 (ChatBusinessManager)                   │
│                                                                     │
│  sendMessage(content, sessionCode, options)                         │
│        │                                                            │
│        ▼                                                            │
│  agentModule.chat(content, sessionCode, url, config, options.property)│
└───────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│                      数据层 (chat-helper)                          │
│                                                                     │
│  useAgent.chat() → createAndPlusMessage() → HTTP POST               │
│        │                                                            │
│        ▼                                                            │
│  transferMessage2MessageApi() → 发送到后端                          │
└───────────────────────────────────────────────────────────────────┘
```

### 8.4 类型定义

```typescript
// @blueking/chat-helper - message/type.ts
interface IMessageProperty {
  extra?: {
    cite?:
      | string
      | {
          type: string;
          title: string;
          data: Array<{ key: string; value: string }>;
        };
    command?: string;
    context?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

// ai-blueking - manager/business/types.ts
interface SendMessageOptions {
  includeHistory?: boolean;
  context?: Record<string, unknown>;
  property?: IMessageProperty;
}
```

---

## 9. 版本历史

| 版本  | 日期       | 更新内容                                         |
| ----- | ---------- | ------------------------------------------------ |
| 2.0.0 | 2024-12-08 | 初始架构设计，完成基础架构实现                   |
| 2.1.0 | 2024-12-20 | 添加 useChatBootstrap、useEventBridge            |
| 2.2.0 | 2024-12-25 | Header 组件分离，ChatBot 支持独立使用            |
| 2.3.0 | 2024-12-29 | 完善事件系统，添加业务管理器                     |
| 2.4.0 | 2026-01-16 | 添加消息属性（Property）系统，支持引用和快捷指令 |

---

_文档版本: 2.4.0_
_最后更新: 2026-01-16_
