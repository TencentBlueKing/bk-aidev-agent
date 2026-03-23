# API 概览

本文档提供 AI 小鲸 v2.0 所有包的 API 总览，帮助你快速了解各模块的职责与导出内容。

## 包一览

| 包名 | 用途 | 关键导出 |
| --- | --- | --- |
| `@blueking/ai-blueking` | 业务组件层 | `AIBlueking`、`ChatBot`、Managers |
| `@blueking/chat-x` | 纯 UI 组件 | `ChatInput`、`MessageContainer`、`MessageRender` |
| `@blueking/chat-helper` | 业务 SDK | `useChatHelper`、`AGUIProtocol` |

## 我该用哪个包？

根据你的场景，按照以下决策树选择合适的包：

![包选择决策树](/images/api/package-decision-tree.png)

### 场景对比

| 场景 | 推荐方案 | 说明 |
| --- | --- | --- |
| SaaS 平台快速接入 | `AIBlueking` | 开箱即用，含弹窗、拖拽、会话管理等完整功能 |
| 嵌入已有页面的聊天窗口 | `ChatBot` | 轻量级，仅包含核心聊天功能 |
| 自定义聊天界面 | `chat-x` + `chat-helper` | 最大灵活性，自由组合 UI 组件与业务逻辑 |

## 导入参考

```typescript
// ========================
// @blueking/ai-blueking
// ========================

// 主组件
import { AIBlueking, ChatBot } from '@blueking/ai-blueking';

// Composables
import { useChatBootstrap } from '@blueking/ai-blueking';

// Managers（业务管理器）
import {
  ComponentManager,
  ChatBusinessManager,
  SessionBusinessManager,
  ShortcutManager,
  UIStateManager,
} from '@blueking/ai-blueking';

// ========================
// @blueking/chat-x
// ========================

// UI 组件
import {
  ChatInput,
  MessageContainer,
  MessageRender,
  ShortcutRender,
  AiSelection,
} from '@blueking/chat-x';

// ========================
// @blueking/chat-helper
// ========================

// SDK
import { useChatHelper, AGUIProtocol } from '@blueking/chat-helper';
```

## 包依赖关系

![包依赖关系](/images/api/package-dependencies.png)

- **ai-blueking** 是最上层的业务组件包，内部依赖 `chat-x` 和 `chat-helper`。
- **chat-x** 是纯 UI 层，不包含任何业务逻辑，可独立使用。
- **chat-helper** 是纯业务 SDK 层，负责与后端通信、状态管理，不包含任何 UI。

## 快速链接

- [ChatBot 组件](./ai-blueking/chatbot.md)
- [AIBlueking 组件](./ai-blueking/aiblueking.md)
- [业务管理器](./ai-blueking/managers.md)
- [类型定义 (ai-blueking)](./ai-blueking/types.md)
- [UI 组件 (chat-x)](./chat-x/components.md)
- [类型定义 (chat-x)](./chat-x/types.md)
- [SDK 模块 (chat-helper)](./chat-helper/sdk.md)
- [类型定义 (chat-helper)](./chat-helper/types.md)
