# Edix 编辑器引擎

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { createEditor, plainSchema, InsertText, ReplaceAll, Delete } from '@blueking/chat-x';

// ---- Demo 1: 单行编辑器 ----
const singleLineEl = ref<HTMLElement | null>(null);
const singleLineContent = ref('');
const singleLineSent = ref('');
let singleEditor: ReturnType<typeof createEditor> | null = null;
let singleDispose: (() => void) | null = null;

// ---- Demo 2: 多行编辑器 ----
const multiLineEl = ref<HTMLElement | null>(null);
const multiLineContent = ref('');
let multiEditor: ReturnType<typeof createEditor> | null = null;
let multiDispose: (() => void) | null = null;

// ---- Demo 3: 程序化命令 ----
const cmdEl = ref<HTMLElement | null>(null);
const cmdContent = ref('');
const isReadonly = ref(false);
let cmdEditor: ReturnType<typeof createEditor> | null = null;
let cmdDispose: (() => void) | null = null;

onMounted(() => {
  // 单行编辑器
  if (singleLineEl.value) {
    singleEditor = createEditor({
      doc: '',
      schema: plainSchema(),
      onChange: doc => { singleLineContent.value = doc; },
      onKeyDown: ({ key, shiftKey }) => {
        if (key === 'Enter' && !shiftKey) {
          if (singleLineContent.value.trim()) {
            singleLineSent.value = singleLineContent.value;
            singleEditor?.command(ReplaceAll, '');
          }
          return true;
        }
      },
    });
    singleDispose = singleEditor.input(singleLineEl.value);
  }

  // 多行编辑器
  if (multiLineEl.value) {
    multiEditor = createEditor({
      doc: '',
      schema: plainSchema({ multiline: true }),
      onChange: doc => { multiLineContent.value = doc; },
    });
    multiDispose = multiEditor.input(multiLineEl.value);
  }

  // 命令演示编辑器
  if (cmdEl.value) {
    cmdEditor = createEditor({
      doc: '可以在这里输入内容',
      schema: plainSchema({ multiline: true }),
      onChange: doc => { cmdContent.value = doc; },
    });
    cmdDispose = cmdEditor.input(cmdEl.value);
    cmdContent.value = '可以在这里输入内容';
  }
});

onUnmounted(() => {
  singleDispose?.();
  multiDispose?.();
  cmdDispose?.();
});

const handleInsert = () => cmdEditor?.command(InsertText, ' [插入文本]');
const handleReplaceAll = () => cmdEditor?.command(ReplaceAll, '已替换为全新内容');
const handleDelete = () => cmdEditor?.command(Delete);
const handleToggleReadonly = () => {
  isReadonly.value = !isReadonly.value;
  cmdEditor?.readonly(isReadonly.value);
};
</script>

`Edix` 是 `@blueking/chat-x` 内置的轻量级富文本编辑器引擎，驱动 `ChatInput` 组件的输入功能。

> **使用场景说明**：`Edix` 主要供 `ChatInput` 内部使用，一般无需直接调用。如需定制输入行为，优先通过 `ChatInput` 的 props 配置。若需深度定制（如自定义 void 节点），可参考本文档。

## 核心概念

```
createEditor(options)
       │
       ├── Schema（定义文档格式与序列化策略）
       │     ├── plainSchema()        → string（纯文本）
       │     └── schema({ void })     → 结构化节点数组（支持 mention 等）
       │
       ├── History（撤销/重做栈，500ms 批合并，上限 500 条）
       │
       ├── Transaction（原子编辑操作，microtask 异步批提交）
       │
       └── editor.input(element)     → 绑定 DOM，返回清理函数
             ├── 拦截 beforeinput（全类型处理）
             ├── 处理 IME 组合输入
             ├── 处理 copy / cut / paste / drag
             └── 处理 keydown（Ctrl+Z 撤销 / Ctrl+Shift+Z 重做）
```

## 快速上手

### 纯文本单行编辑器

按 `Enter` 发送，`Shift+Enter` 无效（单行模式禁止换行）。

<div class="demo">
  <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
    <div
      ref="singleLineEl"
      style="min-height: 36px; padding: 6px 12px; border: 1px solid #c4c6cc; border-radius: 4px; outline: none; font-size: 14px; line-height: 22px; cursor: text;"
      placeholder="输入内容，按 Enter 发送..."
    ></div>
    <div style="display: flex; gap: 8px; align-items: center; font-size: 13px; color: #63656e;">
      <span>当前内容：</span>
      <code style="padding: 2px 6px; background: #f0f1f5; border-radius: 3px;">{{ singleLineContent || '（空）' }}</code>
    </div>
    <div v-if="singleLineSent" style="padding: 8px 12px; background: #e1ecff; border-radius: 4px; font-size: 13px; color: #3a84ff;">
      已发送：{{ singleLineSent }}
    </div>
    <div style="font-size: 12px; color: #979ba5;">↵ Enter 发送 | Ctrl+Z 撤销 | Ctrl+Shift+Z 重做</div>
  </div>
</div>

```typescript
import { createEditor, plainSchema, ReplaceAll } from '@blueking/chat-x';

// plainSchema() 不传参数 = 单行模式（禁止换行）
const editor = createEditor({
  doc: '',
  schema: plainSchema(), // ← 注意：是函数调用，不是直接引用
  onChange: (doc: string) => {
    console.log('内容变化:', doc);
  },
  onKeyDown: ({ key, shiftKey }) => {
    if (key === 'Enter' && !shiftKey) {
      // 返回 true → 调用 e.preventDefault()，阻止默认换行
      handleSend();
      editor.command(ReplaceAll, '');
      return true;
    }
  },
});

// 绑定到 DOM（元素无需手动设 contenteditable，editor 会自动处理）
const el = document.querySelector<HTMLElement>('#editor')!;
const dispose = editor.input(el);

// 清理（解绑所有事件，恢复元素原始状态）
dispose();
```

### 纯文本多行编辑器

`Shift+Enter` 换行，`Ctrl+Z` 撤销。

<div class="demo">
  <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
    <div
      ref="multiLineEl"
      style="min-height: 80px; padding: 6px 12px; border: 1px solid #c4c6cc; border-radius: 4px; outline: none; font-size: 14px; line-height: 22px; cursor: text;"
    ></div>
    <div style="display: flex; gap: 8px; align-items: flex-start; font-size: 13px; color: #63656e;">
      <span style="flex-shrink: 0;">内容（含换行）：</span>
      <code style="padding: 2px 6px; background: #f0f1f5; border-radius: 3px; white-space: pre-wrap; word-break: break-all;">{{ multiLineContent || '（空）' }}</code>
    </div>
    <div style="font-size: 12px; color: #979ba5;">Shift+Enter 换行 | Ctrl+Z 撤销 | Ctrl+Shift+Z 重做</div>
  </div>
</div>

```typescript
import { createEditor, plainSchema } from '@blueking/chat-x';

const editor = createEditor({
  doc: '',
  schema: plainSchema({ multiline: true }), // ← 传 multiline: true 启用多行
  onChange: (doc: string) => {
    // doc 为 string，换行符为 '\n'
    console.log(doc);
  },
});
```

### 结构化编辑器（含自定义 void 节点）

`ChatInput` 内部使用此模式支持 `@mention` 标签。

```typescript
import { createEditor, schema, voidNode } from '@blueking/chat-x';

// 1. 定义 void 节点序列化器
const mentionNode = voidNode({
  // 识别：DOM 中有 data-mention 属性的元素
  is: (el: HTMLElement) => el.hasAttribute('data-mention'),
  // 读取数据：从 DOM 读入编辑器内部状态
  data: (el: HTMLElement) => ({
    id: el.dataset.mentionId!,
    label: el.dataset.mentionLabel!,
  }),
  // 纯文本降级：复制/粘贴时输出的纯文本表示
  plain: data => `@${data.label}`,
});

// 2. 创建 schema（单行，含 mention void 节点）
const editorSchema = schema({
  void: { mention: mentionNode },
  // multiline: true  // 可选，启用多行
});

// 3. doc 类型由 schema 自动推导：
//    单行 → ({ type: 'text'; text: string } | { type: 'mention'; data: { id: string; label: string } })[]
//    多行 → 上述行数组[]
const editor = createEditor({
  doc: [],
  schema: editorSchema,
  onChange: doc => {
    // 遍历节点，区分 text 和 mention
    for (const node of doc) {
      if (node.type === 'text') {
        console.log('文本:', node.text);
      } else if (node.type === 'mention') {
        console.log('提及:', node.data.label);
      }
    }
  },
});
```

## API

### `createEditor<T>(options)`

创建编辑器实例。

```typescript
interface EditorOptions<T> {
  /** 初始文档内容，类型由 schema 决定 */
  doc: T;

  /** 文档 Schema，决定内部表示 ↔ JS 值的互转策略 */
  schema: DocSchema<T>;

  /**
   * 自定义块级元素判断（影响粘贴 HTML 时的段落解析）
   * 默认使用内置 defaultIsBlockNode
   */
  isBlock?: (node: HTMLElement) => boolean;

  /** 文档内容变化时触发，doc 已序列化为 JS 值 */
  onChange: (doc: T) => void;

  /**
   * keydown 回调（IME 组合输入期间不触发）
   * 返回 true → e.preventDefault()（阻止默认行为）
   * 返回 false / undefined → 不阻止
   */
  onKeyDown?: (keyboard: KeyboardPayload) => boolean | void;
}

type KeyboardPayload = Pick<KeyboardEvent, 'altKey' | 'code' | 'ctrlKey' | 'key' | 'metaKey' | 'shiftKey'>;
```

### `Editor` 实例方法

| 方法       | 签名                                            | 说明                                                                                                                                                                                |
| ---------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `input`    | `(element: HTMLElement) => () => void`          | 绑定 DOM 元素，返回清理函数。会自动设置 `contenteditable`、`role="textbox"`、`white-space: pre-wrap`。需要浏览器支持 `beforeinput` 事件（`InputEvent.prototype.getTargetRanges`）。 |
| `command`  | `<A>(fn: EditorCommand<A>, ...args: A) => void` | 执行编辑命令，通过 microtask 异步批量提交 Transaction。只读模式下无效。                                                                                                             |
| `readonly` | `(value: boolean) => void`                      | 切换只读状态，同步更新元素的 `contenteditable` 和 `aria-readonly`。                                                                                                                 |

### Schema 工厂

#### `plainSchema(options?)`

纯文本 Schema，`doc` 类型为 `string`。

```typescript
function plainSchema(options?: { multiline?: boolean }): DocSchema<string>;
```

| 参数        | 默认值  | 说明                                                          |
| ----------- | ------- | ------------------------------------------------------------- |
| `multiline` | `false` | `false` = 单行（`\n` 被自动过滤）；`true` = 多行（`\n` 保留） |

复制时写入 `text/plain`；粘贴时读取 `text/plain`。

#### `schema(options)`

结构化 Schema，支持自定义 void 节点（如 mention、tag）。

```typescript
function schema<V extends Record<string, EditableVoidSerializer<any>>, M extends boolean = false>(options: {
  multiline?: M;
  void?: V;
}): DocSchema<
  M extends true
    ? (TextNode | VoidNode<V>)[][] // 多行
    : (TextNode | VoidNode<V>)[] // 单行
>;
```

复制时同时写入 `text/html`（保留 DOM 结构）和 `text/plain`（由 `plain()` 降级）；粘贴时优先读取 `text/html`。

#### `voidNode(options)`

定义 void 节点序列化器（供 `schema` 的 `void` 选项使用）。

```typescript
function voidNode<D>(options: {
  /** 识别 DOM 元素是否属于此 void 节点类型 */
  is: (node: HTMLElement) => boolean;
  /** 从 DOM 元素读取节点数据 */
  data: (node: HTMLElement) => D;
  /** 纯文本降级（复制/粘贴时），默认返回空字符串 */
  plain?: (data: D) => string;
}): EditableVoidSerializer<D>;
```

### 内置命令

命令函数类型：`EditorCommand<A> = (doc, selection, ...args: A) => Transaction | void`

| 命令         | 签名                            | 说明                                 |
| ------------ | ------------------------------- | ------------------------------------ |
| `InsertText` | `EditorCommand<[text: string]>` | 先删除当前选区，再在起始位置插入文本 |
| `Delete`     | `EditorCommand<[]>`             | 删除当前选区                         |
| `ReplaceAll` | `EditorCommand<[text: string]>` | 清空全文并替换为新内容               |

<div class="demo">
  <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
    <div
      ref="cmdEl"
      style="min-height: 60px; padding: 6px 12px; border: 1px solid #c4c6cc; border-radius: 4px; outline: none; font-size: 14px; line-height: 22px; cursor: text;"
    ></div>
    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
      <button
        @click="handleInsert"
        :disabled="isReadonly"
        style="padding: 4px 12px; border: 1px solid #c4c6cc; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer;"
        :style="{ opacity: isReadonly ? 0.5 : 1 }"
      >InsertText（光标处插入）</button>
      <button
        @click="handleReplaceAll"
        :disabled="isReadonly"
        style="padding: 4px 12px; border: 1px solid #c4c6cc; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer;"
        :style="{ opacity: isReadonly ? 0.5 : 1 }"
      >ReplaceAll（替换全文）</button>
      <button
        @click="handleDelete"
        :disabled="isReadonly"
        style="padding: 4px 12px; border: 1px solid #c4c6cc; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer;"
        :style="{ opacity: isReadonly ? 0.5 : 1 }"
      >Delete（删除选区）</button>
      <button
        @click="handleToggleReadonly"
        style="padding: 4px 12px; border: 1px solid #3a84ff; border-radius: 4px; font-size: 13px; cursor: pointer;"
        :style="{ background: isReadonly ? '#3a84ff' : '#fff', color: isReadonly ? '#fff' : '#3a84ff' }"
      >{{ isReadonly ? '只读（点击解除）' : '可编辑（点击锁定）' }}</button>
    </div>
    <div style="font-size: 13px; color: #63656e; display: flex; gap: 8px; align-items: flex-start;">
      <span style="flex-shrink: 0;">内容：</span>
      <code style="padding: 2px 6px; background: #f0f1f5; border-radius: 3px; white-space: pre-wrap; word-break: break-all;">{{ cmdContent || '（空）' }}</code>
    </div>
    <div style="font-size: 12px; color: #979ba5;">先在编辑器内选中文字，再点击按钮观察效果 | Ctrl+Z 撤销（注意：command() 不计入历史）</div>
  </div>
</div>

```typescript
editor.command(InsertText, 'Hello'); // 插入文本（替换选区）
editor.command(Delete); // 删除选区
editor.command(ReplaceAll, 'New text'); // 替换全文
```

### 自定义命令

实现 `EditorCommand` 接口即可：

```typescript
import type { EditorCommand } from '@blueking/chat-x';

// 示例：在文档末尾追加文本
const AppendText: EditorCommand<[text: string]> = (doc, _selection, text) => {
  const lastLine = doc.length - 1;
  const lastCol = doc[lastLine]?.length ?? 0;
  return new Transaction()
    .select([lastLine, lastCol], [lastLine, lastCol])
    .insert([lastLine, lastCol], stringToDoc(text));
};

editor.command(AppendText, '追加内容');
```

## 键盘事件处理

`onKeyDown` 在 `keydown` 事件时触发（**IME 组合输入期间跳过**）。

```typescript
const editor = createEditor({
  schema: plainSchema(),
  doc: '',
  onChange: () => {},
  onKeyDown: ({ key, ctrlKey, shiftKey, metaKey }) => {
    const isModifier = ctrlKey || metaKey;

    // Enter 发送消息（单行模式推荐）
    if (key === 'Enter' && !shiftKey) {
      handleSend();
      return true; // 阻止默认的换行/段落插入
    }

    // Shift+Enter 插入换行（多行模式）
    // 不返回 true，让编辑器处理默认行为

    // Escape 清空
    if (key === 'Escape') {
      editor.command(ReplaceAll, '');
      return true;
    }
  },
});
```

> **注意**：`Ctrl+Z` / `Ctrl+Shift+Z` 由编辑器**内部处理**，不会传递给 `onKeyDown`。

## 撤销 / 重做

编辑器内置历史记录，无需额外配置：

| 快捷键                         | 行为 |
| ------------------------------ | ---- |
| `Ctrl+Z` / `Cmd+Z`             | 撤销 |
| `Ctrl+Shift+Z` / `Cmd+Shift+Z` | 重做 |

**历史记录策略**：

- 500ms 内的连续编辑合并为同一条历史（批合并）
- 最多保留 500 条历史，超出时丢弃最早的记录
- `editor.command()` 执行的命令**不计入**历史，仅用户交互操作才记录

## 编辑器自动处理的事件

调用 `editor.input(element)` 后，编辑器会接管以下原生事件：

| 事件                     | 处理方式                                               |
| ------------------------ | ------------------------------------------------------ |
| `beforeinput`            | 全部拦截（`e.preventDefault()`），转为内部 Transaction |
| `compositionstart / end` | IME 组合输入开始/结束，期间暂存 mutation 并回滚后提交  |
| `keydown`                | 处理 Undo/Redo，其余转发给 `onKeyDown`                 |
| `copy / cut`             | 调用 schema 的 `copy` 方法序列化到剪贴板               |
| `paste`                  | 调用 schema 的 `paste` 方法解析剪贴板内容              |
| `drop`                   | 支持拖放文本，内部拖动会先删除源位置内容               |
| `selectionchange`        | 同步光标/选区快照到内部状态                            |

`beforeinput` 拦截覆盖的操作类型包括：`insertText`、`insertParagraph`（→`\n`）、`insertLineBreak`（→`\n`）、`deleteContent*`（各方向删除）、`insertFromPaste`、`insertReplacementText` 等。**`format*`（富文本格式化）和 `historyUndo/Redo` 被忽略**。

## 类型工具

```typescript
import type { InferDoc, InferNode, DocSchema } from '@blueking/chat-x';

const mySchema = schema({ void: { mention: mentionNode } });

// 推导 doc 类型
type MyDoc = InferDoc<typeof mySchema>;
// → ({ type: 'text'; text: string } | { type: 'mention'; data: { id: string; label: string } })[]

// 推导单个节点类型
type MyNode = InferNode<typeof mySchema>;
// → { type: 'text'; text: string } | { type: 'mention'; data: { id: string; label: string } }
```

## 注意事项

1. **`plainSchema` 是函数**：必须调用 `plainSchema()` 或 `plainSchema({ multiline: true })`，不能直接赋值 `schema: plainSchema`
2. **`schema` 而非 `structuredSchema`**：结构化模式使用 `schema()`，`structuredSchema` 不存在
3. **需要 `beforeinput` 支持**：`editor.input()` 运行时检查 `InputEvent.prototype.getTargetRanges`，不支持的浏览器会打印 error 并跳过绑定
4. **无需手动 `contenteditable`**：`editor.input()` 会自动设置；清理函数会恢复原始值
5. **`command()` 异步提交**：通过 `microtask` 批量提交，多次 `command()` 调用会合并到同一 microtask
6. **只读模式下 `command()` 无效**：`editor.readonly(true)` 后，调用 `command()` 不会执行任何操作
