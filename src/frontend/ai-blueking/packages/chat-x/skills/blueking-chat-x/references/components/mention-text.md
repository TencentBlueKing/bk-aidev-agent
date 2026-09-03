# MentionText 标签文本

> 能力域：内容渲染 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 0.0.51

MentionText 接收一份 TagSchema 文档（二维数组：行 → 节点），逐行渲染：text 节点输出文本、 tag 节点交给 MentionTag；行间用 <br> 分隔，空白以 pre-wrap 保留。 UserMessage 在 property.extra.docSchema 含标签时用它替代 TextContent。 源码位置：src/components/mention/mention-text.vue。

**关联**：mention-tag（tag 节点的实际渲染者）、user-message（用户消息在文档含标签时改用本组件回显）、text-content（纯文本消息仍走 TextContent）

---

# MentionText 标签文本

> **能力域**：内容渲染

## 源码事实

- **源码位置**：`src/components/mention/mention-text.vue`
- **能力说明**：把 `TagSchema` 文档渲染成「文本 + 资源标签」，让用户消息里 `@` 选中的资源保持标签形态而不是退化成纯文本。
- **样式**：`width: fit-content`、`word-break: break-all`、`white-space: pre-wrap`（行间换行由 `<br>` 承担，行内连续空格与纯文本分支表现一致）。

## 数据流：消息里的标签怎么活下来

```
用户在输入框选中资源
  → onSendMessage(content, docSchema)   content 仍是纯文本，不改后端契约
  → 业务侧把 docSchema 存进 message.property.extra.docSchema
  → UserMessage 检测到文档中存在 tag 节点
  → 用 MentionText 渲染（否则回退 TextContent）
```

业务侧不保存 `docSchema` 时一切照旧：历史消息与第三方消息仍走 [TextContent](/components/rendering/text-content) 渲染纯文本。编辑消息后也需要把新的 `docSchema` 写回，否则改完这条消息标签就丢了。

```typescript
// 发送
const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
  messages.value.push({
    id, messageId: id, role: MessageRole.User, content,
    property: { extra: { docSchema } },
  });
};

// 编辑确认
const handleUserInputConfirm = async (message: Message, content: UserMessage['content'], docSchema: TagSchema) => {
  target.content = content;
  target.property = { ...target.property, extra: { ...target.property?.extra, docSchema } };
};
```

## 渲染示例

## API

### Props

| 属性名 | 类型        | 必填 | 说明                                       |
| ------ | ----------- | ---- | ------------------------------------------ |
| doc    | `TagSchema` | ✅   | 发送时随消息一起保存的编辑器文档           |

### Emits / Slots / Expose

- 无。

### 文档结构

```typescript
type TagSchema = Array<
  Array<
    | { type: 'text'; text: string }
    | {
        type: 'tag';
        data: { label: string; value: string; type: string; icon: string; description: string };
      }
  >
>;
```

外层数组是行，内层数组是行内节点。渲染时第 2 行起前置一个 `<br>`。

## 关联组件

- [MentionTag](/components/rendering/mention-tag) — 单个标签渲染与气泡
- [UserMessage](/components/message/user-message) — 使用方
- [TextContent](/components/rendering/text-content) — 无文档时的回退渲染
