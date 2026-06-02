# 更新日志

## v2.1.4-beta.14

### 新功能

- **`updateAgentInfo` 方法**（**≥ v2.1.4-beta.14**）：`ChatBot` / `AIBlueking` 均暴露 `updateAgentInfo()`，可主动刷新 agent 信息并自动同步 shortcuts 等内部状态；返回 `Promise<IAgentInfo | null>`

### 文档

- 更新 [ChatBot API](/api/ai-blueking/chatbot)、[AIBlueking API](/api/ai-blueking/aiblueking)、[类型定义](/api/ai-blueking/types)、[编程式控制](/guide/advanced-usage/programmatic-control)

---

## v2.1.4-beta.13

### 新功能

- **`ChatBot.whenReady()` / `isReady`**（**≥ v2.1.4-beta.13**）：独立嵌入场景下，`await chatBotRef.whenReady()` 在 `getAgentInfo`、`getSessions` 与 `loadRecentSession` 完成后 resolve，语义对齐 `AIBlueking` 的 `show()` / `ensureSessionReady`；`isReady` 为只读响应式状态。集成模式（传入 `chatHelper`）下 `whenReady` 立即 resolve，会话就绪仍由父级 bootstrap 或 `show()` 保证
- **`url` / `chatHelper` 变更重初始化**：进行中的 `whenReady()` 以 `ChatBotInitStaleError` reject，需重新 `await whenReady()`

### 文档

- 更新 [ChatBot API](/api/ai-blueking/chatbot)、[类型定义](/api/ai-blueking/types)、[编程式控制](/guide/advanced-usage/programmatic-control)、[会话管理](/guide/core-features/session-management) 与 [常见问题](/faq)

---

## v2.1.4-beta.9

### 优化

- **`show()` 会话就绪 Promise**：`await show()` 在 `sessionList` 加载完成后 resolve；`loadRecentSessionOnMount` 为 `true` 时还会等待最近会话选定或创建完成。面板仍立即打开，初始化在后台进行；失败时 Promise reject，并触发 `sdk-error`（`apiName: 'init'`）
- **`requestOptions` 响应式落地**：`headers` / `data` 支持普通对象、零参函数、`ref`、`computed`；外层 `requestOptions` 可为 `MaybeRefOrGetter`（`AIBlueking` / `ChatBot` / `useChatBootstrap`），整体替换后后续请求自动生效，切换 token 或租户无需重建组件
- **`data` 按 HTTP 方法分流**：POST/PUT/PATCH/DELETE 合并进 body；GET/HEAD/OPTIONS 合并进 query（`params`）；body 为 FormData / Blob 等非 plain object 时跳过合并并输出警告
- **`@blueking/chat-helper`**：新增 `resolveRequestValue`、`MaybeRequestValue` 类型，在 `requestData` 拦截器层统一解析
- **`useChatBootstrap` 初始化并发**：`initialize()` 复用进行中的 Promise；`retry` / `updateConfig` 使用 `initGeneration` 丢弃过期初始化结果，避免 URL 切换后旧请求写回 `READY` 状态

### 文档

- 更新 [编程式控制](/guide/advanced-usage/programmatic-control)、[会话管理](/guide/core-features/session-management)、[AIBlueking 浮窗模式](/guide/integration-modes/aiblueking-floating)
- 更新 [自定义请求](/guide/advanced-usage/custom-requests)、[ChatBot](/api/ai-blueking/chatbot)、[AIBlueking](/api/ai-blueking/aiblueking)、[类型定义](/api/ai-blueking/types) 与 [chat-helper 类型](/api/chat-helper/types)

---

## v2.1.4-beta.8

### 新功能

- **`requestOptions` 响应式增强**：`headers` / `data` 支持普通对象、函数、`ref`、`computed`；外层 `requestOptions` 也可为 `ref` / `computed`，替换后后续请求自动生效。`data` 对 POST/PUT/PATCH/DELETE 写入 body，对 GET/HEAD/OPTIONS 自动转为 query 参数。能力在 `@blueking/chat-helper` 的 `requestData` 层统一实现，小鲸与直接使用 chat-helper 的业务均可受益
- **Standalone 子入口**（`@blueking/ai-blueking/standalone`）：内联 Vue 3 runtime 与 chat-x，供非 Vue 宿主（React、Angular、纯 HTML 等）通过 `mountAIBlueking`、`mountChatBot` 挂载小鲸，无需宿主安装 Vue
- 导出同源 `h`、`render`、`createApp`，支持自定义 VNode / 侧栏渲染；提供 `updateProps`、`expose` / `getExpose`、`unmount` 等挂载句柄 API
- 构建产物：`dist/standalone/`（ES / UMD / IIFE），IIFE 全局名 `AIBluekingStandalone`

### 文档

- 新增 [Standalone 非 Vue 宿主集成](/guide/integration-modes/standalone-bundle) 指南
- 新增 [Standalone API](/api/ai-blueking/standalone) 参考

---

## v2.1.4-beta.7

### 新功能

- **侧栏 Tab 自定义渲染**：`ChatBot` / `AIBlueking` 支持 `getSideRenderComponent`、`getSideTabRenderComponent`、`onCustomTabChange`，用于自定义 FlowAgent 节点详情等内容区与 Tab 标签；未传 `onCustomTabChange` 时，Flow 节点 Tab 仍走内置 `getFlowAgentTaskNodeInfo`
- 导出类型 `GetSideRenderComponent`、`GetSideTabRenderComponent`、`OnCustomTabChange`

### 文档

- 新增 [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization) 指南（含 composable 示例与 Playground 对照）
- 更新 [ChatBot](/api/ai-blueking/chatbot)、[AIBlueking](/api/ai-blueking/aiblueking)、[类型定义](/api/ai-blueking/types) API 说明

---

## v2.1.4-beta.6

### 新功能

- **蓝鲸行内富文本**：AI 消息支持 `::bk{属性}正文:/bk::` 语法，在安全白名单内渲染颜色、加粗、斜体、背景色、字号（1–72px），无需开启 HTML 解析
- 行内正文仍支持标准 Markdown（加粗、链接、行内代码等）

### 变更

- Markdown 渲染**不再**解析任意 HTML 标签；行内样式请使用蓝鲸行内富文本语法，详见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)

### 文档

- 新增 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style) 指南，含 LLM / 系统提示词配置示例

---

## v2.1.4-beta.2

### 新功能

- **消息自定义渲染**: 支持在 AI 对话中嵌入自定义组件，包括图表、iframe、表单等任意自定义内容
- 新增 `parseCustomBlocks` 工具函数，将消息内容解析为文本块与自定义组件块的混合列表
- 通过 `#message` 插槽集成自定义渲染器，业务方可灵活扩展组件类型
- 支持混合展示文本与多个自定义组件，AI 可在一条消息中输出多种组件

### 文档

- 新增[消息自定义渲染](/guide/core-features/custom-message-rendering)功能指南

---

## v2.0.0-beta.1

### 重大变更

- **三层模块化架构**: 从单体组件重构为 `ai-blueking` + `chat-x` + `chat-helper` 三个独立包
- **新增 ChatBot 组件**: 可独立使用的轻量聊天组件
- **Manager 模式**: 引入 6 个业务管理器，提高代码可维护性和可扩展性
- **AG-UI 流式协议**: 基于 `AGUIProtocol` 的全新流式响应处理
- **TypeScript 全覆盖**: 所有组件和 SDK 均提供完整类型定义

### 新功能

- ChatBot 组件支持独立模式和集成模式
- AIBlueking 组件支持悬浮球、拖拽、划词选择
- `useChatBootstrap` 自动初始化生命周期
- 消息分享功能（内置 + 自定义两种模式）
- 批量删除会话 (`batchDeleteSessions`)
- 会话重命名 (`renameSession`)
- 消息反馈系统（like/unlike + 原因选择）
- 文件上传支持
- 提示词（`/` 触发）和资源（`@` 触发）快捷输入
- 快捷操作支持表单字段配置

### 包结构

| 包名 | 说明 |
| --- | --- |
| `@blueking/ai-blueking` | 业务集成层，提供 AIBlueking 和 ChatBot 组件 |
| `@blueking/chat-x` | UI 组件层，提供 ChatInput、MessageContainer 等原子组件 |
| `@blueking/chat-helper` | 核心 SDK 层，提供 useChatHelper、AGUIProtocol 等 |

### 迁移指南

从 v1.x 迁移请参考 [迁移指南](/guide/migration-2.0)。

---

## v1.3.2 <Badge type="info" text="2026-01-09" />

### 新功能
- 快捷指令新增 `alias` 字段，支持显示与原始名称不同的别名
- 组件级别新增 `fillBack` 和 `fillRegx` 字段，支持更细粒度的文本填充控制
- 新增 `agentInfo` 属性暴露，可通过组件 ref 访问智能体的完整配置信息

### 优化
- 划词弹窗支持从智能体配置的 `conversationSettings.enableWordSelectionPopup` 动态控制
- 优化划词选择的事件监听器管理，使用 watch 动态添加/移除监听器
- 移除 motion-v 动画库依赖，简化输入框组件渲染逻辑，提升性能
- 重构问候语高度计算逻辑，优化输入框位置的联动计算

### 修复
- 修复从历史会话恢复时会话切换的状态问题
- 修复输入框在某些情况下定位不准确的问题

---

## v1.3.1 <Badge type="info" text="2026-01-06" />

### 新功能
- 核心架构重构：提取聊天核心逻辑到独立的 `use-chat-core` composable
- 新增 `use-iframe-drag-resize` composable，优化 iframe 内的拖拽和调整大小体验
- Props 类型系统增强：新增独立的 Props 类型定义和默认值配置模块
- 快捷方式编辑功能修复：支持 shortcut 消息的编辑和重新发送
- 新增 `init-session-finished` 事件

### 优化
- 优化快捷方式功能，动态合并当前快捷方式与原始快捷方式数据
- 重构模板条件判断顺序，编辑模式优先于显示模式
- 更新 dayjs 和 markdown-it 依赖版本

### 修复
- 修复 shortcut 消息编辑功能无法显示的问题
- 修复 useChatCore 中 TypeScript 类型定义问题

---

## v1.3.0 <Badge type="info" text="2025-12-12" />

::: warning 重要提醒
小鲸 1.3.0 版本必须与后端 SDK 版本 1.0.5.post3 或更高版本匹配使用。
:::

### 新功能
- 新增分享会话功能，支持选择对话内容进行分享
- `dropdownMenuConfig.showShare` 默认启用
- 新增 Cmd/Ctrl + I 快捷键，支持快速切换面板显示/隐藏
- 快捷指令支持动态更新

### 优化
- 修复 iframe 上拖拽失效的问题
- 修复 HTTP 协议下剪切板操作失败的问题
- 改进 Vue2 样式兼容性

---

## v1.2.9 <Badge type="info" text="2025-10-23" />

### 新功能
- 优化小鲸指令配置，支持 simple 配置模式
- 无权限页面优化，添加权限检查机制
- 新增 `showCompressionIcon`、`showMoreIcon`、`defaultChatInputPosition`、`maxWidth` 等 props 配置项

---

## v1.2.8 <Badge type="info" text="2025-10-17" />

::: warning 重要提醒
小鲸 1.2.8 版本必须与后端 SDK 版本 1.0.0b48 或更高版本匹配使用。
:::

### 新功能
- 新增会话创建参数配置
- 新增 feedback 功能，优化反馈交互体验
- 新增 `iconRender` 支持以自定义图标渲染
- 优化 markdown-viewer 组件的 cite 文本处理
- 新增更新位置和大小的功能

---

## v1.2.7 <Badge type="info" text="2025-10-14" />

### 新功能
- 新增 `hideDefaultTrigger` 属性，支持隐藏默认触发按钮
- 新增 `dropdownMenuConfig` 属性，自定义会话操作下拉菜单
- 新增 `placeholder` 属性，自定义输入框占位符
- `handleShow` 方法新增 `forceNewSession` 参数
- 新增 `updatePosition`、`updateSize`、`updatePositionAndSize` 方法
- 新增 `drag-stop`、`resize-stop`、`dragging`、`resizing` 事件
- 历史会话面板新增时间分组

---

## v1.2.6 <Badge type="info" text="2025-09-18" />

::: warning 重要提醒
小鲸 1.2.6 版本必须与后端 SDK 版本 1.0.0b42 或更高版本匹配使用。
:::

### 新功能
- 新增 `setCiteText` 方法，支持编程式设置引用文本
- 群聊咨询用户名支持
- 动态群聊名称生成

---

## v1.2.5 <Badge type="info" text="2025-09-12" />

### 新功能
- 新增 `loadRecentSessionOnMount` 属性
- 新增 403 错误页面支持
- 新增人工反馈功能
- 新增选择模式功能

---

## v1.2.4 <Badge type="info" text="2025-09-03" />

### 新功能
- 新增 `beforeRequest` 钩子支持
- 划选过滤增强，改进划选文本检测逻辑
- 新增 `hide` 属性，支持动态控制快捷操作表单组件的显示/隐藏
- 新增 `shortcutFilter` 属性，支持根据选中文本内容动态过滤快捷操作

---

## v1.2.3 <Badge type="info" text="2025-08-12" />

### 新功能
- 新增会话自动命名功能
- 增强快捷指令功能，支持自定义表单交互
- 新增 `extCls` 属性

---

## v1.2.2 <Badge type="info" text="2025-08-06" />

### 新功能
- 新增编程式会话管理 API
- 新增 `addNewSession`、`updateSessionName`、`switchToSession`、`getSessionList` 方法
- 新增 `initialSessionCode` 和 `autoSwitchToInitialSession` 属性

---

## v1.2.0 <Badge type="info" text="2025-07-30" />

### 新功能
- 新增自定义表单输入功能
- 快捷操作接口从 `ShortCut` 升级为 `IShortcut`
- 新增 `components` 组件配置

### 破坏性变更
- 快捷操作接口由 `ShortCut` 更改为 `IShortcut`
- 快捷操作改为将表单数据发送到后端，需要后端适配

---

## v1.1.0 <Badge type="info" text="2025-07-07" />

### 新功能
- 多会话管理功能
- 动态标题显示
- 新增 `showHistoryIcon` 和 `showNewChatIcon` 属性

### 破坏性变更
- 会话管理架构重构，后端 SDK 需要更新至最新版

---

## v1.0.0 <Badge type="info" text="2025-05-27" />

### 新功能
- 全新架构设计
- 增强的界面适配能力
- 优化交互体验

### 破坏性变更
- 不再暴露 `sendChat` 方法，请使用 `sendMessage`
- 预设对话内容不再支持 `defaultMessages`，需在平台配置

---

## v0.5.0 <Badge type="info" text="2025-03-28" />

### 新功能
- 全新 UI 设计，界面彻底重构
- 支持窗口拖拽和调整大小
- 新增 Nimbus 支持，内置弹出式交互
- 新增预设提示词列表功能
