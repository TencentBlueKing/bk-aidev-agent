# 组件介绍

::: tip Vibe Coding 快速接入
不想手动翻阅文档？你可以通过 AIDev Skill 市场获取 `ai-blueking-guide` Skill，在 AI IDE 中用自然语言描述需求，让 AI 帮你生成集成代码。详见 [Skill 指引](/guide/core-features/skill-guide)。
:::

## 什么是 AI 小鲸 v2.0

AI 小鲸 v2.0 是蓝鲸智云推出的新一代智能对话前端解决方案。它采用**三层模块化架构**，将 UI 渲染、业务逻辑和状态管理彻底分离，为开发者提供灵活、可扩展的智能对话集成能力。

无论你是需要快速嵌入一个聊天窗口，还是构建高度定制化的 AI 交互界面，AI 小鲸 v2.0 都能满足你的需求。它同时支持 **Vue 2** 和 **Vue 3**，并提供完整的 TypeScript 类型定义。

::: tip 核心流程
1. 在 **AIDev 平台**配置 Agent（LLM、知识库、工具、快捷指令等）
2. 发布后获取 **URL**
3. 将 URL 传给 `AIBlueking` 或 `ChatBot` → **开箱即用**
:::

## 架构总览

![三层模块化架构：应用层、ai-blueking 业务组件层、chat-x 与 chat-helper 基础层及后端 API](/images/guide/architecture-layers.png)

AI 小鲸 v2.0 由三层组成：**业务组件层**负责组装和编排，**纯 UI 组件库**专注渲染，**业务 SDK** 处理数据流与状态。三者可独立使用，也可组合集成。

## 三个核心包

| 包名 | 定位 | 说明 |
| --- | --- | --- |
| `@blueking/ai-blueking` | 业务组件层 | 组装 UI + SDK + 管理器，提供 `ChatBot` 和 `AIBlueking` 等开箱即用的高级组件 |
| `@blueking/chat-x` | 纯 UI 组件 | 不含任何业务逻辑，提供 `ChatInput`、`MessageContainer`、`ShortcutRender`、`AiSelection` 等原子级 UI 组件 |
| `@blueking/chat-helper` | 状态管理 + API 调用 + 流式处理 | 提供 `useChatHelper()`、`AGUIProtocol` 流式协议以及 agent / session / message 等业务模块 |

## 集成模式

根据业务场景，你可以选择不同的集成方式：

| 模式 | 组件 / 入口 | 适用场景 | 复杂度 |
| --- | --- | --- | --- |
| 浮窗模式 | `AIBlueking` | SaaS 全局 AI 助手，右下角浮窗 | ⭐ (仅需 `url`) |
| 页面嵌入 | `ChatBot` | 聊天作为页面主内容，嵌入 DOM | ⭐ (仅需 `url`) |
| Standalone | `@blueking/ai-blueking/standalone` | **非 Vue 宿主**（React、纯 HTML 等），`mountAIBlueking` | ⭐⭐ |
| 原子组件 | `chat-x` + `chat-helper` | 深度定制 | ⭐⭐⭐ |

- **AIBlueking 浮窗模式**：全局 AI 助手入口，提供右下角浮球、可拖拽面板、划词弹窗和内置会话管理，适合 SaaS 产品全局集成。仅需传入 `url` 即可开箱即用。
- **ChatBot 页面嵌入模式**：将聊天窗口嵌入到页面的指定区域（如侧边栏、主内容区），适合聊天作为核心功能的场景。同样仅需传入 `url`。
- **Standalone 非 Vue 宿主**（v2.1.4-beta.8+）：宿主无 Vue 时，通过 `mountAIBlueking` / `mountChatBot` 挂载，bundle 内已含 Vue 3 runtime。详见 [Standalone 集成](/guide/integration-modes/standalone-bundle)。
- **原子组件模式**：直接使用 `chat-x` 的 UI 组件和 `chat-helper` 的业务 SDK，自由组装，适合需要深度定制交互的场景。

## 核心特性

- **AG-UI 流式响应** — 基于 `AGUIProtocol` 实现实时流式输出，支持打字机效果与中断控制
- **会话生命周期管理** — 完整的会话创建、切换、删除、重命名，支持多会话并行
- **快捷指令** — 内置快捷指令（Shortcut）体系（由 AIDev 后台配置，自动加载）
- **引用与溯源** — 支持消息引用、来源标注，增强内容可信度
- **分享能力** — 支持会话分享与快照导出
- **拖拽交互** — AIBlueking 面板支持自由拖拽与尺寸调整

## v2.0 的变化

AI 小鲸 v2.0 是一次架构级重构，主要变化包括：

- **模块化架构** — 从单体组件拆分为三层架构，关注点彻底分离
- **Manager 模式** — 引入 `SessionManager`、`ChatManager`、`ShortcutManager` 等业务管理器，易于扩展和覆写
- **独立包设计** — `chat-x` 和 `chat-helper` 可完全独立使用，不依赖上层组件
- **TypeScript 优先** — 全量 TypeScript 重写，提供完整的类型定义和类型推导
- **AG-UI 协议** — 全新的流式通信协议，替代旧版 SSE 方案，支持更丰富的事件类型

::: tip 从 v1.x 升级？
请参阅 [v1.x 迁移指南](/guide/migration-2.0) 了解详细的升级步骤与 Breaking Changes。
:::
