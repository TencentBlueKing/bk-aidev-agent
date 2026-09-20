# InputAttachment 输入附件区

> 能力域：输入交互 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

ChatInput 底部附件区布局，承载快捷按钮、文件与发送图标。 源码位置：src/components/chat-input/input-attachment/input-attachment.vue。

---

# InputAttachment 输入附件区

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/input-attachment/input-attachment.vue`
- **能力说明**：ChatInput 底部附件区布局，承载快捷按钮、文件与发送图标。
- **交互说明**：
  - `sendMessage` 点击绑定在 `.send-message-icon` 容器上（覆盖图标与按钮空白区域），而非仅绑定在 `SendMessageIcon` 上。
  - `Streaming` / `Pending` / `Fetching` 时展示 `LoadingMessageIcon`，点击发出 `stopSending`。
  - `Disabled`、`sendDisabledTip`、`Pending`、`Streaming` 状态下点击发送容器不会发出 `sendMessage`。

## API 摘要

### Props

- `{ messageState?: MessageStatus; sendDisabledTip?: string; tippyOptions?: AITippyProps; }`

### Emits

- `{ (e: 'sendMessage'): void; (e: 'stopSending'): void; }`

### Slots

- `default`
- `before-send`（发送按钮左侧区域，ChatInput 默认在此渲染 ModelSelector）
- `send-icon`

### Expose

- 无。

## 组件依赖

- 无组件依赖或仅依赖基础库。

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
- 自定义 `send-icon` 插槽时需自行处理发送/停止点击逻辑。
