# CollapsibleContent 折叠内容

> 能力域：内容渲染 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 0.0.51

CollapsibleContent 用 ResizeObserver 持续测量插槽真实高度，超过 maxHeight（默认 200px）才折叠并显示切换按钮； 折叠通过外层 max-height + overflow hidden 实现，展开态可由 v-model:expanded 受控，便于「全部展开」这类批量操作。 源码位置：src/components/chat-content/collapsible-content/collapsible-content.vue。

**关联**：user-message（用户消息正文超过 200px 时折叠）、activity-layout（活动消息的另一种折叠布局）

---

# CollapsibleContent 折叠内容

> **能力域**：内容渲染

## 源码事实

- **源码位置**：`src/components/chat-content/collapsible-content/collapsible-content.vue`
- **能力说明**：默认插槽内容高度超过 `maxHeight` 时折叠，并在下方渲染「显示更多 / 收起」；未超出时**不渲染**切换按钮。
- **切换按钮配色**：默认 `$color-text-secondary`（#979ba5），hover 转 `$color-text`（#4d4f56），箭头图标随展开态旋转。

## 实现要点

- **高度测量与折叠分离**：折叠由外层 `max-height` + `overflow: hidden` 实现，真实高度始终从内层测量容器读取，因此折叠状态不会污染测量结果。
- **持续跟踪高度**：内容可能因为图片加载、流式追加或窗口缩放而变高，用 `ResizeObserver` 持续观测而非只测一次；`ResizeObserver` 不可用时不折叠（降级为完整展示）。
- **展开态可受控**：`v-model:expanded` 允许外部驱动，便于实现「全部展开」；不绑定时组件内部自持。

## 用法

::: info 内部组件
本组件不在包入口导出，由消息组件内部使用。
:::

```vue
<template>
  <CollapsibleContent :max-height="200">
    <TextContent :content="content" />
  </CollapsibleContent>

  <!-- 外部受控展开态 -->
  <CollapsibleContent v-model:expanded="allExpanded" :max-height="120">
    <MarkdownContent :content="content" />
  </CollapsibleContent>
</template>
```

**渲染效果**（阈值 120px，可用按钮切换展开态）

## API

### Props

| 属性名    | 类型     | 默认值 | 必填 | 说明                                           |
| --------- | -------- | ------ | ---- | ---------------------------------------------- |
| maxHeight | `number` | `200`  | -    | 折叠态下内容区最大高度（px），超出才出现按钮   |
| expanded  | `boolean` | `false` | -   | 展开态，支持 `v-model:expanded`                |

### Emits

| 事件名          | 参数                | 触发时机           |
| --------------- | ------------------- | ------------------ |
| update:expanded | `(value: boolean)`  | 点击切换按钮       |

### Slots

| 插槽名  | 说明             |
| ------- | ---------------- |
| default | 被折叠的内容     |

## 使用方

[UserMessage](/components/message/user-message) 用它把用户消息正文限制在 `CONST_USER_MESSAGE_MAX_HEIGHT`（200px）以内。

## 关联组件

- [UserMessage](/components/message/user-message) — 用户消息正文折叠
- [ActivityLayout](/components/helper/activity-layout) — 活动消息的折叠布局
