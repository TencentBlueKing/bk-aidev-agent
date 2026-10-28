# 侧栏 Tab 自定义渲染

> **自 v2.1.4-beta.7 起**，`ChatBot` / `AIBlueking` 支持将 FlowAgent 等场景下侧栏自定义 Tab 的**内容区**与**标签栏**交由业务方渲染，并与主对话区「在对话中定位」联动。

## 概述

侧栏常驻默认 Tab 是「文件产物」。FlowAgent 等活动消息可通过 `addCustomTab` 打开节点详情等自定义 Tab。此前需在 `ChatContainer` 层配置 `getSideRenderComponent` 等能力；自 **v2.1.4-beta.7** 起，以下 Props 已透传到 **`ChatBot`** 与 **`AIBlueking`**，集成方无需再单独包裹 `ChatContainer`。

| 能力 | Prop | 说明 |
| --- | --- | --- |
| 自定义侧栏**内容** | `getSideRenderComponent` | 按当前 Tab 的 `data.props` 返回 VNode，覆盖 `addCustomTab` 注册的 `data.component` |
| 自定义 Tab **标签** | `getSideTabRenderComponent` | 自定义标签栏图标、文案、关闭按钮等 |
| 切换 Tab 时**拉取详情** | `onCustomTabChange` | 异步返回详情数据，写入 `data.props`（含 `loading`、`data`）；不传时 `ChatBot` 对 Flow 节点 Tab 走内置 `getFlowAgentTaskNodeInfo` |

与 [消息自定义渲染](/guide/core-features/custom-message-rendering) 的区别：

- **消息自定义渲染**：主对话区消息体内的 `custom-component` 块
- **侧栏自定义渲染**：右侧侧栏中的 Tab 内容与标签（侧栏固定右侧，已移除 `placement`）

底层机制与 `@blueking/chat-x` 的 `ChatContainer` 一致，详见 chat-x Wiki「自定义侧栏内容 / Tab 标签」。

## 内建「执行情况」Tab 已下线 {#execution-tab-visible}

chat-x **3.0.0** 起，侧栏不再内建「执行情况」Tab，也不再导出 `ExecutionSummary`。`useCustomTabProvider` 改为由容器传入 `defaultTab`。`ChatContainer` 传入的常驻默认 Tab 是「文件产物」（`order: -1`，不可关闭，`loadOnSelect: false`）。

`ChatBot` / `AIBlueking` 的类型里仍有 `executionTabVisible`，组件也会把它传给 `ChatContainer`，但 `ChatContainer` 已不声明、不读取这个 prop，**设置后没有效果**。不要再用它隐藏默认 Tab。

v2.2.x 文档站示例仍带这个 Tab，见 [示例 · 侧栏 Tab 自定义](/demos/side-render) 顶部说明。

对话流里的 FlowAgent 标题栏仍显示执行统计。失败节点的「重试 / 跳过」只出现在对话流（依赖 `retryable` / `skippable`），分享态只读。

## 内置「文件产物」Tab

「文件产物」（`name: 'file-artifact'`）是侧栏常驻默认 Tab：排在自定义 Tab 之前，不可关闭，没有产物时展示「暂无数据」。它自持数据（`loadOnSelect: false`），选中时不触发 `onCustomTabChange`，`getSideRenderComponent` 也不会改写它的内容。

自 **v2.2.2** 起，`AIBlueking` / `ChatBot` 会把 `ChatContainer.onArtifactClick` 接到 `pv_files/download_url`。AI 回复中的文件卡片打开这个 Tab，聚合当前会话里带 `outputId` 的产物与附件并预览 / 下载。集成方无需额外配置；原子组装时需自行传入 `onArtifactClick`。

浮窗展开侧栏时会先腾出右侧空间再扩宽面板，见 [AIBlueking 浮窗模式](/guide/integration-modes/aiblueking-floating)。

侧栏折叠由 `v-model:asideCollapsed` 驱动。浮窗入口在 `AIHeader`；**嵌入式 ChatBot 须业务 Header 提供开关**，否则用户无法手动展开/收起。详见 [ChatBot 页面嵌入 · 业务 Header](/guide/integration-modes/chatbot-embedded#业务-header会话名称--侧栏开关)。

## 数据流

```mermaid
sequenceDiagram
  participant Flow as FlowAgentContent
  participant Container as ChatContainer
  participant App as 业务层 onCustomTabChange
  participant UI as 侧栏内容组件

  Flow->>Container: addCustomTab({ name, label, data: { component, props, messageUid } })
  Container->>App: onTabChange → onCustomTabChange(tab)
  Note over Container: props.loading=true
  App-->>Container: 详情数据
  Note over Container: props.loading=false, props.data=结果
  Container->>UI: getSideRenderComponent(h, props) ?? data.component
```

选中自定义 Tab 后，内容区渲染优先级为：

1. `loadOnSelect === false` 的 Tab（「文件产物」）直接用 Tab 自己的 `data.component`，不调用 `getSideRenderComponent`
2. 其余 Tab：`getSideRenderComponent(h, selectedTab.data.props)` 返回的 VNode
3. 否则使用 `addCustomTab` 时传入的 `data.component`，并 `v-bind="data.props"`

## 快速开始

### 1. 定义侧栏内容组件

内容组件需根据 `loading` / `data` 展示骨架与详情，并在标题区保留 **`locateButton` 插槽**（由容器注入「在对话中定位」按钮）：

```vue
<!-- CustomTabContent.vue -->
<template>
  <div>
    <header>
      <h3>{{ loading ? '加载中…' : titleText }}</h3>
      <slot name="locateButton" />
    </header>
    <div v-if="loading" class="skeleton" />
    <dl v-else>
      <dt>node_name</dt>
      <dd>{{ nodeName }}</dd>
      <!-- 使用 props.data 渲染业务字段 -->
    </dl>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  loading?: boolean;
  nodeId?: string;
  nodeName?: string;
  taskId?: number;
  taskName?: string;
  data?: Record<string, unknown>;
}>();
</script>
```

### 2. 封装渲染函数（推荐 composable）

```typescript
// use-side-render-handlers.ts
import { h } from 'vue';
import CustomTabContent from './CustomTabContent.vue';
import type { GetSideRenderComponent, GetSideTabRenderComponent } from '@blueking/ai-blueking';

export function useSideRenderHandlers() {
  const getSideRenderComponent: GetSideRenderComponent = (createElement, props) => {
    const raw = props ?? {};
    return createElement(CustomTabContent, {
      loading: Boolean(raw.loading),
      nodeId: typeof raw.node_id === 'string' ? raw.node_id : '',
      nodeName: typeof raw.node_name === 'string' ? raw.node_name : '',
      taskId: typeof raw.task_id === 'number' ? raw.task_id : undefined,
      taskName: typeof raw.task_name === 'string' ? raw.task_name : '',
      data:
        typeof raw.data === 'object' && raw.data !== null && !Array.isArray(raw.data)
          ? (raw.data as Record<string, unknown>)
          : {},
    });
  };

  const getSideTabRenderComponent: GetSideTabRenderComponent = (createElement, tab, { removeCustomTab }) => {
    // 仅自定义 Flow 节点 Tab（name 形如 task_id|node_id|node_name）
    if (!tab.name.includes('|')) return undefined;

    const [, , nodeName = ''] = tab.name.split('|');
    return createElement('span', { style: { display: 'inline-flex', alignItems: 'center', gap: '6px' } }, [
      createElement('span', {}, nodeName || tab.label),
      createElement('button', {
        type: 'button',
        onClick: (e: Event) => {
          e.stopPropagation();
          removeCustomTab(tab.name);
        },
      }, '×'),
    ]);
  };

  return { getSideRenderComponent, getSideTabRenderComponent };
}
```

Flow 协议侧 `data.props` 常用 **snake_case**（如 `task_id`、`node_name`），在 `getSideRenderComponent` 内映射为组件 **camelCase** props 即可。

### 3. 挂到 ChatBot / AIBlueking

```vue
<template>
  <ChatBot
    url="/api/ai"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    @execution-panel-change="onExecutionPanelChange"
  />
</template>

<script setup lang="ts">
import { ChatBot } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/style.css';
import { useSideRenderHandlers } from './use-side-render-handlers';

const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();

function onExecutionPanelChange(isCollapse: boolean) {
  // 侧栏展开/收起时，若外层有 draggable 容器，需同步布局（见注意事项）
}
</script>
```

`AIBlueking` 用法相同，将上述三个 Prop 传给内层 `ChatBot` 即可。

## onCustomTabChange（可选）

类型：

```typescript
import type { OnCustomTabChange } from '@blueking/ai-blueking';

const onCustomTabChange: OnCustomTabChange = async (tab) => {
  const { task_id, node_id } = tab.data?.props ?? {};
  if (task_id == null || !node_id) return {};
  const detail = await fetchMyNodeDetail(task_id, node_id);
  return detail; // 合并进 tab.data.props.data，并置 loading=false
};
```

| 场景 | 行为 |
| --- | --- |
| **未传** `onCustomTabChange` | `ChatBot` 对含 `task_id`、`node_id` 的 Flow 节点 Tab 自动调用 `chatHelper.message.getFlowAgentTaskNodeInfo` |
| **已传** | 完全由业务方返回详情，内置拉取不再执行 |

切换 Tab 时容器会先将 `props.loading` 设为 `true`，再 `await onCustomTabChange(tab)`，最后合并 `{ loading: false, data: 返回值 }`。

## 类型导出

从 `@blueking/ai-blueking` 引入：

```typescript
import type {
  GetSideRenderComponent,
  GetSideTabRenderComponent,
  OnCustomTabChange,
} from '@blueking/ai-blueking';
```

## 与 FlowAgent / addCustomTab 的关系

- **打开 Tab**：仍由 `FlowAgentContent` 等内部调用 `useCustomTabConsumer().addCustomTab()`，业务方通常无需手动调用
- **覆盖展示**：通过 `getSideRenderComponent` / `getSideTabRenderComponent` 统一替换默认的 `BkFlowNodeDetail` 与默认标签样式
- **定位联动**：`addCustomTab` 的 `data.messageUid` 须与活动消息 `message.uid` 一致；内容组件保留 `#locateButton` 插槽

直接使用 `ChatContainer` 时，Prop 名称与行为相同，见 [ChatBot API](/api/ai-blueking/chatbot#side-render-customization)。

::: info 版本要求
本能力自 **v2.1.4-beta.7** 起在 `ChatBot` / `AIBlueking` 上提供；更低版本请直接使用 `@blueking/chat-x` 的 `ChatContainer` 同名 Props。
:::

## 注意事项

::: warning 外层 draggable 与侧栏展开
若 `ChatBot` 包在可拖拽面板内，监听 `execution-panel-change`，在侧栏因 `addCustomTab` 自动展开时同步外层布局（与 `isCollapse` 联动）。
:::

::: info 自定义 Tab 何时被清空
会话消息变化**不会**调用 `resetCustomTab`。`ChatContainer` 在卸载时才把侧栏重置为仅保留默认「文件产物」Tab。
:::

::: info props 命名与 remount
侧栏内容使用 `:key="selectedTab.name"`，切换 Tab 会重建子树。`data.props` 建议与后端 Flow 字段对齐（snake_case），在 `getSideRenderComponent` 中再映射为组件 props。
:::

## 参考示例

[示例 · 侧栏 Tab 自定义](/demos/side-render) 连接文档站内置的巡检流程 Mock，使用 `3.1.0-beta.6`。侧栏常驻「文件产物」，节点「详情」打开自定义 Tab；失败节点的重试 / 跳过在对话里的流程卡片上。页面还列出了流程智能体的 SSE 事件序列（`flow_agent_*` 的 `value` 为任务数组、状态为 BKFlow 大写）。

仓库内 Playground（`packages/ai-blueking/playground`）也提供完整示例（其中 SSE 示例将 `value` 简写为对象，实际协议为数组）：

- 页面：`views/SideRenderView.vue`（路由 `/examples/side-render`）
- 组件：`components/side-render/CustomTabContent.vue`、`FlowAgentSideRenderDemo.vue`
- 逻辑：`components/side-render/use-side-render-handlers.ts`

本地调试：在 ai-blueking 包目录执行 `pnpm dev:ai`，访问侧栏渲染示例页。

## Standalone 宿主注意 {#standalone-宿主注意}

自 **v2.1.4-beta.8** 起，非 Vue 宿主通过 [`@blueking/ai-blueking/standalone`](/guide/integration-modes/standalone-bundle) 集成时，`getSideRenderComponent` 的 `createElement` **必须**使用本入口导出的 `h`：

```typescript
import { mountChatBot, h } from '@blueking/ai-blueking/standalone';

mountChatBot('#root', {
  props: {
    url: '/api/',
    getSideRenderComponent: (createElement, props) => {
      // createElement 与 standalone 的 h 同源；也可直接写 h(...)
      return h(MySidePanel, props);
    },
  },
});
```

勿从 npm 的 `vue` 包单独 `import { h }`，否则 VNode 与组件内部 runtime 不一致会导致渲染异常。

## 相关文档

- [Standalone 非 Vue 宿主集成](/guide/integration-modes/standalone-bundle)
- [消息自定义渲染](/guide/core-features/custom-message-rendering) — 主对话区 `custom-component` 块
- [ChatBot API — 侧栏自定义渲染](/api/ai-blueking/chatbot#side-render-customization)
- [AIBlueking API](/api/ai-blueking/aiblueking)
- [类型定义 — GetSideRenderComponent 等](/api/ai-blueking/types#getsiderendercomponent)
