# Manager 模式

## 为什么需要 Manager

在 AI 小鲸 v2.0 的架构中，我们引入了 **Manager 模式**来解决组件层日益增长的复杂性问题。Manager 模式的核心理念是：

- **关注点分离**：将业务逻辑从 Vue 组件中抽离，组件只负责渲染，Manager 负责业务编排
- **可测试性**：Manager 是纯 TypeScript 类，不依赖 Vue 运行时，可以轻松编写单元测试
- **可扩展性**：通过依赖注入和面向接口编程，新增功能只需添加新的 Manager，无需修改已有代码

## Manager 总览

v2.0 内置了 6 个核心 Manager，各司其职：

| Manager | 职责 | 依赖 |
|---------|------|------|
| `ComponentManager` | UI 状态管理 + 事件协调中心 | 无 |
| `ChatBusinessManager` | 消息发送、停止生成、流式处理 | `agentModule`、`sessionModule` |
| `SessionBusinessManager` | 会话的创建、读取、更新、删除 | `sessionModule`、`messageModule`、`agentModule` |
| `ShortcutManager` | 快捷指令的注册与管理 | `agentModule` |
| `UIStateManager` | 选择模式、编辑模式等 UI 状态 | 无 |
| `ShareBusinessManager` | 分享流程编排 | `messageModule`、`sessionModule` |

### 职责说明

- **ComponentManager** 是整个 Manager 体系的协调中心，负责管理组件级别的 UI 状态（如加载态、错误态），同时作为内部事件总线，协调各 Manager 之间的通信。
- **ChatBusinessManager** 封装了与 AI 对话相关的所有业务逻辑，包括消息发送、流式响应处理、停止生成等操作。
- **SessionBusinessManager** 管理会话的完整生命周期，包括会话列表加载、新建会话、切换会话、删除会话等。
- **ShortcutManager** 负责快捷指令的注册、查询和执行，支持自定义指令扩展。
- **UIStateManager** 管理与用户交互相关的 UI 状态，如消息选择模式、文本编辑模式等。
- **ShareBusinessManager** 编排消息分享的完整流程，包括选择消息、生成分享链接、复制内容等。

## Manager 创建模式

所有 Manager 都通过**依赖注入**的方式创建，在组件初始化时由 `useChatBootstrap` 或手动方式完成实例化：

```typescript
import { ComponentManager, ChatBusinessManager, SessionBusinessManager } from '@blueking/ai-blueking';

// 1. 创建无依赖的基础 Manager
const componentManager = new ComponentManager();

// 2. 创建依赖底层模块的业务 Manager
const chatManager = new ChatBusinessManager(
  chatHelper.agent,    // agentModule - 提供 AI 代理交互能力
  chatHelper.session,  // sessionModule - 提供会话上下文
  chatbotInit          // 初始化配置
);

// 3. 创建需要多个模块的 Manager
const sessionManager = new SessionBusinessManager(
  chatHelper.session,  // sessionModule
  chatHelper.message,  // messageModule
  chatHelper.agent,    // agentModule
  {
    enableChatSession: true  // 启用多会话管理
  }
);
```

### 依赖关系图

![Manager 依赖关系图](/images/guide/manager-dependencies.png)

## 自定义 Manager 扩展

当内置 Manager 无法满足需求时，你可以创建自定义 Manager 并注册到体系中。

### 步骤一：定义自定义 Manager

```typescript
import { BaseManager } from '@blueking/ai-blueking';

export class AnalyticsManager extends BaseManager {
  private trackingId: string;

  constructor(trackingId: string) {
    super();
    this.trackingId = trackingId;
  }

  // 追踪消息发送事件
  trackMessageSent(content: string) {
    console.log(`[${this.trackingId}] 消息已发送: ${content.substring(0, 50)}...`);
    // 上报到分析平台
  }

  // 追踪会话切换事件
  trackSessionSwitch(sessionCode: string) {
    console.log(`[${this.trackingId}] 会话切换: ${sessionCode}`);
  }

  dispose() {
    // 清理资源
  }
}
```

### 步骤二：注册到 ComponentManager

```typescript
const analyticsManager = new AnalyticsManager('my-app-001');

// 注册到 ComponentManager，使其参与事件协调
componentManager.register('analytics', analyticsManager);

// 在事件中使用
componentManager.on('send-message', (content: string) => {
  analyticsManager.trackMessageSent(content);
});

componentManager.on('session-switch', (code: string) => {
  analyticsManager.trackSessionSwitch(code);
});
```

### 步骤三：在组件中使用

```typescript
// 通过 provide/inject 在组件树中共享
provide('analyticsManager', analyticsManager);

// 子组件中获取
const analytics = inject<AnalyticsManager>('analyticsManager');
```

## 副作用处理原则

Manager 模式的一个核心原则是：**所有副作用都由 Manager 处理，组件保持纯渲染**。

### 什么是副作用？

- API 调用（发送消息、加载会话列表等）
- 状态变更（修改全局状态、更新缓存等）
- 浏览器 API 调用（localStorage、clipboard 等）
- 定时器和订阅管理

### 正确做法

```typescript
// ✅ 组件只负责渲染和用户交互转发
const ChatInput = defineComponent({
  setup() {
    const chatManager = inject<ChatBusinessManager>('chatManager');

    const handleSend = (content: string) => {
      // 将用户操作委托给 Manager
      chatManager.sendMessage(content);
    };

    return { handleSend };
  },
});

// ✅ Manager 处理所有副作用
class ChatBusinessManager {
  async sendMessage(content: string) {
    // 副作用：更新状态
    this.setLoading(true);
    try {
      // 副作用：API 调用
      await this.agentModule.chat(content, this.sessionCode);
      // 副作用：触发事件
      this.emit('message-sent', content);
    } catch (error) {
      // 副作用：错误处理
      this.handleError(error);
    } finally {
      this.setLoading(false);
    }
  }
}
```

### 错误做法

```typescript
// ❌ 不要在组件中直接处理副作用
const ChatInput = defineComponent({
  setup() {
    const handleSend = async (content: string) => {
      // 错误：组件内直接发起 API 调用
      const response = await fetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ content }),
      });
      // 错误：组件内直接操作 DOM / 全局状态
      document.title = '新消息...';
    };

    return { handleSend };
  },
});
```

遵循这一原则，可以确保组件的可复用性和可测试性，同时让业务逻辑的维护和调试变得更加简单。
