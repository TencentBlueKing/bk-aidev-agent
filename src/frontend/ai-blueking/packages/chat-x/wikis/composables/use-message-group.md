---
name: useMessageGroup
slug: use-message-group
category: composable
description: >-
  核心消息分组逻辑，将原始 `Message[]` 数组转换为结构化的 `MessageGroup[]`。处理 Tool 消息合并、Loading
  自动注入、执行摘要过滤和消息多选/分享等逻辑。
aiSummary: >
  useMessageGroup 接收 keyword、messages、selectedUserMessages，通过 watchEffect 产出 messageGroups（User/Assistant/Tool 合并、末尾 Loading 注入、pause 与分享勾选等）。
  executionGroups 供侧边执行摘要过滤，并暴露 isShareMode、全选与 onConfirmShare。
  ChatContainer 组装后传给 MessageContainer；ExecutionSummary 消费 executionGroups。
relatedComponents:
  - slug: chat-container
    relation: 调用并传入 MessageContainer
  - slug: message-container
    relation: 必填 messageGroups 数据源
  - slug: execution-summary
    relation: 使用 executionGroups 与定位
sinceVersion: 1.0.0
---

# useMessageGroup 消息分组

> **分类**：composable

核心消息分组逻辑，将原始 `Message[]` 数组转换为结构化的 `MessageGroup[]`。处理 Tool 消息合并、Loading 自动注入、执行摘要过滤和消息多选/分享等逻辑。

## 函数签名

```typescript
function useMessageGroup(options: {
  keyword?: ShallowRef<string>;
  messages: ComputedRef<Message[]>;
  selectedUserMessages: Ref<Message[] | undefined>;
}): {
  messageGroups: Ref<MessageGroup[]>;
  executionGroups: ComputedRef<MessageGroup[]>;
  isShareMode: ShallowRef<boolean>;
  isAllSelected: ComputedRef<boolean>;
  onToggleShareAll: (isAllSelected: boolean) => void;
  onCancelShare: () => void;
  onConfirmShare: () => Message[];
};
```

## 分组规则

`watchEffect` 遍历 `messages` 数组，按以下规则分组：

```
messages 原始数组（按顺序处理）
         │
    ┌────┴────┐────────────┐
    │         │            │
role=user  role=tool     其他 role
    │         │            │
 ① 将累积的    ② 通过          ③ 累积到
 assistant     toolCallId     assistantMessages
 消息推入       找到对应的      等待 user 消息
 list 作为      Assistant       触发分组
 一组，当前     消息，注入
 user 单独      toolMessage
 成组           后 continue

④ 遍历结束后将剩余 assistantMessages 推入 list
⑤ 末尾为 user 消息 → 追加 Loading 消息组
```

### Tool 消息处理

`role: 'tool'` 消息不会独立渲染，而是通过 `toolCallId` 注入到对应 AssistantMessage 的 `toolCall.toolMessage` 字段：

```typescript
const toolMessage = messages.find(
  m => m.role === 'assistant' && m.toolCalls?.some(t => t.id === message.toolCallId),
);
if (toolMessage) {
  const toolCall = toolMessage.toolCalls?.find(t => t.id === message.toolCallId);
  if (toolCall) {
    toolCall.toolMessage = message;
  }
  // 同步 assistant 状态（错误等）
}
```

若找不到对应 `toolCall`（例如数据不一致），**跳过注入**，避免非空断言导致的运行时异常。

### pause 字段

每个 Assistant 消息组计算 `pause` 属性：

```typescript
pause = assistantMessages.some(m => m.property?.extra?.pause) ?? false;
```

`pause` 为 `true` 时，`MessageContainer` 不渲染该组的 `MessageTools` 工具栏。

## executionGroups

`executionGroups` 从 `messageGroups` 中过滤出执行类消息，供 `ExecutionSummary` 使用。每个执行组会自动从前一组用户消息中提取 `userMessageTitle`，作为执行摘要的标题显示；若无前置用户消息则回退为当前时间戳：

```typescript
const isExecutionMessage = (m: Message): boolean => {
  return (
    // 带 toolCalls 的 assistant 消息
    (m.role === 'assistant' && !!m.toolCalls?.length) ||
    // FlowAgent 类型的 activity 消息
    (m.role === 'activity' && m.activityType === 'flow_agent')
  );
};
```

支持关键词过滤，通过 `SEARCH_TEXT_EXTRACTORS` 注册表扩展可搜索文本：

| 消息类型   | 搜索范围                                                     |
| ---------- | ------------------------------------------------------------ |
| toolCall   | `function.name`、`mcpName`、`description`、`arguments`、`id` |
| flow_agent | `task_name`、各节点 `name`                                   |

## 分享模式

`useMessageGroup` 提供完整的分享模式支持：

```typescript
const {
  isShareMode, // 是否处于分享模式
  isAllSelected, // 是否全选
  onToggleShareAll, // 切换全选
  onCancelShare, // 取消分享（清空选中 + 退出分享模式）
  onConfirmShare, // 确认分享（返回选中的消息）
} = useMessageGroup(options);
```

选中联动规则：

- 选中用户消息组 → 其后紧邻的 AI 回复组视觉联动选中
- 取消用户消息组 → 关联 AI 回复组同时取消

## 使用示例

```typescript
import { computed, ref as deepRef, shallowRef } from 'vue';
import { useMessageGroup, type Message } from '@blueking/chat-x';

const keyword = shallowRef('');
const messages = computed(() => props.messages);
const selectedUserMessages = deepRef<Message[]>([]);

const { messageGroups, executionGroups, isShareMode, isAllSelected, onToggleShareAll, onCancelShare, onConfirmShare } =
  useMessageGroup({
    keyword,
    messages,
    selectedUserMessages,
  });
```

## 返回值说明

| 属性/方法名      | 类型                          | 说明                                                                        |
| ---------------- | ----------------------------- | --------------------------------------------------------------------------- |
| messageGroups    | `Ref<MessageGroup[]>`         | 完整消息分组列表                                                            |
| executionGroups  | `ComputedRef<MessageGroup[]>` | 仅包含执行类消息的分组（工具调用 + FlowAgent），自动提取 `userMessageTitle` |
| isShareMode      | `ShallowRef<boolean>`         | 是否处于分享模式                                                            |
| isAllSelected    | `ComputedRef<boolean>`        | 所有用户消息组是否全部选中                                                  |
| onToggleShareAll | `(checked: boolean) => void`  | 切换全选                                                                    |
| onCancelShare    | `() => void`                  | 取消分享模式                                                                |
| onConfirmShare   | `() => Message[]`             | 确认分享，返回选中的消息数组                                                |

## 类型定义

```typescript
import { type MessageGroup } from '@blueking/chat-x';

interface MessageGroup {
  uuid: string;
  type: MessageRole;
  messages: Message[];
  checked: boolean;
  isHover: boolean;
  pause?: boolean;
  startTime?: number;
  userMessageTitle?: number | string;
}
```

## 关联组件

- [ChatContainer](../components/molecular/chat-container.md) — 调用 useMessageGroup 并下传分组
- [MessageContainer](../components/molecular/message-container.md) — 渲染 messageGroups
- [ExecutionSummary](../components/molecular/execution-summary.md) — 消费 executionGroups
