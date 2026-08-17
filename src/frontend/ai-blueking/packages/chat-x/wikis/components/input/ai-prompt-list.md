---
name: AiPromptList Prompt 列表
slug: ai-prompt-list
kind: component
domain: input
description: \ Prompt 选择列表，供 AiSlashInput 插入模板文本。
aiSummary: >
  \ Prompt 选择列表，供 AiSlashInput 插入模板文本。
  源码位置：src/components/chat-input/ai-slash-input/ai-prompt-list/ai-prompt-list.vue。
relatedComponents:
  - slug: ai-slash-input
    relation: 输入 \ 时由 AiSlashInput tippy 菜单渲染
sinceVersion: 1.0.0
---

# AiPromptList Prompt 列表

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/ai-slash-input/ai-prompt-list/ai-prompt-list.vue`
- **能力说明**：`\` Prompt 选择列表，供 AiSlashInput 插入模板文本。


> Prompt 列表面板样式与 Slash/Skill 面板统一。

## API 摘要

### Props

- `{ onSelect: (prompt: string) => void; prompts: string[]; }`

### Emits

- 无。

### Slots

- 无。

### Expose

- 无。

## 组件依赖

- 无组件依赖或仅依赖基础库。

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
