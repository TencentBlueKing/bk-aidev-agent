---
name: AiSlashEditor 富文本编辑器
slug: ai-slash-editor
kind: component
domain: input
description: 旧版富文本编辑器实现，封装 command selection 与提示菜单。
aiSummary: >
  旧版富文本编辑器实现，封装 command selection 与提示菜单。
  源码位置：src/components/chat-input/ai-slash-editor/ai-slash-editor.vue。
relatedComponents: []
sinceVersion: 1.0.0
---

# AiSlashEditor 富文本编辑器

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/ai-slash-editor/ai-slash-editor.vue`
- **能力说明**：旧版富文本编辑器实现，封装 command selection 与提示菜单。

## API 摘要

### Props

- `{ disabled?: boolean; modelValue?: string; placeholder?: string; prompts?: string[]; }`

### Emits

- `{ (e: 'update:modelValue', value: string): void; (e: 'focus'): void; (e: 'keydown', event: IKeyboardEvent): void; (e: 'layoutChange', layoutInfo: monacoEditor.EditorLayoutInfo): void; }`

### Slots

- 无。

### Expose

- `{ get editor(`

## 组件依赖

- `AiPromptList`
- `AiSlashMenu`

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
