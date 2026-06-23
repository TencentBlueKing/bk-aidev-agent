# useCommandSelection

> 导入：`import { useCommandSelection } from '@blueking/chat-x'` ｜ since 1.0.0

useCommandSelection 无参数，返回 commandSelection、docSnapshot、GetCursorPosition、GetDocSnapshot。 GetCursorPosition 写入光标行列；GetDocSnapshot 将当前文档快照写入 docSnapshot，供外部 modelValue 与编辑器比对同步。 仅在 AiSlashInput（@ 菜单插入与 modelValue 同步）内部使用。

**关联**：chat-input（AiSlashInput 内部使用）

---

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

editor.command(GetDocSnapshot)
  └── GetDocSnapshot(doc)
        docSnapshot.value = doc   // 当前文档快照，用于与 props.modelValue 比对
```

**使用时机**：

- 在 `@` 资源插入流程中，先执行 `GetCursorPosition` 快照当前光标，再据此计算删除范围和插入位置。
- 在外部 `modelValue` 变化时，先执行 `GetDocSnapshot` 取得编辑器当前文档，与 `docToString(modelValue)` 比对，决定是否 `ReplaceAll` 同步。

## 概念演示

`commandSelection` 追踪编辑器光标的 `{ line, column }` 位置（行从 0 开始，column 为字符偏移量）。以下用原生 textarea 模拟等价的位置信息：

> 实际使用时，由 `editor.command(GetCursorPosition)` 触发写入，而非手动计算。

## 在 AiSlashInput 中的实际用法

```typescript
import { watch } from 'vue';

const { commandSelection, GetCursorPosition, GetDocSnapshot, docSnapshot } = useCommandSelection();

// 用户从 @xxx 菜单中选择资源时：
const insertTagAtCursor = (tag: IAiSlashMenuItem) => {
  editor.command(GetCursorPosition);
  const { column, line } = commandSelection.value;
  editor.command(DeleteTag, [line, column - keyword.value.length - 1], [line, column]);
  editor.command(InsertTag, [line, column], tag);
};

// 外部 modelValue 变化时，与编辑器文档对齐（简化示意；需已存在 editor、props、text、docToString）
watch(
  () => props.modelValue,
  () => {
    editor.command(GetDocSnapshot);
    if (docToString(docSnapshot.value || []) !== docToString(text.value || [])) {
      editor.command(ReplaceAll, docToString(text.value || []) as unknown as string);
    }
  },
  { deep: false },
);
```

## API

### 参数

无。`useCommandSelection()` 不接受任何参数。

### 返回值

| 属性名              | 类型                                           | 初始值                   | 说明                                                                                       |
| ------------------- | ---------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------ |
| `commandSelection`  | `ShallowRef<{ column: number; line: number }>` | `{ column: 0, line: 0 }` | 存储最近一次执行 `GetCursorPosition` 时的光标行列位置                                      |
| `docSnapshot`       | `ShallowRef<DocFragment>`                      | `[]`                     | 存储最近一次执行 `GetDocSnapshot` 时的文档快照                                             |
| `GetCursorPosition` | `EditorCommand<[]>`                            | —                        | 编辑器命令，由 `editor.command(GetCursorPosition)` 触发，将当前光标写入 `commandSelection` |
| `GetDocSnapshot`    | `EditorCommand<[]>`                            | —                        | 编辑器命令，由 `editor.command(GetDocSnapshot)` 触发，将当前文档写入 `docSnapshot`       |

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
  docSnapshot: ShallowRef<DocFragment>;
  GetCursorPosition: EditorCommand<[]>;
  GetDocSnapshot: EditorCommand<[]>;
}
```

## 实现源码

```typescript
import { shallowRef } from 'vue';

import type { EditorCommand } from '../edix';
import type { DocFragment } from '../edix/doc/types';

export const useCommandSelection = () => {
  const commandSelection = shallowRef<{ column: number; line: number }>({ column: 0, line: 0 });
  const docSnapshot = shallowRef<DocFragment>([]);

  const GetCursorPosition: EditorCommand<[]> = (_doc, selection) => {
    const [, focus] = selection;
    const [line, column] = focus;
    commandSelection.value = { column, line };
  };

  const GetDocSnapshot: EditorCommand<[]> = doc => {
    docSnapshot.value = doc;
  };

  return {
    commandSelection,
    docSnapshot,
    GetCursorPosition,
    GetDocSnapshot,
  };
};
```

## 注意事项

1. **只读命令**：`GetCursorPosition` 不返回 `Transaction`，不修改编辑器文档内容，仅记录位置
2. **异步快照**：`commandSelection` 在 `editor.command(GetCursorPosition)` 执行后**同步**更新，下一行代码即可安全读取
3. **`shallowRef` 而非 `ref`**：对象引用替换触发响应式，内部字段修改不触发（此处每次整体替换，无影响）
4. **仅适用于 edix 编辑器**：`GetCursorPosition` / `GetDocSnapshot` 依赖 edix 的文档与选区格式，不适用于原生 contenteditable 或其他富文本库

## 关联组件

- [ChatInput](../components/input/chat-input) — AiSlashInput 子模块使用
