# 组件总览

`@blueking/chat-x` 的组件按原子设计方法论分为两层：**原子组件**（基础 UI 单元）和**分子组件**（业务功能单元）。

## 快速选择

| 场景                        | 推荐组件                             |
| --------------------------- | ------------------------------------ |
| 接入完整聊天界面（推荐）    | `ChatContainer`                      |
| 自定义布局的聊天界面        | `MessageContainer` + `ChatInput`     |
| 仅渲染消息列表              | `MessageRender`                      |
| 仅渲染单条消息内容          | `ContentRender`                      |
| 渲染 Markdown / 代码 / 图表 | `MarkdownContent`                    |
| 流式文字打字机效果          | `AnimationText` / `useAnimationText` |
| AI 划词快捷操作             | `AiSelection`                        |
| 快捷指令入口                | `ShortcutBtns` + `ShortcutRender`    |

## 原子组件

职责单一、可独立使用，是分子组件的构建块。→ [查看原子组件详细列表](./atomic/index.md)

### 交互

| 组件名          | 说明                                                  | 文档                                |
| --------------- | ----------------------------------------------------- | ----------------------------------- |
| `ScrollBtn`     | 操作按钮（停止生成 / 返回底部）                       | [查看](./atomic/scroll-btn.md)      |
| `ToolBtn`       | 工具栏图标按钮；内置 10 个预置图标，支持激活 / 禁用态 | [查看](./atomic/tool-btn.md)        |
| `ShortcutBtn`   | 单个快捷指令按钮；`btn` / `menu` 两种布局             | [查看](./atomic/shortcut-btn.md)    |
| `ShortcutBtns`  | 快捷指令按钮组；响应式溢出自动收入"更多"菜单          | [查看](./atomic/shortcut-btns.md)   |
| `FileUploadBtn` | 文件上传触发按钮；多选、类型过滤、2.5MB 校验          | [查看](./atomic/file-upload-btn.md) |
| `AiLoading`     | AI 思考中三色渐变脉冲动画                             | [查看](./atomic/ai-loading.md)      |

### 内容渲染

| 组件名               | 说明                                                | 文档                                     |
| -------------------- | --------------------------------------------------- | ---------------------------------------- |
| `MarkdownContent`    | Markdown 全功能渲染；流式补全、代码高亮、图表、公式 | [查看](./atomic/markdown-content.md)     |
| `AnimationText`      | 流式文本打字机动画                                  | [查看](./atomic/animation-text.md)       |
| `CodeContent`        | 代码块高亮；`highlight.js` 分行缓存，流式支持       | [查看](./atomic/code-content.md)         |
| `MermaidContent`     | Mermaid 图表渲染；三级去重防抖                      | [查看](./atomic/mermaid-content.md)      |
| `LatexContent`       | LaTeX 公式渲染；5 次降级重试                        | [查看](./atomic/latex-content.md)        |
| `TextContent`        | 纯文本气泡；XSS 安全，无 Markdown                   | [查看](./atomic/text-content.md)         |
| `ImageContent`       | 图片渲染；三态状态机，流式防抖                      | [查看](./atomic/image-content.md)        |
| `CiteContent`        | 引用片段气泡，配合 `ChatInput` 使用                 | [查看](./atomic/cite-content.md)         |
| `ReferenceContent`   | 引用文档列表，安全跳转                              | [查看](./atomic/reference-content.md)    |
| `KeyValueContent`    | 键值对展示；固定行高，超长截断                      | [查看](./atomic/key-value-content.md)    |
| `DescPanel`          | 描述面板；JSON 解析 → 键值 / 索引 / 纯文本          | [查看](./atomic/desc-panel.md)           |
| `CommonErrorContent` | 通用错误提示；红色图标 + 文本                       | [查看](./atomic/common-error-content.md) |

## 分子组件

由原子组件组合而成，提供完整业务功能。→ [查看分子组件详细列表](./molecular/index.md)

### 顶层容器（直接使用）

| 组件名             | 说明                                                                 | 文档                                     |
| ------------------ | -------------------------------------------------------------------- | ---------------------------------------- |
| `ChatContainer`    | 完整聊天容器；整合消息列表 + 输入框 + 执行摘要 + 分栏布局 + 分享模式 | [查看](./molecular/chat-container.md)    |
| `MessageContainer` | 消息列表容器；自动滚动管理、Teleport 挂载点注册                      | [查看](./molecular/message-container.md) |
| `ChatInput`        | 聊天输入框；`/` Prompt、`@` 资源、引用、文件上传、快捷指令           | [查看](./molecular/chat-input.md)        |
| `AiSelection`      | AI 划词弹窗；全局事件监听定位选区，触发快捷指令                      | [查看](./molecular/ai-selection.md)      |

### 渲染调度

| 组件名           | 说明                                                          | 文档                                   |
| ---------------- | ------------------------------------------------------------- | -------------------------------------- |
| `MessageRender`  | 消息级调度器；按 `role` 分发到对应消息组件                    | [查看](./molecular/message-render.md)  |
| `ContentRender`  | 内容级调度器；按 `MessageContentType` 分发到原子组件          | [查看](./molecular/content-render.md)  |
| `ToolcallRender` | Tool Call 渲染；折叠 / 展开 + 四态状态机                      | [查看](./molecular/toolcall-render.md) |
| `ShortcutRender` | 快捷指令表单渲染；动态注册 Vue 组件，`watchEffect` 初始化表单 | [查看](./molecular/shortcut-render.md) |

### 消息类型

| 组件名             | 触发条件                     | 说明                                          | 文档                                     |
| ------------------ | ---------------------------- | --------------------------------------------- | ---------------------------------------- |
| `UserMessage`      | `role: user`                 | 用户消息气泡；蓝色背景，支持复制              | [查看](./molecular/user-message.md)      |
| `AssistantMessage` | `role: assistant`            | AI 消息；完整状态机，含推理 / ToolCall / 文件 | [查看](./molecular/assistant-message.md) |
| `LoadingMessage`   | `assistant` + `Pending`      | AI 思考中占位动画                             | [查看](./molecular/loading-message.md)   |
| `ReasoningMessage` | `assistant` + 推理内容       | 推理过程折叠面板                              | [查看](./molecular/reasoning-message.md) |
| `ActivityMessage`  | `assistant` + `activityType` | 文件引用 / 搜索结果等活动消息                 | [查看](./molecular/activity-message.md)  |
| `ToolMessage`      | `role: tool`                 | Tool 返回结果；`DescPanel` 渲染 JSON          | [查看](./molecular/tool-message.md)      |
| `InfoMessage`      | `role: info`                 | 系统信息提示；居中灰色气泡                    | [查看](./molecular/info-message.md)      |

### 通用功能

| 组件名                | 说明                                              | 文档                                     |
| --------------------- | ------------------------------------------------- | ---------------------------------------- |
| `MessageTools`        | 消息工具栏；复制 / 点赞 / 踩 / 重新生成           | [查看](./molecular/message-tools.md)     |
| `MessageUserFeedback` | 用户反馈弹层；踩后弹出原因选择表单                | [查看](./molecular/user-feedback.md)     |
| `ExecutionSummary`    | 执行摘要面板；时间线展示工具调用和 FlowAgent 记录 | [查看](./molecular/execution-summary.md) |
| `FileContent`         | 附件文件展示；图标 + 文件名 + 大小                | [查看](./molecular/file-content.md)      |

## 组件层级关系

```
ChatContainer（完整聊天容器）
├── ResizeLayout（分栏布局）
│   ├── aside（侧边栏）
│   │   ├── Tab（执行情况 + 自定义 Tab）
│   │   ├── ExecutionSummary（执行摘要面板）
│   │   │   ├── HighlightKeyword（关键词高亮）
│   │   │   └── MessageRender × N
│   │   └── 自定义 Tab 组件（component :is）
│   └── main（主内容区）
│       ├── MessageContainer
│       ├── SelectionFooter（分享模式）
│       ├── ShortcutRender（快捷指令表单）
│       └── ChatInput
└── 欢迎页（无消息时）

MessageContainer
├── useContainerScrollProvider（滚动管理）
├── useGlobalConfig（Teleport 挂载点注册）
├── MessageRender × N
│   ├── UserMessage          [role: user]
│   │   ├── TextContent / KeyValueContent
│   │   └── FileContent?
│   ├── AssistantMessage     [role: assistant]
│   │   ├── ReasoningMessage?
│   │   │   └── MarkdownContent
│   │   ├── ActivityMessage?
│   │   │   └── AiLoading
│   │   ├── ContentRender
│   │   │   ├── MarkdownContent
│   │   │   │   ├── CodeContent
│   │   │   │   ├── MermaidContent
│   │   │   │   ├── LatexContent
│   │   │   │   └── ImageContent
│   │   │   ├── TextContent
│   │   │   ├── CiteContent
│   │   │   ├── ReferenceContent
│   │   │   └── KeyValueContent
│   │   ├── ToolcallRender?
│   │   │   └── ToolMessage
│   │   └── FileContent?
│   ├── LoadingMessage       [assistant + Pending]
│   │   └── AiLoading
│   ├── InfoMessage          [role: info]
│   ├── ToolMessage          [role: tool]
│   │   └── DescPanel
│   └── ActivityMessage      [role: assistant + activityType]
└── MessageTools（每条消息悬浮工具栏）
    ├── ToolBtn × N
    └── MessageUserFeedback（踩后弹出）

ChatInput
├── CiteContent?（引用气泡）
├── AiSlashInput（富文本编辑器）
│   ├── / → Prompt 菜单
│   └── @ → 资源菜单
├── ShortcutBtns?
│   ├── ShortcutBtn × N（可见）
│   └── ShortcutBtn × N（更多菜单）
└── FileUploadBtn?

AiSelection（全局划词弹窗）
└── ShortcutBtn × N（快捷指令列表）
```

## 引入方式

### 常用组件

```typescript
import {
  // 顶层容器
  ChatContainer,
  MessageContainer,
  ChatInput,
  AiSelection,

  // 调度器（按需使用）
  MessageRender,
  ContentRender,

  // 原子内容渲染
  MarkdownContent,
  AnimationText,
  TextContent,
  CiteContent,
  ReferenceContent,

  // 交互原子
  ScrollBtn,
  ToolBtn,
  ShortcutBtn,
  ShortcutBtns,

  // 枚举 & 类型
  MessageStatus,
  MessageRole,
  MessageContentType,
  type Message,
  type Shortcut,
} from '@blueking/chat-x';
```

### 完整导入（含内部组件）

```typescript
import {
  // 消息类型组件
  UserMessage,
  AssistantMessage,
  LoadingMessage,
  ReasoningMessage,
  ActivityMessage,
  ToolMessage,
  InfoMessage,

  // 功能组件
  MessageTools,
  MessageUserFeedback,
  ExecutionSummary,
  FileContent,
  ToolcallRender,
  ShortcutRender,

  // 原子内部组件
  AiLoading,
  FileUploadBtn,
  HighlightKeyword,
  SelectionFooter,
  CodeContent,
  MermaidContent,
  LatexContent,
  ImageContent,
  KeyValueContent,
  DescPanel,
  CommonErrorContent,
} from '@blueking/chat-x';
```
