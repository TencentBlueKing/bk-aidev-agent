---
name: AiSlashInput 富文本命令输入
slug: ai-slash-input
kind: component
domain: input
description: ChatInput 内部富文本输入，支持 / Prompt 与 @ 资源标签。
aiSummary: >
  ChatInput 内部富文本输入，支持 / Prompt 与 @ 资源标签。
  源码位置：src/components/chat-input/ai-slash-input/ai-slash-input.vue。
relatedComponents: []
sinceVersion: 1.0.0
---

# AiSlashInput 富文本命令输入

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/ai-slash-input/ai-slash-input.vue`
- **能力说明**：ChatInput 内部富文本输入，支持 / Prompt 与 @ 资源标签。

## API 摘要

### Props

- `{ modelValue: string | TagSchema; placeholder?: string; prompts?: string[]; resources?: IAiSlashMenuItem[]; }`

### Emits

- `{ (e: 'update:modelValue', value: TagSchema, selectedResourceList: IAiSlashMenuItem[]): void; (e: 'keydown', event: KeyboardEvent & KeyboardPayload): void; (e: 'upload', files: File[]): void; }`

### Slots

- 无。

### Expose

- `{ cleanup: (`

## 组件依赖

- `AiPromptList`
- `AiSlashMenu`

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
