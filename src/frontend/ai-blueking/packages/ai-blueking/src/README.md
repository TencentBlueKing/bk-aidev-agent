# AIBlueking V2 - 小鲸组件重构版本

## 简介

AIBlueking V2 是小鲸组件的重构版本，采用全新的三层架构设计：

1. **AG-UI SDK** - 负责数据管理和 Agent 交互
2. **原子化组件** - 纯 UI 渲染组件
3. **小鲸组件** - 业务逻辑封装和完整功能

## 核心特性

- ✅ **模块化设计** - 清晰的职责划分，易于维护和扩展
- ✅ **两种使用方式** - 完整组件和可嵌入的 ChatBot
- ✅ **业务管理器** - 统一的业务逻辑封装
- ✅ **类型安全** - 完整的 TypeScript 类型定义
- ✅ **事件驱动** - 灵活的事件系统

## 架构设计

```
┌─────────────────────────────────────────┐
│         小鲸组件层（V2）                  │
│  ┌─────────────┐    ┌─────────────┐    │
│  │ AIBlueking  │    │  ChatBot    │    │
│  │ (完整版)     │    │  (核心版)    │    │
│  └─────────────┘    └─────────────┘    │
│           │                 │           │
│  ┌────────────────────────────────┐    │
│  │      业务管理器层               │    │
│  │  SessionBusiness | ChatBusiness │    │
│  │  UIState | Shortcut            │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
           │                  │
┌──────────┴──────┐   ┌──────┴──────────┐
│  原子化组件层    │   │   AG-UI SDK     │
│  MessageRender  │   │  session/message │
│  ChatInput      │   │  agent/http     │
│  ShortcutBtns   │   │                 │
└─────────────────┘   └─────────────────┘
```

## 安装使用

### 基础使用 - 完整小鲸组件

适用场景：需要 Nimbus 悬浮球、选中文本弹窗、拖拽功能的完整体验。

```vue
<template>
  <AIBlueking
    url="/api/ai"
    title="AI 助手"
    :shortcuts="shortcuts"
    :enable-popup="true"
    :draggable="true"
    @send-message="handleSendMessage"
  />
</template>

<script setup>
import { AIBlueking } from '@blueking/ai-blueking/v2';

const shortcuts = [
  { id: 'translate', name: '翻译', prompt: '请帮我翻译：' },
];

const handleSendMessage = (message) => {
  console.log('发送消息:', message);
};
</script>
```

### ChatBot 嵌入使用

适用场景：需要将聊天功能嵌入到任意页面中，不需要悬浮球和拖拽。

```vue
<template>
  <div class="page-layout">
    <ChatBot
      url="/api/ai"
      :session-code="sessionCode"
      height="600px"
      @send-message="handleSendMessage"
    />
  </div>
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking/v2';

const sessionCode = ref('');

const handleSendMessage = (message) => {
  console.log('发送消息:', message);
};
</script>
```

### 自定义代码块头部（codeHeader 插槽）

适用场景：需要在 AI 返回的 markdown 代码块头部增加“插入”“应用”等业务按钮。

`AIBlueking` 和 `ChatBot` 均支持 `codeHeader` 插槽，参数为：

- `language: string`：代码块语言
- `token: Token[]`：markdown token 列表（可用于高级解析场景）

```vue
<template>
  <AIBlueking :url="apiUrl">
    <template #codeHeader="{ language, token }">
      <span @click="handleCodeInsert(language, token)">插入</span>
      <span @click="handleCodeApply(language, token)">应用</span>
    </template>
  </AIBlueking>
</template>

<script setup lang="ts">
import type Token from 'markdown-it/lib/token';

const apiUrl = '/api/ai';

const handleCodeInsert = (language: string, token: Token[]) => {
  console.log('insert code', language, token);
};

const handleCodeApply = (language: string, token: Token[]) => {
  console.log('apply code', language, token);
};
</script>
```

### 高级用法 - 自定义业务逻辑

适用场景：需要完全自定义业务逻辑和 UI 交互。

```vue
<script setup>
import { useChatHelper } from '@blueking/chat-helper';
import {
  SessionBusinessManager,
  ChatBusinessManager,
  EventManager,
} from '@blueking/ai-blueking/v2';

// 创建 AG-UI SDK 实例
const chatHelper = useChatHelper({
  requestData: { urlPrefix: '/api/ai' },
});

// 创建事件管理器
const eventManager = new EventManager();

// 创建业务管理器
const sessionManager = new SessionBusinessManager(
  chatHelper.session,
  chatHelper.message,
  eventManager
);

const chatManager = new ChatBusinessManager(
  chatHelper.agent,
  chatHelper.message,
  eventManager
);

// 自定义业务逻辑
const handleCustomFlow = async () => {
  await sessionManager.createSession({ name: '新会话' });
  await chatManager.sendMessage('你好');
};
</script>
```

## API 文档

### AIBlueking Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| url | string | - | API 服务地址 |
| title | string | 'AI 助手' | 组件标题 |
| shortcuts | IShortcut[] | [] | 快捷方式列表 |
| enablePopup | boolean | false | 是否启用选中文本弹窗 |
| draggable | boolean | true | 是否可拖拽 |
| hideNimbus | boolean | false | 是否隐藏悬浮球 |
| requestOptions | IRequestOptions | - | 请求配置 |

### AIBlueking Emits

| 事件 | 参数 | 说明 |
|------|------|------|
| send-message | message: string | 发送消息时触发 |
| shortcut-click | data: { shortcut, source } | 快捷方式点击时触发 |
| show | - | 面板显示时触发 |
| close | - | 面板关闭时触发 |

### AIBlueking Expose

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| show | sessionCode?: string | Promise<void> | 显示面板 |
| hide | - | void | 隐藏面板 |
| sendMessage | message: string | Promise<void> | 发送消息 |
| stopGeneration | - | void | 停止生成 |
| setCiteText | text: string | void | 设置引用文本 |

### AIBlueking Slots

| 插槽 | 参数 | 说明 |
|------|------|------|
| codeHeader | `{ language: string; token: Token[] }` | 自定义消息中 markdown 代码块头部 |

### ChatBot Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| url | string | - | API 服务地址（独立模式） |
| chatHelper | IChatHelper | - | ChatHelper 实例（集成模式） |
| sessionCode | string | - | 会话编码 |
| height | string \| number | '600px' | 组件高度 |
| shortcuts | IShortcut[] | [] | 快捷方式列表 |
| autoLoad | boolean | true | 是否自动加载 |
| enableSelection | boolean | false | 启用消息选择（仅集成模式，独立模式自动管理） |
| shareLoading | boolean | false | 分享加载中（仅集成模式，独立模式自动管理） |

### 分享功能

ChatBot 在**独立模式**下内置了完整的消息分享流程：

1. 用户点击消息工具栏的「分享」按钮 → 自动进入选择模式
2. 用户勾选要分享的消息，点击「确定」→ 调用后端 `share/` API
3. 生成分享链接并复制到剪贴板 → Toast 提示「分享链接已复制到剪贴板」
4. 自动退出选择模式

在**集成模式**下（由 `ai-blueking.vue` 使用），分享由父组件协调管理：
- `ai-blueking.vue` 有 AIHeader 和 ChatBot 两个分享入口
- 通过 `UIStateManager` 统一管理选择模式状态
- 通过 `ShareBusinessManager` 封装分享业务逻辑
- ChatBot 通过 `enableSelection` / `shareLoading` props 接受外部控制

## 业务管理器

### SessionBusinessManager

负责会话业务流程管理。

```typescript
const sessionManager = new SessionBusinessManager(
  chatHelper.session,
  chatHelper.message,
  eventManager,
  {
    enableChatSession: true,
    autoSwitchToInitialSession: true,
  }
);

// 创建会话
await sessionManager.createSession({ name: '新会话' });

// 切换会话
await sessionManager.switchSession(sessionCode);

// 删除会话
await sessionManager.deleteSession(sessionCode);
```

### ChatBusinessManager

负责聊天业务流程管理。

```typescript
const chatManager = new ChatBusinessManager(
  chatHelper.agent,
  chatHelper.message,
  eventManager
);

// 发送消息
await chatManager.sendMessage('你好');

// 停止生成
chatManager.stopGeneration();

// 设置引用文本
chatManager.setCiteText('引用内容');
```

### UIStateManager

负责 UI 状态管理。

```typescript
const uiStateManager = new UIStateManager();

// 启用选择模式
uiStateManager.enableSelectionMode();

// 选中消息
uiStateManager.selectMessage(messageId);

// 获取选中的消息
const selected = uiStateManager.selectedMessages;
```

### ShortcutManager

负责快捷方式管理。

```typescript
const shortcutManager = new ShortcutManager(eventManager, shortcuts);

// 设置快捷方式
shortcutManager.setShortcuts(newShortcuts);

// 过滤快捷方式
const filtered = shortcutManager.filterShortcuts(selectedText, filterFn);
```

## 事件系统

```typescript
import { EventManager } from '@blueking/ai-blueking/v2';

const eventManager = new EventManager();

// 订阅事件
eventManager.on('session-created', (data) => {
  console.log('会话已创建:', data);
});

// 发射事件
eventManager.emit('session-created', { session });

// 取消订阅
eventManager.off('session-created');
```

## 从旧版本迁移

### 主要变化

1. **SDK 重构** - 旧的 `AIBluekingSDK` 被拆分为 AG-UI SDK 和业务管理器
2. **组件分离** - 提供 `AIBlueking` 和 `ChatBot` 两个组件
3. **类型更新** - 部分类型定义有所调整

### 迁移步骤

1. 更新导入路径：
```typescript
// 旧版本
import { AIBlueking } from '@blueking/ai-blueking';

// 新版本
import { AIBlueking } from '@blueking/ai-blueking/v2';
```

2. Props 保持兼容（大部分情况下无需修改）

3. 如果使用了 SDK，需要改为使用业务管理器

## 最佳实践

### 1. 使用合适的组件

- 需要完整功能（悬浮球、拖拽）→ 使用 `AIBlueking`
- 嵌入到页面中 → 使用 `ChatBot`
- 完全自定义 → 使用业务管理器 + AG-UI SDK

### 2. 事件管理

使用统一的 `EventManager` 管理所有事件：

```typescript
const eventManager = new EventManager();

// 业务管理器共享同一个事件管理器
const sessionManager = new SessionBusinessManager(..., eventManager);
const chatManager = new ChatBusinessManager(..., eventManager);
```

### 3. 错误处理

```typescript
try {
  await chatManager.sendMessage(message);
} catch (error) {
  console.error('发送失败:', error);
  // 显示错误提示
}
```

### 4. 内存清理

```typescript
onBeforeUnmount(() => {
  // 清理事件监听
  eventManager.clear();
  // 停止聊天
  chatHelper.agent.stopChat();
});
```

## 目录结构

```
v2/
├── ai-blueking.vue          # AIBlueking 完整组件
├── components/              # 核心组件
│   ├── chat-bot.vue         # ChatBot 核心组件
│   └── types.ts             # 组件类型定义
├── manager/                 # 管理器层
│   ├── component-manager.ts # UI 组件协调
│   ├── event-manager.ts     # 事件管理
│   └── business/            # 业务管理器
│       ├── session-business-manager.ts
│       ├── chat-business-manager.ts
│       ├── ui-state-manager.ts
│       └── shortcut-manager.ts
├── config/                  # 配置
│   ├── protocol-config.ts   # Protocol 配置
│   └── prop-defaults.ts     # Props 默认值
├── containers/              # 容器组件
│   └── draggable-container.vue
├── examples/                # 使用示例
│   ├── basic-usage.vue
│   ├── chatbot-embedded.vue
│   └── advanced-usage.vue
├── types.ts                 # 类型定义
├── index.ts                 # 导出入口
└── README.md                # 本文档
```

## 常见问题

### Q: 如何切换会话？

```typescript
// 方式1：通过 expose 方法
aiBluekingRef.value?.switchToSession(sessionCode);

// 方式2：通过业务管理器
await sessionManager.switchSession(sessionCode);
```

### Q: 如何自定义样式？

使用 `extCls` 属性添加自定义类名，然后通过 CSS 覆盖样式。

### Q: 如何处理错误？

监听 `error` 事件或 `sdk-error` 事件：

```vue
<AIBlueking @sdk-error="handleError" />
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License













