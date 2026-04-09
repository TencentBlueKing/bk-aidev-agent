# 原子组件

原子组件是 `@blueking/chat-x` 中最基础的 UI 单元，职责单一、可独立使用，作为分子组件的构建块。

## 交互组件

| 组件名             | 说明                                                                                                             | 内部使用方                                              | 文档                           |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------ |
| `ScrollBtn`        | 操作按钮（停止生成 / 返回底部）；支持 `loading` 加载态和 `disabled` 禁用态                                       | `MessageContainer`                                      | [查看](./scroll-btn.md)        |
| `ToolBtn`          | 工具栏图标按钮；内置 10 个预置 SVG 图标（含 `activeLike`/`activeUnLike`），Tippy tooltip，`active`/`disabled` 态 | `MessageTools`                                          | [查看](./tool-btn.md)          |
| `ShortcutBtn`      | 单个快捷指令按钮；`btn`/`menu` 两种布局，图标支持 URL / CSS 类名 / 函数 / 组件                                   | `ShortcutBtns`、`AiSelection`、`ChatInput`              | [查看](./shortcut-btn.md)      |
| `ShortcutBtns`     | 快捷指令按钮组；内置 `useObserverVisibleList` 响应式溢出，超出容器宽度自动收入"更多"菜单                         | `ChatInput`                                             | [查看](./shortcut-btns.md)     |
| `FileUploadBtn`    | 文件上传触发按钮；多选、类型过滤、2.5MB 大小校验、文件数上限（`max(maxFiles, 3)`）                               | `ChatInput`                                             | [查看](./file-upload-btn.md)   |
| `AiLoading`        | AI 思考中动画；SVG 三色（蓝→紫→粉）渐变脉冲，`uid` 隔离多实例渐变 ID                                             | `LoadingMessage`、`ReasoningMessage`、`ActivityMessage` | [查看](./ai-loading.md)        |
| `HighlightKeyword` | 关键词高亮；函数式组件，通过 `inject` 获取搜索关键词，匹配文本自动高亮                                           | `ExecutionSummary`                                      | [查看](./highlight-keyword.md) |
| `SelectionFooter`  | 选择操作栏；消息多选模式底部栏，提供全选/取消/确认操作                                                           | `ChatContainer`                                         | [查看](./selection-footer.md)  |

## 内容渲染组件

### 富文本 / 标记语言

| 组件名            | 说明                                                                                                                                                    | 文档                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| `MarkdownContent` | Markdown 全功能渲染管线；token 分组 → 分发子组件（MermaidContent / LatexContent / CodeContent / VNodeRenderer）；含流式语法补全、throttle、fade-in 动画 | [查看](./markdown-content.md) |
| `CodeContent`     | 代码块高亮渲染；`highlight.js` 分行缓存，流式"当前行"特殊标记，语言映射 Map，复制使用 `innerText`                                                       | [查看](./code-content.md)     |
| `MermaidContent`  | Mermaid 图表渲染；三级去重（代码 → parse → SVG）、throttle、单例 mermaid 实例、SVG ID 随机化                                                            | [查看](./mermaid-content.md)  |
| `LatexContent`    | LaTeX 公式渲染；`katex` + 自动语法补全（7 步）+ 5 次渐进式降级重试，错误白色静默                                                                        | [查看](./latex-content.md)    |
| `AnimationText`   | 流式文本动画；`useAnimationText` composable 将文本分块逐块渐显                                                                                          | [查看](./animation-text.md)   |

### 消息内容展示

| 组件名               | 说明                                                                                                            | 文档                              |
| -------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `TextContent`        | 纯文本气泡（`#e1ecff` 蓝色背景）；`{{ content }}` 文本插值，XSS 安全，无 Markdown                               | [查看](./text-content.md)         |
| `ImageContent`       | 图片渲染；三态状态机（加载中 / 错误 / 图片），全局 URL 缓存，流式防抖（500ms debounce + 100ms throttle）        | [查看](./image-content.md)        |
| `CiteContent`        | 引用片段气泡；显示引用文字 + 关闭按钮，与 `ChatInput` 通过 `v-model:cite` 配合                                  | [查看](./cite-content.md)         |
| `ReferenceContent`   | 引用文档列表；Fragment 根，悬浮显示预览/跳转图标，`window.open(..., 'noopener,noreferrer')` 安全跳转            | [查看](./reference-content.md)    |
| `KeyValueContent`    | 键值对展示；`height: 20px` 固定行高，`text-overflow: ellipsis` 截断，无 tooltip                                 | [查看](./key-value-content.md)    |
| `DescPanel`          | 描述面板；`JSON.parse` 解析 `desc`（对象 → 键值列表 / 数组 → 索引列表 / 其他 → 纯文本），`v-overflow-tips` 悬浮 | [查看](./desc-panel.md)           |
| `CommonErrorContent` | 通用错误提示；红色错误图标（`#ea3636`）+ 文本，XSS 安全                                                         | [查看](./common-error-content.md) |

## 快速参考

### 对外常用组件

直接在业务代码中使用：

```typescript
import {
  ScrollBtn,
  ToolBtn,
  ShortcutBtn,
  ShortcutBtns,
  MarkdownContent,
  AnimationText,
  TextContent,
  CiteContent,
  ReferenceContent,
} from '@blueking/chat-x';
```

### 内部组件

由分子组件内部管理，一般不需要直接使用：

```typescript
import {
  FileUploadBtn, // ChatInput 内部
  AiLoading, // LoadingMessage / ReasoningMessage / ActivityMessage 内部
  HighlightKeyword, // ExecutionSummary 内部
  SelectionFooter, // ChatContainer 内部
  CodeContent, // MarkdownContent 内部
  MermaidContent, // MarkdownContent 内部
  LatexContent, // MarkdownContent 内部
  ImageContent, // MarkdownContent 内部
  KeyValueContent, // UserMessage 内部
  DescPanel, // ToolcallRender / ToolMessage 内部
  CommonErrorContent, // MarkdownContent / ReasoningMessage 内部
} from '@blueking/chat-x';
```
