# 从 v1.x 迁移到 v2.0

本指南帮助你将项目从 AI 小鲸 v1.x 升级到 v2.0。v2.0 是一次重大架构升级，但我们尽可能保持了 API 的兼容性，大多数项目可以在 1-2 小时内完成迁移。

## 架构变化概述

| 维度 | v1.x | v2.0 |
|------|------|------|
| 架构 | 单体组件，所有功能耦合在一起 | 三层模块化架构 |
| 包结构 | 单一包 | `ai-blueking` + `chat-x` + `chat-helper` |
| 组件 | 仅导出一个默认组件 | 导出 `AIBlueking` + `ChatBot` 两个组件 |
| 状态管理 | 组件内部状态 | Manager 模式 + 响应式模块 |
| 事件系统 | 直接 Vue emit | 双层事件架构（内部事件 + Vue emit） |
| 可扩展性 | 有限，需要 fork 修改 | 高度可扩展，支持自定义 Manager |

### 三层架构说明

![三层架构说明](/images/guide/migration-three-layers.png)

## 破坏性变更总览

- **导入方式**改为具名导入
- **多个属性**重命名或迁移到不同组件
- **事件名称**统一规范化
- **方法名称**更加语义化
- **请求配置**统一到 `requestOptions`

## 导入变更

```typescript
// ❌ v1.x - 默认导入
import AIBlueking from '@blueking/ai-blueking';

// ✅ v2.0 - 具名导入
import { AIBlueking, ChatBot } from '@blueking/ai-blueking';
```

### 新增的独立导入

```typescript
// 如果只需要核心对话组件（不需要窗口管理）
import { ChatBot } from '@blueking/ai-blueking';

// 如果需要底层数据管理能力
import { useChatHelper } from '@blueking/ai-blueking';

// 如果需要初始化生命周期管理
import { useChatBootstrap } from '@blueking/ai-blueking';
```

## 属性映射

以下是 v1.x 到 v2.0 的属性映射表：

| v1.x 属性 | v2.0 位置 | 说明 |
|-----------|----------|------|
| `agentUrl` | `ChatBot: url` / `AIBlueking: url` | 重命名为 `url` |
| `headConfig` | `AIBlueking: hideHeader` | 改为布尔值控制，`true` 隐藏头部 |
| `sessionConfig` | `AIBlueking: enableChatSession` | 简化为布尔值，`true` 启用多会话 |
| `shortcutList` | `ChatBot/AIBlueking: shortcuts` | 重命名为 `shortcuts` |
| `promptList` | `ChatBot/AIBlueking: prompts` | 重命名为 `prompts` |
| `welcomeContent` | `ChatBot/AIBlueking: helloText` | 重命名为 `helloText` |
| `customRequestHeaders` | `requestOptions.headers` | 统一到 `requestOptions` 对象 |
| `customRequestData` | `requestOptions.data` | 统一到 `requestOptions` 对象 |

### 属性迁移示例

```vue
<!-- ❌ v1.x -->
<AIBlueking
  agent-url="/api/agent/chat"
  :head-config="{ title: 'AI 助手', showClose: true }"
  :session-config="{ enable: true, maxCount: 10 }"
  :shortcut-list="shortcuts"
  :prompt-list="prompts"
  welcome-content="你好！我是 AI 助手"
  :custom-request-headers="{ Authorization: token }"
  :custom-request-data="{ app_id: 'app' }"
/>

<!-- ✅ v2.0 -->
<AIBlueking
  url="/api/agent/chat"
  :hide-header="false"
  :enable-chat-session="true"
  :shortcuts="shortcuts"
  :prompts="prompts"
  hello-text="你好！我是 AI 助手"
  :request-options="{
    headers: () => ({ Authorization: token }),
    data: () => ({ app_id: 'app' }),
  }"
/>
```

## 事件映射

| v1.x 事件 | v2.0 事件 | 说明 |
|-----------|----------|------|
| `message-send` | `send-message` | 重命名，动词前置 |
| `stream-start` | `receive-start` | 重命名，语义更清晰 |
| `stream-end` | `receive-end` | 重命名，语义更清晰 |

### 事件迁移示例

```vue
<!-- ❌ v1.x -->
<AIBlueking
  @message-send="onMessageSend"
  @stream-start="onStreamStart"
  @stream-end="onStreamEnd"
/>

<!-- ✅ v2.0 -->
<AIBlueking
  @send-message="onSendMessage"
  @receive-start="onReceiveStart"
  @receive-end="onReceiveEnd"
/>
```

## 方法映射

| v1.x 方法 | v2.0 方法 | 说明 |
|-----------|----------|------|
| `send(text)` | `sendMessage(text)` | 重命名，更具语义 |
| `stop()` | `stopGeneration()` | 重命名，明确停止的是生成过程 |
| `showPanel()` | `show()` | 简化命名 |
| `hidePanel()` | `hide()` | 简化命名 |

### 方法迁移示例

```typescript
// ❌ v1.x
aiRef.value?.send('你好');
aiRef.value?.stop();
aiRef.value?.showPanel();
aiRef.value?.hidePanel();

// ✅ v2.0
// AIBlueking
aiBluekingRef.value?.sendMessage('你好');
aiBluekingRef.value?.show();
aiBluekingRef.value?.hide();

// ChatBot
chatBotRef.value?.sendMessage('你好');
chatBotRef.value?.stopGeneration();
```

## v2.0 新功能

以下是 v2.0 中新增的能力，在 v1.x 中不可用：

### 1. 独立 ChatBot 组件

v2.0 新增了 `ChatBot` 组件，可以脱离窗口管理独立使用，适合嵌入到自定义布局中：

```vue
<template>
  <div class="my-custom-layout">
    <Sidebar />
    <ChatBot url="/api/agent/chat" class="chat-area" />
  </div>
</template>
```

### 2. Manager 模式

通过 Manager 模式，你可以扩展和自定义业务逻辑，而无需修改组件源码。详见 [Manager 模式](./internals/manager-pattern.md)。

### 3. 消息属性系统

结构化的消息元数据支持，允许传递引用内容、快捷指令参数等。详见 [消息属性系统](./internals/message-property.md)。

### 4. 编程式控制

更丰富的模板引用 API，支持外部精确控制组件行为。详见 [编程式控制](./advanced-usage/programmatic-control.md)。

### 5. 事件桥接

双层事件架构，内部事件和 Vue 事件自动桥接。详见 [事件系统](./internals/event-system.md)。

### 6. 初始化生命周期管理

状态机驱动的初始化流程，提供精细的生命周期控制。详见 [初始化生命周期](./internals/chat-bootstrap.md)。

### 7. 请求拦截器

请求和响应拦截器，用于统一的认证、日志、错误处理。详见 [自定义请求](./advanced-usage/custom-requests.md)。

## 逐步迁移清单

按照以下步骤有序完成迁移：

### 第一步：更新依赖

```bash
# 更新到最新版本
npm install @blueking/ai-blueking@latest
```

### 第二步：修改导入语句

```typescript
// 将所有默认导入改为具名导入
// Before: import AIBlueking from '@blueking/ai-blueking';
// After:
import { AIBlueking } from '@blueking/ai-blueking';
```

### 第三步：更新属性名

按照上方的属性映射表，逐一修改组件属性：

- [ ] `agentUrl` → `url`
- [ ] `headConfig` → `hideHeader`
- [ ] `sessionConfig` → `enableChatSession`
- [ ] `shortcutList` → `shortcuts`
- [ ] `promptList` → `prompts`
- [ ] `welcomeContent` → `helloText`
- [ ] `customRequestHeaders` + `customRequestData` → `requestOptions`

### 第四步：更新事件名

- [ ] `message-send` → `send-message`
- [ ] `stream-start` → `receive-start`
- [ ] `stream-end` → `receive-end`

### 第五步：更新方法调用

- [ ] `send()` → `sendMessage()`
- [ ] `stop()` → `stopGeneration()`
- [ ] `showPanel()` → `show()`
- [ ] `hidePanel()` → `hide()`

### 第六步：更新 TypeScript 类型（如适用）

```typescript
// ❌ v1.x 类型
import type { AIBluekingInstance } from '@blueking/ai-blueking';

// ✅ v2.0 类型
import type { AIBluekingExpose, ChatBotExpose } from '@blueking/ai-blueking';
```

### 第七步：测试验证

- [ ] 组件正常渲染
- [ ] 消息发送和接收正常
- [ ] 会话管理正常（如启用）
- [ ] 快捷指令正常（如使用）
- [ ] 自定义请求头/数据正常传递
- [ ] 事件回调正常触发
- [ ] 编程式方法调用正常

## 常见问题

### 1. 导入报错：找不到默认导出

**问题**：`Module has no default export`

**原因**：v2.0 移除了默认导出，改为具名导出

**解决**：
```typescript
// Before
import AIBlueking from '@blueking/ai-blueking';
// After
import { AIBlueking } from '@blueking/ai-blueking';
```

### 2. requestOptions 中 headers 不生效

**问题**：自定义请求头未被发送

**原因**：v2.0 中 `headers` 必须是**函数**而非静态对象

**解决**：
```typescript
// ❌ 错误：静态对象
const requestOptions = {
  headers: { Authorization: `Bearer ${token}` },
};

// ✅ 正确：返回对象的函数
const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${token}` }),
};
```

### 3. 事件处理器未触发

**问题**：之前的事件监听不再触发

**原因**：事件名已更改

**解决**：检查事件映射表，更新事件名。特别注意 `message-send` → `send-message` 的顺序变化。

### 4. headConfig 复杂配置如何迁移

**问题**：v1.x 的 `headConfig` 支持 title、showClose 等多个配置项

**解决**：v2.0 中头部配置被简化，`hideHeader` 控制显隐，标题等信息从 Agent 配置自动获取。如需更多自定义，可使用插槽（slot）。

### 5. 同时使用 AIBlueking 和 ChatBot

**问题**：不确定应该使用哪个组件

**解决**：
- **AIBlueking**：带窗口管理（拖拽、缩放、显隐），适合作为浮窗助手
- **ChatBot**：纯对话组件，适合嵌入到自定义布局中

两者可以在同一个项目中共存，但通常只需选择其一。
