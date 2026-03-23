# 架构概览

本文档介绍 AI 小鲸 v2.0 的整体架构设计，帮助开发者理解各层职责、数据流转以及核心设计模式。

## 三层架构

AI 小鲸 v2.0 采用清晰的三层架构，自顶向下分别为：**应用层**、**业务组件层**、**基础层（UI + SDK）**。

![三层架构：应用层、ai-blueking 业务组件层、chat-x 与 chat-helper 基础层及后端 API](/images/guide/architecture-layers.png)

### 各层职责

- **应用层**：宿主应用，通过引入 `@blueking/ai-blueking` 提供的组件快速集成 AI 对话能力。
- **业务组件层 (`@blueking/ai-blueking`)**：唯一的组装层，负责将底层 UI 组件和 SDK 能力编排为完整的业务组件（`AIBlueking`、`ChatBot`），并通过 Manager 模式管理业务逻辑。
- **基础层**：
  - `@blueking/chat-x`：纯 UI 组件库，不包含任何业务逻辑，仅负责渲染。
  - `@blueking/chat-helper`：AG-UI 业务 SDK，封装了与后端的通信协议、流式消息处理、会话管理等核心能力。

> **核心约束**：`chat-x` 和 `chat-helper` 彼此完全独立，不存在直接依赖关系。`ai-blueking` 是唯一的组装层，负责将两者粘合在一起。

## 数据流

AI 小鲸的数据流遵循单向流动原则：

![数据流全景：用户操作经 Component、Manager、chat-helper 与后端交互，经响应式 ref 回流至 UI](/images/guide/data-flow.png)

**流程说明**：

1. **用户操作**：用户在界面上触发交互（如发送消息、切换会话、点击快捷指令等）。
2. **Component 层**：Vue 组件捕获事件，调用对应的 Manager 方法。
3. **Manager 层**：业务管理器执行编排逻辑，调用 `chat-helper` SDK 提供的接口。
4. **SDK 层**：`chat-helper` 通过 AG-UI 协议与后端 API 进行通信（支持流式响应）。
5. **响应回传**：后端返回的数据经 SDK 解析后更新内部响应式状态（`ref`），Vue 组件自动感知变化并重新渲染 UI。

这种单向数据流确保了状态变更的可预测性和可调试性。

## Manager 模式

AI 小鲸 v2.0 采用 Manager 模式将业务逻辑从组件中抽离，每个 Manager 负责一个独立的业务领域：

| Manager                    | 职责                                                                 |
| -------------------------- | -------------------------------------------------------------------- |
| **ComponentManager**       | UI 状态管理与事件协调，作为各 Manager 之间的中枢调度器               |
| **ChatBusinessManager**    | 消息发送、停止生成、消息重建等核心聊天业务逻辑                       |
| **SessionBusinessManager** | 会话的增删改查（CRUD），包括会话列表加载、新建、切换、重命名、删除等 |
| **ShortcutManager**        | 快捷指令的筛选、选择、回填以及参数构建                               |
| **UIStateManager**         | 管理选择模式、编辑模式等 UI 交互状态                                 |
| **ShareBusinessManager**   | 分享流程的完整管理，包括消息选择、确认分享、取消分享等               |

所有 Manager 在 `ChatBot` 初始化时统一创建，通过依赖注入获取所需的 SDK 实例和其他 Manager 引用，避免循环依赖。

## ChatBot 内部架构

`ChatBot` 组件内部通过 6 个 Composable 函数实现关注点分离，每个 Composable 负责一个明确的功能切面：

| Composable            | 职责                                                                            |
| --------------------- | ------------------------------------------------------------------------------- |
| **useChatbotInit**    | Props 校验、`chatHelper` 创建/复用、Manager 实例化                              |
| **useChatbotState**   | 派生 `computed` 属性（如 `messageStatus`、`isWelcomeState` 等）                 |
| **useMessageSender**  | 输入状态管理 + 消息发送编排                                                     |
| **useShortcuts**      | 快捷指令选择、fillBack 回填、property 参数构建                                  |
| **useToolActions**    | 消息工具栏操作（引用 cite、重新生成 rebuild、删除 delete、点赞/踩 like/unlike） |
| **useShareSelection** | 选择模式切换 + 分享流程管理                                                     |

这些 Composable 在 `ChatBot` 的 `setup` 函数中按顺序组合，各自管理独立的状态和逻辑，最终通过返回值暴露给模板使用。

## 设计原则

AI 小鲸 v2.0 的架构设计遵循以下核心原则：

- **低耦合**：各层之间通过明确的接口通信，`chat-x` 和 `chat-helper` 互不依赖，可独立升级和测试。
- **高内聚**：每个 Manager 和 Composable 只负责单一职责，业务逻辑集中管理而非分散在组件模板中。
- **类型安全**：全面使用 TypeScript，所有公开 API（Props、Events、Expose、Manager 方法）均有完整的类型定义，确保编译期错误检查。
- **依赖注入**：Manager 通过构造函数注入所需依赖（如 `chatHelper` 实例、其他 Manager 引用），便于单元测试时 Mock 替换，同时避免模块间的硬编码依赖。
