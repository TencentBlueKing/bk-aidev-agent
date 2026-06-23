# InputAttachment 输入附件区

> 能力域：输入交互 ｜ 导入：`import { InputAttachment } from '@blueking/chat-x'` ｜ since 1.0.0

ChatInput 底部附件区布局，承载快捷按钮、文件与发送图标。 源码位置：src/components/chat-input/input-attachment/input-attachment.vue。

---

# InputAttachment 输入附件区

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/input-attachment/input-attachment.vue`
- **能力说明**：ChatInput 底部附件区布局，承载快捷按钮、文件与发送图标。

## API 摘要

### Props

- `{ messageState?: MessageStatus; sendDisabledTip?: string; tippyOptions?: AITippyProps; }`

### Emits

- `{ (e: 'sendMessage'): void; (e: 'stopSending'): void; }`

### Slots

- `default`
- `send-icon`

### Expose

- 无。

## 组件依赖

- 无组件依赖或仅依赖基础库。

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
