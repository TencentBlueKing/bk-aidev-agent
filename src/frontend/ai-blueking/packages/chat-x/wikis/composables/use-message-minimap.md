---
name: useMessageMinimap
slug: use-message-minimap
category: composable
description: 消息定位器的数据逻辑：按消息组配对问答轮次，以消息容器为 root 计算可视区内的轮次，并提取问答预览文本。
aiSummary: >
  useMessageMinimap 接收消息容器与 messageGroups，返回 rounds（用户提问组 + 紧随的助手组）、visible（提问数 ≥ MESSAGE_MINIMAP_MIN_ROUNDS，即超过 4 条）与 activeIndexes（可视区内的轮次序号）。
  内部以容器为 root 创建 IntersectionObserver 观察各轮次的消息组节点，消息组变化时等 DOM 更新后重新观察，作用域销毁时断开。
  同文件导出 getQuestionText / getAnswerText（只取 assistant markdown 的行内文字，跳过代码块与图片，截断到 300 字）与 findMessageGroupElement。
  由内部组件 MessageMinimap 与 MessageContainer 使用。源码位置：src/composables/use-message-minimap.ts。
relatedComponents:
  - slug: message-container
    relation: 通过 enableMessageMinimap 渲染消息定位器，并用 findMessageGroupElement 定位
  - slug: use-message-group
    relation: 输入的 messageGroups 来自 useMessageGroup
sinceVersion: 3.1.0
---

# useMessageMinimap 消息定位器

> **分类**：composable（内部，供 `MessageMinimap` / `MessageContainer` 使用）

消息定位器（[MessageContainer · 消息定位器](/components/setup/message-container#消息定位器)）背后的数据逻辑。一般不需要直接调用，开关 `enableMessageMinimap` 即可。

## 工作原理

```
useMessageMinimap({ container, messageGroups })
  │
  ├── rounds = resolveMinimapRounds(messageGroups)
  │     用户组 + 紧随其后的助手组 = 一轮；Loading 组或没有回答时 answerGroup 为空
  │
  ├── visible = rounds.length >= MESSAGE_MINIMAP_MIN_ROUNDS（5）
  │
  └── watch(container / rounds / visible, flush: 'post')
        重建 IntersectionObserver（root = container）
        观察容器直接子节点中 data-message-group-id 属于各轮次的节点
        提问组或回答组任一可见 → 该轮序号进入 activeIndexes
```

## 基础用法

```typescript
import { useMessageMinimap } from '@blueking/chat-x';

const { rounds, visible, activeIndexes } = useMessageMinimap({
  container: () => props.container,
  messageGroups: () => props.messageGroups,
});
```

## API

### 参数

| 参数          | 类型                                                | 说明                                                                 |
| ------------- | --------------------------------------------------- | -------------------------------------------------------------------- |
| container     | `MaybeRefOrGetter<HTMLElement \| null \| undefined>` | 消息滚动容器，作为 IntersectionObserver 的 root；为空时不观察         |
| messageGroups | `MaybeRefOrGetter<MessageGroup[]>`                  | 当前渲染的消息组（`useMessageGroup` 结果），组节点需带 `data-message-group-id` |

### 返回值

| 字段          | 类型                                     | 说明                                     |
| ------------- | ---------------------------------------- | ---------------------------------------- |
| rounds        | `ComputedRef<MessageMinimapRound[]>`     | 问答轮次，顺序与消息组一致               |
| visible       | `ComputedRef<boolean>`                   | 提问超过 4 条时为 `true`                 |
| activeIndexes | `ShallowRef<number[]>`                   | 当前出现在容器可视区内的轮次序号         |

### 同文件导出

| 名称                            | 说明                                                                                                           |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `MESSAGE_MINIMAP_MIN_ROUNDS`    | 展示定位器所需的最少轮次，值为 `5`                                                                             |
| `MESSAGE_MINIMAP_PREVIEW_LIMIT` | 回答预览文本的最大长度，值为 `300`                                                                             |
| `resolveMinimapRounds(groups)`  | 从消息组列表配对问答轮次                                                                                       |
| `getQuestionText(message)`      | 提问纯文本：字符串原样使用，多模态内容只取文本片段，空白合并                                                   |
| `getAnswerText(messages)`       | 回答纯文本：只取 assistant 的 markdown 行内文字与行内代码，跳过代码块和图片；与消息渲染一致不解析 HTML，原始标签按文字保留；reasoning / tool / activity 不参与 |
| `findMessageGroupElement(container, uid)` | 在容器直接子节点中按 `data-message-group-id` 查找消息组元素                                          |

## 类型定义

```typescript
type MessageMinimapRound = {
  answerGroup?: MessageGroup;
  userGroup: MessageGroup;
};
```

## 注意事项

- 消息组增删时 `useMessageGroup` 会重新生成 `uid`，因此观察在 `flush: 'post'` 的 watch 中按最新 DOM 重建。
- 作用域销毁时自动 `disconnect`，无需手动清理。
