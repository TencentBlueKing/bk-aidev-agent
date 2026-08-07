---
name: useCustomTab
slug: use-custom-tab
category: composable
description: >-
  Provider/Consumer 模式的自定义 Tab 管理，用于 `ChatContainer` 侧边栏的 Tab 动态管理。Provider 在
  `ChatContainer` 中创建，Consumer 在任意后代组件中注入使用。
aiSummary: >
  useCustomTabProvider 返回 tabs、selectedTab、isCollapse 及 add/ensure/remove/selectCustomTab，并通过 provide 共享；可选 onTabChange 在切换时拉取数据。
  ensureCustomTab 只挂载/合并元信息，不展开侧栏、不切换选中；addCustomTab 会展开并选中。
  useCustomTabConsumer 在后代注入同一套 API，常用于侧栏动态节点详情等。EXECUTION_TAB_NAME 标识默认「执行情况」Tab。
  ChatContainer 侧栏集成 Provider 与 Tab UI。
relatedComponents:
  - slug: chat-container
    relation: Provider 与侧栏 Tab 主场景
sinceVersion: 1.0.0
---

# useCustomTab 自定义 Tab 管理

> **分类**：composable

Provider/Consumer 模式的自定义 Tab 管理，用于 `ChatContainer` 侧边栏的 Tab 动态管理。Provider 在 `ChatContainer` 中创建，Consumer 在任意后代组件中注入使用。

## 函数签名

### useCustomTabProvider

```typescript
function useCustomTabProvider<T extends Record<string, unknown>>(options: {
  // 执行情况 Tab 是否展示，缺省 true；传 getter 以保持响应式
  executionTabVisible?: () => boolean | undefined;
  onTabChange?: (tab: CustomTab<T>) => void;
}): {
  tabs: ShallowRef<CustomTab<T>[]>;
  displayTabs: ComputedRef<CustomTab<T>[]>;
  selectedTab: Ref<CustomTab<T>>;
  isCollapse: ShallowRef<boolean>;
  addCustomTab: (tab: CustomTab<T>) => void;
  ensureCustomTab: (tab: CustomTab<T>) => void;
  removeCustomTab: (tabName: string) => void;
  selectCustomTab: (tab: CustomTab<T>) => void;
  resetCustomTab: () => void;
};
```

### useCustomTabConsumer

```typescript
function useCustomTabConsumer<T extends Record<string, unknown>>():
  | undefined
  | {
      tabs: ShallowRef<CustomTab<T>[]>;
      displayTabs: ComputedRef<CustomTab<T>[]>;
      selectedTab: ShallowRef<CustomTab<T> | null>;
      addCustomTab: (tab: CustomTab<T>) => void;
      ensureCustomTab: (tab: CustomTab<T>) => void;
      removeCustomTab: (tabName: string) => void;
      selectCustomTab: (tab: CustomTab<T>) => void;
      resetCustomTab: () => void;
    };
```

## 使用示例

### Provider（容器组件）

```typescript
import { useCustomTabProvider, EXECUTION_TAB_NAME } from '@blueking/chat-x';

const { tabs, selectedTab, isCollapse, addCustomTab, ensureCustomTab, removeCustomTab, selectCustomTab, resetCustomTab } =
  useCustomTabProvider({
  onTabChange: async tab => {
    // Tab 切换时加载数据
    const data = await fetchTabData(tab.name);
    return data;
  },
});
```

### Consumer（后代组件）

```typescript
import { useCustomTabConsumer } from '@blueking/chat-x';

const tabManager = useCustomTabConsumer();

// 添加一个自定义 Tab（展开侧栏并选中）
tabManager?.addCustomTab({
  name: 'node-detail-123',
  label: '节点详情',
  data: {
    component: NodeDetailComponent,
    props: { nodeId: '123' },
  },
});

// 仅确保 Tab 存在（不展开、不切换选中）—— 如侧栏已因执行情况打开时同步挂上文件产物
tabManager?.ensureCustomTab({
  name: 'file-artifact',
  label: '文件产物',
  closable: false,
  order: -1,
});

// 移除 Tab
tabManager?.removeCustomTab('node-detail-123');
```

## 内置常量

| 常量名               | 值            | 说明                                       |
| -------------------- | ------------- | ------------------------------------------ |
| `EXECUTION_TAB_NAME` | `'execution'` | 执行情况 Tab 的固定标识                    |
| `DEFAULT_TAB_ORDER`  | `100`         | Tab 默认排序权重；执行情况固定为 `0`       |
| `CUSTOM_TAB_TOKEN`   | `Symbol`      | provide/inject 注入 Token                  |

## 返回值说明

| 属性/方法名     | 类型                        | 说明                                              |
| --------------- | --------------------------- | ------------------------------------------------- |
| tabs            | `ShallowRef<CustomTab[]>`   | 所有 Tab 列表（含默认的执行情况 Tab，保留隐藏项） |
| displayTabs     | `ComputedRef<CustomTab[]>`  | Tab 栏实际展示列表：过滤 `visible === false`，按 `order` 升序稳定排序 |
| selectedTab     | `Ref<CustomTab>`            | 当前选中的 Tab；选中项被隐藏时自动回退到首个可见 Tab |
| isCollapse      | `ShallowRef<boolean>`       | 侧边栏折叠状态；`addCustomTab` 时自动设为 `false` |
| addCustomTab    | `(tab: CustomTab) => void`  | 添加/合并 Tab，**展开侧栏并选中**目标 Tab |
| ensureCustomTab | `(tab: CustomTab) => void`  | 添加/合并 Tab，**不展开、不切换选中**；用于静默挂载（如文件产物） |
| removeCustomTab | `(tabName: string) => void` | 移除指定 Tab                                      |
| selectCustomTab | `(tab: CustomTab) => void`  | 切换到指定 Tab，触发 `onTabChange` 回调           |
| resetCustomTab  | `() => void`                  | 重置为仅保留「执行情况」Tab、折叠侧栏并选中默认 Tab；`ChatContainer` 在卸载时调用，避免残留自定义 Tab |

## 类型定义

```typescript
interface CustomTab<T = Record<string, unknown>> {
  label: string;
  name: string;
  /** 可与 `component` / `props` 并列；用于侧栏「在对话中定位」与主消息 `message.uid` 对齐 */
  data?: T & { messageUid?: string };
  /** 排序权重，升序，越小越靠前；缺省 100，执行情况默认 0 */
  order?: number;
  /** 是否在 Tab 栏展示，缺省 true；false 时仍可被程序化选中，但内容不渲染、会自动切到首个可见 Tab */
  visible?: boolean;
  /** 是否可关闭，缺省 true；执行情况强制不可关闭 */
  closable?: boolean;
}
```

## 设计特点

- `tabs` 使用 `shallowRef`，`addCustomTab` 通过展开新数组触发更新，避免 `UnwrapRef<T>` 类型问题
- 默认的「执行情况」Tab 始终存在且不可关闭，`order` 固定 `0`；可通过 `executionTabVisible` 配置显隐
- `displayTabs` 负责「过滤显隐 + 按 `order` 排序」；原始 `tabs` 仍保留全部 Tab 供程序化选中与查找
- 排序为稳定排序，`order` 相同的 Tab 保持插入先后顺序
- 选中的 Tab 被配置隐藏时，内容不再渲染，自动切换到首个可见 Tab
- `addCustomTab` 同时展开侧边栏（`isCollapse = false`）并在 `nextTick` 后自动选中目标 Tab；同名 Tab 合并更新
- `ensureCustomTab` 与 `addCustomTab` 共用合并逻辑，但不改 `isCollapse`、不切换 `selectedTab`；适合「侧栏已打开时同步挂上文件产物」等场景

## 关联组件

- [ChatContainer](../components/setup/chat-container) — 侧栏 Tab 与自定义面板
- [useArtifactPreview](./use-artifact-preview) — 文件产物 Tab：有产物时 `ensureCustomTab`，点击卡片时 `addCustomTab`
