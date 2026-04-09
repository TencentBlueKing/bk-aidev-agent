---
name: useCommandSelection
slug: use-command-selection
category: composable
description: >-
  为 `edix` 富文本编辑器提供光标位置追踪能力的组合式函数。内部封装一个
  `EditorCommand`，由编辑器调用后将光标的行列信息存入响应式变量，供后续编辑命令（如插入 tag、删除关键词）精确定位。
aiSummary: >
  useCommandSelection 无参数，返回 commandSelection（ShallowRef 行列）与 GetCursorPosition（edix EditorCommand）。
  在 editor.command(GetCursorPosition) 时把焦点端写入 commandSelection，供后续 DeleteTag、InsertTag 等命令计算范围。
  仅在 AiSlashInput（@ 菜单插入）内部使用。
relatedComponents:
  - slug: chat-input
    relation: AiSlashInput 内部使用
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { shallowRef } from 'vue';

  // 概念演示：模拟 commandSelection 的行列追踪
  // 实际使用需配合 edix editor.command(GetCursorPosition)
  const commandSelection = shallowRef({ line: 0, column: 0 });
  const demoText = shallowRef('第一行文本\n第二行更长的文本内容\n第三行');

  const handleTextareaKeyUp = (e: KeyboardEvent) => {
    const ta = e.target as HTMLTextAreaElement;
    const pos = ta.selectionStart ?? 0;
    const textBefore = ta.value.slice(0, pos);
    const lines = textBefore.split('\n');
    const line = lines.length - 1;
    const column = (lines[line] ?? '').length;
    commandSelection.value = { line, column };
  };
  const handleTextareaClick = (e: MouseEvent) => {
    handleTextareaKeyUp(e as unknown as KeyboardEvent);
  };
</script>

# useCommandSelection 光标位置追踪

> **分类**：composable

为 `edix` 富文本编辑器提供光标位置追踪能力的组合式函数。内部封装一个 `EditorCommand`，由编辑器调用后将光标的行列信息存入响应式变量，供后续编辑命令（如插入 tag、删除关键词）精确定位。

> 该 composable 仅在 `AiSlashInput` 内部使用，属于编辑器底层基础设施，**通常无需直接调用**。

## 实现原理

```
editor.command(GetCursorPosition)
  │  edix 编辑器将 (doc, selection) 注入 EditorCommand
  │
  └── GetCursorPosition(doc, selection)
        const [, focus] = selection   // selection = [anchor, focus]
        const [line, column] = focus  // focus = [lineIndex, columnIndex]
        commandSelection.value = { column, line }
                                 ↓
               commandSelection（shallowRef，初始值 { column: 0, line: 0 }）
```

**使用时机**：在 `@` 资源插入流程中，先执行 `GetCursorPosition` 快照当前光标，再据此计算删除范围和插入位置。

## 概念演示

`commandSelection` 追踪编辑器光标的 `{ line, column }` 位置（行从 0 开始，column 为字符偏移量）。以下用原生 textarea 模拟等价的位置信息：

> 实际使用时，由 `editor.command(GetCursorPosition)` 触发写入，而非手动计算。

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 8px;">
    <textarea
      :value="demoText"
      @input="e => { demoText = e.target.value; handleTextareaKeyUp(e); }"
      @keyup="handleTextareaKeyUp"
      @click="handleTextareaClick"
      style="width: 100%; height: 80px; padding: 8px; font-size: 13px; font-family: monospace; border: 1px solid #dcdee5; border-radius: 4px; resize: none; box-sizing: border-box; line-height: 1.6;"
    />
    <div style="display: flex; gap: 16px; font-size: 13px; font-family: monospace; color: #4d4f56; background: #f5f7fa; padding: 8px 12px; border-radius: 4px;">
      <span><strong>commandSelection.value =</strong></span>
      <span style="color: #3a84ff;">{ line: {{ commandSelection.line }}, column: {{ commandSelection.column }} }</span>
    </div>
    <p style="margin: 0; font-size: 12px; color: #979ba5;">在文本框中点击或移动光标，观察 commandSelection 的实时变化</p>
  </div>
</div>

## 在 AiSlashInput 中的实际用法

```typescript
const { commandSelection, GetCursorPosition } = useCommandSelection();

// 用户从 @xxx 菜单中选择资源时：
const insertTagAtCursor = (tag: IAiSlashMenuItem) => {
  // 1. 执行命令，快照当前光标位置 → 写入 commandSelection.value
  editor.command(GetCursorPosition);

  // 2. 读取快照的行列位置
  const { column, line } = commandSelection.value;

  // 3. 根据位置删除已输入的 "@keyword"，插入 tag
  editor.command(DeleteTag, [line, column - keyword.value.length - 1], [line, column]);
  editor.command(InsertTag, [line, column], tag);
};
```

## API

### 参数

无。`useCommandSelection()` 不接受任何参数。

### 返回值

| 属性名              | 类型                                           | 初始值                   | 说明                                                                                       |
| ------------------- | ---------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------ |
| `commandSelection`  | `ShallowRef<{ column: number; line: number }>` | `{ column: 0, line: 0 }` | 存储最近一次执行 `GetCursorPosition` 时的光标行列位置                                      |
| `GetCursorPosition` | `EditorCommand<[]>`                            | —                        | 编辑器命令，由 `editor.command(GetCursorPosition)` 触发，将当前光标写入 `commandSelection` |

## 类型说明

```typescript
// EditorCommand：edix 编辑器的命令签名
type EditorCommand<A extends unknown[]> = (
  doc: DocFragment,
  selection: SelectionSnapshot, // [[anchorLine, anchorColumn], [focusLine, focusColumn]]
  ...args: A
) => Transaction | void;

// useCommandSelection 返回值
interface UseCommandSelectionReturn {
  commandSelection: ShallowRef<{ column: number; line: number }>;
  GetCursorPosition: EditorCommand<[]>;
}
```

## 实现源码

```typescript
import { shallowRef } from 'vue';
import type { EditorCommand } from '../edix';

export const useCommandSelection = () => {
  // 存储最近一次快照的光标位置
  const commandSelection = shallowRef<{ column: number; line: number }>({
    column: 0,
    line: 0,
  });

  // EditorCommand：由 editor.command() 调用，注入 doc 和 selection
  const GetCursorPosition: EditorCommand<[]> = (_doc, selection) => {
    const [, focus] = selection; // 取 focus 端（忽略 anchor）
    const [line, column] = focus;
    commandSelection.value = { column, line };
    // 不返回 Transaction，即只读取不修改文档
  };

  return {
    commandSelection,
    GetCursorPosition,
  };
};
```

## 注意事项

1. **只读命令**：`GetCursorPosition` 不返回 `Transaction`，不修改编辑器文档内容，仅记录位置
2. **异步快照**：`commandSelection` 在 `editor.command(GetCursorPosition)` 执行后**同步**更新，下一行代码即可安全读取
3. **`shallowRef` 而非 `ref`**：对象引用替换触发响应式，内部字段修改不触发（此处每次整体替换，无影响）
4. **仅适用于 edix 编辑器**：`GetCursorPosition` 依赖 edix 的 `SelectionSnapshot` 格式，不适用于原生 contenteditable 或其他富文本库

## 关联组件

- [ChatInput](../components/molecular/chat-input.md) — AiSlashInput 子模块使用
