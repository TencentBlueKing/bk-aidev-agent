---
name: MessageTime 消息时间
slug: message-time
kind: component
domain: feedback
description: 按「今天 / 昨天 / 今年内 / 跨年」四档格式展示消息创建时间。
aiSummary: >
  按 createdAt 展示消息时间，四档格式：今天 `12:00`、昨天 `昨天 12:00`、今年内更早 `3-12 12:00`、非今年 `2025-3-12 12:00`；
  时区取 props.timezone，未传时回退 injectGlobalConfig().timezone（由 ChatContainer 的 timezone prop 注入），都没有则用浏览器时区；
  无值或非法时间不渲染任何 DOM。通常通过 MessageTools 的 prepend / append 插槽使用。
  源码位置：src/components/message-tools/message-time/message-time.vue。
relatedComponents:
  - slug: message-tools
    relation: 通过 prepend / append 插槽嵌入工具栏
  - slug: user-message
    relation: 用户消息在工具栏左侧展示时间
  - slug: message-container
    relation: AI 消息组在工具栏右侧展示本轮回答时间
sinceVersion: '2.1.0'
---

<script lang="ts" setup>
  import MessageTimeComp from '../../../src/components/message-tools/message-time/message-time.vue'

  // 相对当前时间构造样例，保证四档格式在任何日期打开文档都成立
  const buildTime = (dayOffset, hours, minutes, yearOffset = 0) => {
    const date = new Date();
    date.setFullYear(date.getFullYear() - yearOffset);
    date.setDate(date.getDate() - dayOffset);
    date.setHours(hours, minutes, 0, 0);
    return date.toISOString();
  };

  const todayTime = buildTime(0, 12, 0);
  const yesterdayTime = buildTime(1, 12, 0);
  const thisYearTime = buildTime(30, 12, 0);
  const lastYearTime = buildTime(30, 12, 0, 1);
</script>

# MessageTime 消息时间

## 源码事实

- **源码位置**：`src/components/message-tools/message-time/message-time.vue`
- **格式化工具**：`src/components/message-tools/message-time/format-message-time.ts`
- **能力域**：工具与反馈
- **能力说明**：按「今天 / 昨天 / 今年内 / 跨年」四档格式展示消息创建时间。

> **能力域**：工具与反馈

展示单条消息（或一组 AI 回答）的创建时间。组件本身只负责格式化与渲染一段文本，**位置由使用方决定**——项目内通过 `MessageTools` 的 `prepend` / `append` 插槽嵌入工具栏。

## 格式规则

时间按与「今天」的日历日差值分四档，同一档内时分固定 `HH:mm`（24 小时制，补零），月日**不补零**：

| 档位         | 判定条件               | 输出示例        |
| ------------ | ---------------------- | --------------- |
| 今天         | 与今天同一日历日       | `12:00`         |
| 昨天         | 与今天相差 1 个日历日  | `昨天 12:00`    |
| 今年内更早   | 相差 ≥ 2 天且年份相同  | `3-12 12:00`    |
| 非今年       | 年份不同               | `2025-3-12 12:00` |

- 分档与展示取**同一时区**的日历日：既避免「昨天 23:59」与「今天 00:01」因毫秒差不足一天被判成同一天，也避免按浏览器时区分档、按配置时区显示时分导致的错位
- `昨天` 走 `t('昨天')` 国际化，英文环境输出 `Yesterday 12:00`

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 6px;">
    <MessageTimeComp :created-at="todayTime" />
    <MessageTimeComp :created-at="yesterdayTime" />
    <MessageTimeComp :created-at="thisYearTime" />
    <MessageTimeComp :created-at="lastYearTime" />
  </div>
</div>

## 基础用法

`createdAt` 接受 ISO 字符串或毫秒时间戳：

```vue
<template>
  <MessageTime :created-at="message.createdAt" />
</template>

<script setup lang="ts">
  import { MessageTime } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: 'user',
    content: '你好',
    status: 'completed',
    createdAt: '2026-08-17T04:00:00.000Z',
  };
</script>
```

> **无值不渲染**：`createdAt` 为空、为空字符串或无法解析成合法时间时，组件不渲染任何 DOM（`v-if`），使用方无需额外判空。

## 时区配置

时区按以下优先级取值，均未配置时使用**浏览器时区**：

```
props.timezone
  └─ 未传 → injectGlobalConfig()?.timezone（由 ChatContainer 的 timezone prop 注入）
       └─ 未配置 → 浏览器时区
```

```vue
<template>
  <!-- 整个会话统一按北京时间展示 -->
  <ChatContainer
    :messages="messages"
    timezone="Asia/Shanghai"
  />
</template>
```

```vue
<template>
  <!-- 单个实例覆盖全局配置 -->
  <MessageTime
    :created-at="message.createdAt"
    timezone="UTC"
  />
</template>
```

- 取值为 [IANA 时区名](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)（如 `Asia/Shanghai`、`UTC`、`America/New_York`）
- 传入非法时区名时回退到浏览器时区，不会导致渲染失败
- 同一时区的 `Intl.DateTimeFormat` 实例内部有缓存，长会话中不会为每条消息重复构造

## 在消息工具栏中的使用

`MessageTools` 提供 `prepend`（工具图标左侧）与 `append`（工具图标右侧）两个插槽，项目内的时间位置即由此决定：

| 场景         | 插槽      | 时间取值                                     |
| ------------ | --------- | -------------------------------------------- |
| 用户消息     | `prepend` | 该条消息的 `createdAt`                       |
| AI 消息组    | `append`  | 组内**最后一条**带 `createdAt` 的消息，即本轮回答完成时间 |

```vue
<template>
  <MessageTools :on-action="handleAction">
    <template #append>
      <MessageTime :created-at="createdAt" />
    </template>
  </MessageTools>
</template>

<script setup lang="ts">
  import { MessageTime, MessageTools } from '@blueking/chat-x';
</script>
```

> 组内 `reasoning` / `activity` 等子消息不单独展示时间，一个 AI 回答组只显示一次。

## API

### Props

| 属性名    | 类型               | 必填 | 默认值 | 说明                                                                 |
| --------- | ------------------ | ---- | ------ | -------------------------------------------------------------------- |
| createdAt | `number \| string` | 否   | —      | 消息创建时间，ISO 字符串或毫秒时间戳；无值或非法时不渲染             |
| timezone  | `string`           | 否   | —      | IANA 时区名；优先于全局配置，两者都未配置时按浏览器时区展示          |

### Events / Slots / Expose

无。

### 全局配置依赖

通过 `injectGlobalConfig()` 读取 `timezone`。祖先需已调用 `useGlobalConfig()`（通常由 `ChatContainer` 的 `timezone` prop 注册）；无 Provider 时按浏览器时区展示。

## 类型定义

```typescript
export type MessageTimeProps = {
  createdAt?: number | string;
  timezone?: string;
};

// 独立可用的格式化函数（组件内部使用，未从包入口导出）
declare const formatMessageTime: (createdAt?: number | string, timezone?: string) => string;
```

## 样式说明

```scss
.ai-message-time {
  flex: none;
  font-size: var(--ai-font-size, 12px);
  line-height: 16px;
  color: $color-text-secondary;
  white-space: nowrap;
}
```

- 字号跟随 `--ai-font-size`（`ChatContainer` 的 `size` 档位），颜色使用次要文本语义色
- `flex: none` + `nowrap` 保证在工具栏 flex 布局中不被压缩换行

## 注意事项

1. **时间来源**：`createdAt` 由消息层（`chat-helper`）写入 `BaseMessage`，组件不参与取数
2. **不做相对时间**：不提供「几分钟前」这类相对描述，四档格式固定
3. **空值语义**：不渲染而非渲染占位，工具栏侧的 `prepend` / `append` 包裹容器会因 `:empty` 收起，不留多余间距

## 关联组件

- [MessageTools](/components/feedback/message-tools) — 通过 `prepend` / `append` 插槽嵌入
- [UserMessage](/components/message/user-message) — 用户消息时间位置
- [MessageContainer](/components/setup/message-container) — AI 消息组时间位置
- [useGlobalConfig](/composables/use-global-config) — `timezone` 全局配置
