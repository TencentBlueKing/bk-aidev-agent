# AiSlashInput 富文本命令输入

> 能力域：输入交互 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

ChatInput 内部富文本编辑区，基于 edix 编辑器渲染「文本 + 资源标签」文档。 自身不渲染菜单，只把触发方式与过滤关键字通过 menuChange 抛给上层，并暴露插入 / 替换 / 关闭菜单等命令。 源码位置：src/components/chat-input/ai-slash-input/ai-slash-input.vue。

**关联**：chat-input（上层输入区，持有菜单状态并调用本组件的 expose 方法）、input-menu-panel（由 menuChange 驱动的菜单面板，选中后回调插入方法）、mention-tag（文档中的 tag 节点由 MentionTag 渲染）

---

# AiSlashInput 富文本命令输入

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/ai-slash-input/ai-slash-input.vue`
- **能力说明**：基于 [edix](/edix/) 的 `contenteditable` 编辑区，文档结构为 `TagSchema`（二维数组：行 → 节点，节点为 `text` 或 `tag`）。
- **职责边界**：只管「编辑 + 触发态识别 + 插入」，**不渲染菜单**。菜单的数据、分组、显隐都在 [ChatInput](/components/input/chat-input) 与 [InputMenuPanel](/components/input/input-menu-panel) 中。

## 触发状态机

触发状态由 `use-menu-trigger.ts` 维护，对外统一为 `{ trigger, keyword }`：

| 触发方式             | 唤起时机                | 过滤关键字来源                             | 选中时消费的字符      |
| -------------------- | ----------------------- | ------------------------------------------ | --------------------- |
| `/` `@` `\`（字符）  | `keydown` 命中触发字符  | 触发符 → 光标之间的非空白文本              | 关键字 + 触发符       |
| `plus`               | 上层调用 `openPlusMenu` | 唤起瞬间光标位置 → 当前光标之间的文本      | 仅关键字              |

- 内容或光标变化后延迟 16ms 重算触发态（等 DOM 应用本次输入），上下文失效（如光标移到触发符之前）时自动关闭。
- `plus` 唤起时若编辑器还没有文本节点（空输入框），关键字保持为空。
- 每次 `trigger` / `keyword` 变化都会 emit `menuChange`。

## 文档与标签

标签是 edix 的 void 节点，识别依据是 `contenteditable="false"` 且带 `data-tag-type` 属性；节点数据全部落在 DOM 属性上，因此文档可以脱离 `menuSources` 独立还原（消息回显与 hover 气泡都依赖这点）：

| 节点数据      | 来源                          | DOM 属性              |
| ------------- | ----------------------------- | --------------------- |
| `label`       | `item.name`                   | `data-tag-label`      |
| `value`       | `item.id`                     | `data-tag-value`      |
| `type`        | `item.type`                   | `data-tag-type`       |
| `icon`        | `item.icon`（仅字符串 URL）   | `data-tag-icon`       |
| `description` | `item.description`            | `data-tag-description` |

序列化为纯文本时，`skill` 输出 `/<value>`，其余类型输出 `@<label>`（见 `constants.ts` 的 `tagSchemaToMessageString`）。

## 与 modelValue 的同步

`modelValue` 支持 `string` 与 `TagSchema` 两种形态：传字符串时经 `stringToDoc` 转成文档。当 `modelValue` 由外部异步更新（历史会话回填、父组件重置、编辑态回填）且与编辑器当前内容不一致时，组件通过 `GetDocSnapshot` 读取快照并与 `docToString(modelValue)` 比对，必要时执行 `ReplaceAll` 同步，避免内外状态脱节。

## 粘贴与换行

- 粘贴内容中包含文件时阻止默认行为并 emit `upload`，交由上层走上传流程；纯文本粘贴保持编辑器默认行为。
- `Enter` 阻止编辑器默认换行（发送与否由上层判断），`Shift + Enter` 正常换行。
- 编辑区默认保持 4 行高度，避免输入后 placeholder 消失导致高度抖动；父级触达 `max-height` 后由本组件内部滚动。

## API

### Props

| 属性名      | 类型                  | 默认值                     | 必填 | 说明                       |
| ----------- | --------------------- | -------------------------- | ---- | -------------------------- |
| modelValue  | `string \| TagSchema` | -                          | ✅   | 编辑器文档                 |
| placeholder | `string`              | `请输入内容` / `Please enter content` | - | 占位文案，经 `aria-placeholder` 渲染，支持 `\n` 多行 |

### Emits

| 事件名            | 参数                                                    | 触发时机                       |
| ----------------- | ------------------------------------------------------- | ------------------------------ |
| update:modelValue | `(value: TagSchema)`                                    | 编辑器内容变化                 |
| keydown           | `(event: KeyboardEvent & KeyboardPayload)`              | 编辑器按键（上层据此判断发送） |
| upload            | `(files: File[])`                                       | 粘贴内容中含文件               |
| menuChange        | `(payload: { keyword: string; trigger: MenuTrigger \| null })` | 触发方式或过滤关键字变化 |

### Expose

| 方法名               | 类型                                     | 说明                                                             |
| -------------------- | ---------------------------------------- | ---------------------------------------------------------------- |
| insertMenuItem       | `(item: IInputMenuItem) => void`         | 消费「触发符 + 关键字」后在光标处插入标签并补一个空格             |
| appendMention        | `(item: IInputMenuItem) => void`         | 在文档末尾追加标签（位置由文档算出，不读光标，供外部无焦点时调用） |
| replaceAll           | `(value: string) => void`                | 整体替换文档内容（Prompt 选中走此路径）                          |
| consumeTriggerText   | `() => [number, number]`                 | 仅删除「触发符 + 关键字」，返回删除后的 `[line, column]`         |
| closeMenu            | `() => void`                             | 关闭触发态                                                       |
| cleanup              | `() => void`                             | 清空文档并关闭触发态（发送后调用）                               |
| focus                | `() => void`                             | 聚焦编辑器并把光标置于末尾                                       |
| openPlusMenu         | `() => void`                             | 唤起 `plus` 聚合菜单；光标已在编辑器内时保持原位                 |

::: tip 为什么 appendMention 不读光标
外部调用（如文件产物面板点「引用」）时编辑器通常没有焦点，而 DOM 选区与编辑器内部选区是异步同步的，依赖光标会把标签插到错误位置，因此位置直接由文档末尾算出。
:::

## 使用建议

直接使用本组件需要自行实现菜单与插入调度，通常应通过 [ChatInput](/components/input/chat-input) 使用。若确需单独接入，最小闭环是：监听 `menuChange` 决定菜单显隐与数据 → 用户选中后调用 `insertMenuItem` / `replaceAll` → 发送后调用 `cleanup`。

## 关联组件

- [ChatInput](/components/input/chat-input) — 上层输入区
- [InputMenuPanel](/components/input/input-menu-panel) — 菜单面板与分组逻辑
- [MentionTag](/components/rendering/mention-tag) — 标签渲染
- [Edix 编辑器引擎](/edix/) — 文档模型与命令机制
