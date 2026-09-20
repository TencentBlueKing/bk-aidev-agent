# MentionTag 资源标签

> 能力域：内容渲染 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 0.0.51

MentionTag 渲染「图标 + 蓝色名称」的内联资源标签：节点数据全部落在 data-tag-* 属性上， 既是编辑器 void 节点的识别依据，也让消息里复制的标签能原样还原； description 非空时 hover / 点击弹出「类型：名称 + 描述」气泡；type 为 artifact 且存在产物预览上下文时点击打开侧栏预览。 源码位置：src/components/mention/mention-tag.vue（气泡见 mention-popover.vue 与 create-mention-tippy.ts）。

**关联**：mention-text（按文档结构批量渲染标签与文本）、ai-slash-input（编辑器内的 tag 节点由本组件渲染）、resource-icon（标签左侧图标）、file-artifact-panel（artifact 标签点击后打开的侧栏预览）

---

# MentionTag 资源标签

> **能力域**：内容渲染

## 源码事实

- **标签**：`src/components/mention/mention-tag.vue`
- **气泡内容**：`src/components/mention/mention-popover.vue`
- **气泡配置**：`src/components/mention/create-mention-tippy.ts`
- **能力说明**：设计稿形态为「图标 + 蓝色文字」内联展示，无背景块；高度 22px，`vertical-align: bottom`。

## data-tag-\* 属性

标签把节点数据全部写在 DOM 属性上，这不是冗余：

| 属性                   | 作用                                                     |
| ---------------------- | -------------------------------------------------------- |
| `data-tag-type`        | 与 `contenteditable="false"` 一起作为编辑器 void 节点的识别依据 |
| `data-tag-value`       | 资源 id，`artifact` 点击预览、`skill` 序列化都取它        |
| `data-tag-label`       | 展示名，避免从 `textContent` 读取时混入图标带来的空白     |
| `data-tag-icon`        | 图标 URL（组件形式的图标无法序列化，此时为空）            |
| `data-tag-description` | 描述文案，让气泡脱离 `menuSources` 独立工作               |

因此从消息里复制一段带标签的文本再粘贴回输入框，标签能被原样还原。

## 交互

- **描述气泡**：`description` 非空时才创建气泡（否则 `onShow` 直接返回 `false`）。标题格式为 `类型：名称`，类型名与菜单分组标题同源（`getMenuTypeLabel`）。
- **触发方式**：`mouseenter focus click`，展示延迟 300ms、关闭无延迟；`hideOnClick` 关闭并改用 `onClickOutside` 收起，因此再次点击标签不会把气泡收掉，触屏也能点开。
- **产物预览**：`type` 为 `artifact` 且存在 [useArtifactPreview](/composables/use-artifact-preview) 上下文时，点击标签以 `{ file: { outputId: value } }` 打开侧栏预览。
- **可交互暗示**：仅在「有描述」或「可预览」时给出 `cursor: pointer` 与名称下划线。

::: info 为什么用指令而不是 `<Tippy>` 组件
标签渲染在 `contenteditable` 内部，多包一层元素会干扰编辑器对 void 节点的识别与 DOM 比对，因此气泡走 `v-tippy` 指令。
:::

## 渲染示例

> 前三个标签中「翻译」「天气查询」带描述，hover 可见气泡；`artifact` 标签在有产物预览上下文时可点击。

## API

### Props

| 属性名      | 类型     | 必填 | 说明                                                  |
| ----------- | -------- | ---- | ----------------------------------------------------- |
| label       | `string` | ✅   | 标签展示名                                            |
| value       | `string` | ✅   | 资源 id                                               |
| type        | `string` | ✅   | 资源类型，决定兜底图标、气泡标题与是否可预览          |
| icon        | `string` | -    | 图标 URL；缺省时按 `type` 兜底                        |
| description | `string` | -    | 描述文案，非空时启用气泡                              |

### MentionPopover Props

| 属性名      | 类型     | 必填 | 说明                                 |
| ----------- | -------- | ---- | ------------------------------------ |
| title       | `string` | ✅   | 形如「工具：天气查询」               |
| description | `string` | -    | 描述正文，最大宽度 240px，自动换行   |

### Emits / Slots / Expose

- 无。

## 关联组件

- [MentionText](/components/rendering/mention-text) — 按文档结构批量渲染
- [AiSlashInput](/components/input/ai-slash-input) — 编辑器内的标签宿主
- [ResourceIcon](/components/helper/resource-icon) — 标签图标
- [useArtifactPreview](/composables/use-artifact-preview) — 产物预览上下文
