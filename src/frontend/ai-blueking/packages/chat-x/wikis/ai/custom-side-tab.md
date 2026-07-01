---
name: 自定义侧栏 Tab 标签
slug: custom-side-tab
category: ai
description: >
  通过 ChatContainer 的 getSideTabRenderComponent 自定义侧栏 Tab 栏标签的渲染，
  覆盖默认的图标 + 文案 + 关闭按钮组合。
aiSummary: >
  ChatContainer 在 ResizeLayout 侧栏 TabPanel 的 label 插槽中调用 getSideTabRenderComponent(h, tab, { removeCustomTab })。
  返回 VNode 时完全接管该 Tab 标签 UI；返回 undefined 时走内置 ExecutionIcon/NodeTabIcon + 文案 + CloseIcon。
  与 addCustomTab 的 name/label 配合；关闭逻辑可复用 events.removeCustomTab 或依赖默认关闭按钮。
relatedComponents:
  - slug: chat-container
    relation: getSideTabRenderComponent 定义与 Tab 栏渲染入口
  - slug: flow-agent-content
    relation: FlowAgent 通过 addCustomTab 追加节点/任务 Tab
sinceVersion: '2.1.0'
---

# 自定义侧栏 Tab 标签

## 概述

`ChatContainer` 右侧（或 `placement` 指定侧）侧栏顶部为 **Tab 标签栏**：默认包含固定的「执行情况」Tab，以及由 `addCustomTab` 动态追加的自定义 Tab。

应用层可通过 **`getSideTabRenderComponent`** 按 Tab 粒度自定义**标签区域**的展示（图标、文案、关闭按钮、徽章等），而不改动 Tab 的 `name` / `label` 数据模型与 `addCustomTab` 流程。

| 能力 | Prop | 作用范围 |
| ---- | ---- | -------- |
| 自定义 **Tab 标签** | `getSideTabRenderComponent` | 仅 Tab 栏每一枚标签的 `label` 插槽 |
| 自定义 **侧栏内容** | `getSideRenderComponent` | 选中 Tab 后下方内容区（见 [自定义侧栏内容](./custom-side-content.md)） |

Tab 的增删、选中、数据加载仍由 [useCustomTab](../composables/use-custom-tab.md) 与 `onCustomTabChange` 负责，本文只描述**标签 UI** 扩展。

## 渲染位置

侧栏结构（简化）：

```
ResizeLayout #aside
├── Tab（:active="selectedTab.name"）
│   └── TabPanel × N
│        └── label: getSideTabRenderComponent(h, tab, { removeCustomTab }) ?? 默认标签
├── ExecutionSummary（选中「执行情况」时）
└── component :is（选中自定义 Tab 时的内容区）
```

源码入口（`chat-container.vue`）：`TabPanel` 的 `label` 为函数，内部优先调用 `getSideTabRenderComponent`，未返回有效 VNode 时使用默认实现。

## API

### getSideTabRenderComponent

```typescript
type GetSideTabRenderComponent = (
  createElement: typeof h,
  tab: CustomTab<Record<string, unknown>>,
  events: { removeCustomTab: (tabName: string) => void },
) => VNode | undefined;
```

| 参数 | 说明 |
| ---- | ---- |
| `createElement` | Vue 的 `h`，用于创建 VNode |
| `tab` | 当前 Tab 项，含 `name`、`label`、可选 `icon`、`data` |
| `events.removeCustomTab` | 与容器内部一致的移除方法，传入 `tab.name` 即可关闭该 Tab |

| 返回值 | 行为 |
| ------ | ---- |
| `VNode` | **完全替换**该 Tab 的标签 UI（不再自动渲染默认图标、文案、关闭按钮） |
| `undefined` | 使用内置标签：执行情况 Tab 用 `ExecutionIcon`，其余用 `NodeTabIcon` + `tab.label`（溢出 tooltip）+ `CloseIcon`（非执行情况 Tab 可点关闭） |

### 与 CustomTab 的关系

`addCustomTab` / `useCustomTabConsumer` 写入的 `CustomTab` 决定 Tab **是否存在**以及 **name / label**；`getSideTabRenderComponent` 只决定**已存在 Tab 在标签栏长什么样**。

```typescript
import type { CustomTab } from '@blueking/chat-x';

// 典型：FlowAgent 打开的节点 Tab
// name: `${task_id}|${node.id}|${node.name}`
// label: node.name
```

内置常量 `EXECUTION_TAB_NAME === 'execution'` 对应默认「执行情况」Tab，一般不需要自定义其标签；若返回自定义 VNode，需自行处理「不可关闭」等产品规则。

## 默认标签行为

当 `getSideTabRenderComponent` 返回 `undefined` 时，每个 `TabPanel` 的 `label` 为：

1. **图标**：`tab.name === EXECUTION_TAB_NAME` → `ExecutionIcon`，否则 `NodeTabIcon`
2. **文案**：`tab.label`，带 `vOverflowTips` 防止过长截断
3. **关闭**：仅非 `execution` Tab 渲染 `CloseIcon`，`onClick` 调用 `removeCustomTab(tab.name)`

选中 Tab 时，对应标签会 `scrollIntoView({ behavior: 'smooth' })` 滚入可视区域。

## 使用示例

### 按 Tab name 定制标签

```vue
<template>
  <ChatContainer
    :get-side-tab-render-component="getSideTabRenderComponent"
    ...
  />
</template>

<script setup lang="ts">
  import { h } from 'vue';
  import { ChatContainer, type CustomTab } from '@blueking/chat-x';

  const getSideTabRenderComponent = (
    createElement: typeof h,
    tab: CustomTab<Record<string, unknown>>,
    { removeCustomTab },
  ) => {
    // 示例：某一业务 Tab 使用纯文本标签
    if (tab.name === '634859') {
      return createElement('span', { class: 'my-tab-label' }, tab.label);
    }
    // 其余 Tab 走默认图标 + 文案 + 关闭
    return undefined;
  };
</script>
```

### 自定义标签并自行处理关闭

```typescript
const getSideTabRenderComponent = (createElement, tab, { removeCustomTab }) => {
  if (!tab.name.startsWith('custom-')) {
    return undefined;
  }

  return createElement('span', { class: 'custom-tab-label' }, [
    createElement('span', {}, tab.label),
    createElement('button', {
      type: 'button',
      onClick: (e: Event) => {
        e.stopPropagation();
        removeCustomTab(tab.name);
      },
    }, '×'),
  ]);
};
```

> 自定义标签时若未提供关闭入口，用户只能依赖其它逻辑调用 `removeCustomTab`，或等待 `executionGroups` 清空后容器 `resetCustomTab`。

## Playground 参考

`playground/chat-bot-new.vue` 中注册了 `getSideTabRenderComponent`：当 `tab.name === '634859'` 时返回简单文本节点，用于验证「覆盖默认标签」路径；其余 Tab 返回 `undefined` 走默认 UI。

```typescript
const getSideTabRenderComponent = (createElement: typeof h, tab: CustomTab<Record<string, unknown>>) => {
  if (tab.name === '634859') {
    return createElement('div', {}, 'dddd');
  }
  return undefined;
};
```

本地调试：在 FlowAgent 消息中触发会生成对应 `name` 的 Tab，或经 `chatContainerRef.addCustomTab({ name: '634859', label: '...' })` 手动添加。

## 与内容区、数据加载的配合

| 步骤 | 说明 |
| ---- | ---- |
| 1 | 消息内组件（如 `FlowAgentContent`）`addCustomTab({ name, label, data })` |
| 2 | 可选：`getSideTabRenderComponent` 美化该 Tab 的标签 |
| 3 | 选中 Tab 时触发 `onCustomTabChange`，合并进 `data.props`（见 [custom-side-content](./custom-side-content.md)） |
| 4 | 可选：`getSideRenderComponent` 覆盖侧栏内容组件 |

标签与内容相互独立：可只定制标签、只定制内容，或两者同时定制。

## 注意事项

- **不要**在 `getSideTabRenderComponent` 内修改 `tabs` 列表；增删 Tab 请用 `addCustomTab` / `removeCustomTab`。
- 返回的 VNode 应处理好 **点击关闭 vs 切换 Tab** 的事件冒泡（关闭按钮建议 `stopPropagation`）。
- `tab.label` 为空时默认文案区域仍渲染，业务侧应在 `addCustomTab` 时保证可读 `label`。
- 分享模式 `RenderMode.Share` 下侧栏不展示，该 Prop 不会生效。

## 相关文档

- [自定义侧栏内容](./custom-side-content.md) — `getSideRenderComponent`、`onCustomTabChange`、`locateButton`
- [useCustomTab](../composables/use-custom-tab.md) — `addCustomTab` / `removeCustomTab` / Provider-Consumer
- [ChatContainer](../components/setup/chat-container.md) — 侧栏整体行为与 expose API
- [自定义消息类型](./custom-message.md) — FlowAgent 内 `addCustomTab` 场景
