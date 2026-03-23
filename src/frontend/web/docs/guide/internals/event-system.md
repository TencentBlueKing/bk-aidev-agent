# 事件系统

AI 小鲸 v2.0 采用了双层事件架构，既保证了内部模块间的解耦通信，又兼容了 Vue 的标准事件机制。

## 双层事件架构

### 内部事件层

内部事件通过 `ComponentManager` 的 `on` / `emit` 方法进行通信。这是 Manager 之间以及 Manager 与内部组件之间的主要通信方式。

```typescript
// 发布事件
componentManager.emit('send-message', { content: '你好', sessionCode: 'abc123' });

// 订阅事件
componentManager.on('send-message', (payload) => {
  console.log('收到消息:', payload.content);
});
```

### Vue 事件层

Vue 事件通过标准的 `emit` 机制向父组件传递。这是组件对外暴露的公共 API。

```vue
<!-- 父组件中使用 -->
<ChatBot
  @send-message="handleSendMessage"
  @receive-start="handleReceiveStart"
  @receive-end="handleReceiveEnd"
/>
```

## useEventBridge：桥接两层事件

`useEventBridge` 是连接内部事件与 Vue 事件的桥梁组合式函数。它自动监听 `ComponentManager` 上的内部事件，并将其转发为 Vue `emit` 调用。

```typescript
import { useEventBridge } from '@blueking/ai-blueking';

// 在 ChatBot 组件内部
const emit = defineEmits([
  'send-message',
  'receive-start',
  'receive-end',
  'session-change',
  // ...
]);

// 一行代码完成桥接
useEventBridge(componentManager, emit);
```

### 工作原理

`useEventBridge` 内部会遍历 `EVENT_BRIDGE_MAP`，为每个内部事件注册监听器，当事件触发时自动调用对应的 Vue `emit`。

## EVENT_BRIDGE_MAP

`EVENT_BRIDGE_MAP` 定义了内部事件名到 Vue emit 名的映射关系：

```typescript
const EVENT_BRIDGE_MAP: Record<string, string> = {
  // UI 事件
  'input-focus':        'input-focus',
  'input-blur':         'input-blur',
  'scroll-to-bottom':   'scroll-to-bottom',

  // 业务事件
  'send-message':       'send-message',
  'receive-start':      'receive-start',
  'receive-end':        'receive-end',
  'stop-generation':    'stop-generation',
  'message-error':      'message-error',

  // 头部事件
  'header-close':       'close',
  'header-clear':       'clear',
  'header-toggle-full': 'toggle-fullscreen',

  // 选择事件
  'selection-change':   'selection-change',
  'selection-confirm':  'selection-confirm',
  'selection-cancel':   'selection-cancel',
};
```

## 事件分类

### UI 事件

与界面交互相关的事件，不涉及业务逻辑：

| 事件名 | 触发时机 | 载荷 |
|--------|---------|------|
| `input-focus` | 输入框获得焦点 | 无 |
| `input-blur` | 输入框失去焦点 | 无 |
| `scroll-to-bottom` | 消息列表滚动到底部 | 无 |

### 业务事件

与核心对话业务相关的事件：

| 事件名 | 触发时机 | 载荷 |
|--------|---------|------|
| `send-message` | 用户发送消息 | `{ content: string, property?: IMessageProperty }` |
| `receive-start` | 开始接收 AI 回复 | `{ sessionCode: string }` |
| `receive-end` | AI 回复结束 | `{ sessionCode: string, message: IMessage }` |
| `stop-generation` | 用户停止生成 | 无 |
| `message-error` | 消息处理出错 | `{ error: Error }` |

### 头部事件

与顶部操作栏相关的事件：

| 事件名 | 触发时机 | 载荷 |
|--------|---------|------|
| `header-close` | 点击关闭按钮 | 无 |
| `header-clear` | 点击清空按钮 | 无 |
| `header-toggle-full` | 点击全屏切换 | `{ isFullscreen: boolean }` |

### 选择事件

与消息选择模式相关的事件：

| 事件名 | 触发时机 | 载荷 |
|--------|---------|------|
| `selection-change` | 选择的消息发生变化 | `{ selectedIds: string[] }` |
| `selection-confirm` | 确认选择 | `{ messages: IMessage[] }` |
| `selection-cancel` | 取消选择模式 | 无 |

## 订阅事件

### 在 Manager 中订阅

```typescript
// 订阅单个事件
componentManager.on('send-message', (payload) => {
  console.log('用户发送了:', payload.content);
});

// 订阅一次性事件
componentManager.once('receive-end', (payload) => {
  console.log('首次回复完成');
});

// 取消订阅
const handler = (payload) => { /* ... */ };
componentManager.on('send-message', handler);
componentManager.off('send-message', handler);
```

### 在 Vue 组件中订阅

```vue
<template>
  <ChatBot
    @send-message="onSendMessage"
    @receive-start="onReceiveStart"
    @receive-end="onReceiveEnd"
    @message-error="onMessageError"
  />
</template>

<script setup lang="ts">
const onSendMessage = (payload: { content: string }) => {
  console.log('消息已发送:', payload.content);
};

const onReceiveStart = () => {
  console.log('开始接收回复...');
};

const onReceiveEnd = (payload: { message: IMessage }) => {
  console.log('回复完成:', payload.message);
};

const onMessageError = (payload: { error: Error }) => {
  console.error('消息出错:', payload.error);
};
</script>
```

## 添加自定义事件

当内置事件不能满足需求时，你可以添加自定义事件类型。

### 步骤一：定义事件

```typescript
// types/events.ts
declare module '@blueking/ai-blueking' {
  interface ComponentManagerEvents {
    // 添加自定义事件类型
    'custom-analytics': { action: string; label: string };
    'theme-change': { theme: 'light' | 'dark' };
  }
}
```

### 步骤二：在 Manager 中触发

```typescript
// 在自定义 Manager 中触发事件
class ThemeManager {
  constructor(private componentManager: ComponentManager) {}

  switchTheme(theme: 'light' | 'dark') {
    // 执行主题切换逻辑...
    this.componentManager.emit('theme-change', { theme });
  }
}
```

### 步骤三：扩展 EVENT_BRIDGE_MAP（可选）

如果需要将自定义事件桥接到 Vue emit：

```typescript
import { EVENT_BRIDGE_MAP } from '@blueking/ai-blueking';

// 扩展桥接映射
EVENT_BRIDGE_MAP['theme-change'] = 'theme-change';
EVENT_BRIDGE_MAP['custom-analytics'] = 'analytics';
```

### 步骤四：在父组件中监听

```vue
<ChatBot
  @theme-change="onThemeChange"
  @analytics="onAnalytics"
/>
```

## 完整事件流示例

以下展示一条消息从用户输入到父组件接收的完整事件流：

![完整事件流](/images/guide/event-flow.png)

这种双层事件架构确保了内部实现的灵活性，同时保持了对外 API 的稳定性和 Vue 生态的一致性。
