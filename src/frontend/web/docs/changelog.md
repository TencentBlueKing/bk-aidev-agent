# 更新日志

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
