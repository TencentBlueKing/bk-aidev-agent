# useCustomTab

> 导入：`import { useCustomTab } from '@blueking/chat-x'` ｜ since 1.0.0

useCustomTabProvider 返回 tabs、selectedTab、isCollapse 及 add/remove/selectCustomTab，并通过 provide 共享；可选 onTabChange 在切换时拉取数据。 useCustomTabConsumer 在后代注入同一套 API，常用于侧栏动态节点详情等。EXECUTION_TAB_NAME 标识默认「执行情况」Tab。 ChatContainer 侧栏集成 Provider 与 Tab UI。

**关联**：chat-container（Provider 与侧栏 Tab 主场景）

---

# useCustomTab 自定义 Tab 管理

> **分类**：composable

Provider/Consumer 模式的自定义 Tab 管理，用于 `ChatContainer` 侧边栏的 Tab 动态管理。Provider 在 `ChatContainer` 中创建，Consumer 在任意后代组件中注入使用。

## 函数签名

### useCustomTabProvider

```typescript
function useCustomTabProvider<T extends Record<string, unknown>>(options: {
  onTabChange?: (tab: CustomTab<T>) => void;
}): {
  tabs: ShallowRef<CustomTab<T>[]>;
  selectedTab: Ref<CustomTab<T>>;
  isCollapse: ShallowRef<boolean>;
  addCustomTab: (tab: CustomTab<T>) => void;
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
      selectedTab: ShallowRef<CustomTab<T> | null>;
      addCustomTab: (tab: CustomTab<T>) => void;
      removeCustomTab: (tabName: string) => void;
      selectCustomTab: (tab: CustomTab<T>) => void;
      resetCustomTab: () => void;
    };
```

## 使用示例

### Provider（容器组件）

```typescript
import { useCustomTabProvider, EXECUTION_TAB_NAME } from '@blueking/chat-x';

const { tabs, selectedTab, isCollapse, addCustomTab, removeCustomTab, selectCustomTab, resetCustomTab } =
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

// 添加一个自定义 Tab
tabManager?.addCustomTab({
  name: 'node-detail-123',
  label: '节点详情',
  data: {
    component: NodeDetailComponent,
    props: { nodeId: '123' },
  },
});

// 移除 Tab
tabManager?.removeCustomTab('node-detail-123');
```

## 内置常量

| 常量名               | 值            | 说明                      |
| -------------------- | ------------- | ------------------------- |
| `EXECUTION_TAB_NAME` | `'execution'` | 执行情况 Tab 的固定标识   |
| `CUSTOM_TAB_TOKEN`   | `Symbol`      | provide/inject 注入 Token |

## 返回值说明

| 属性/方法名     | 类型                        | 说明                                              |
| --------------- | --------------------------- | ------------------------------------------------- |
| tabs            | `ShallowRef<CustomTab[]>`   | 所有 Tab 列表（含默认的执行情况 Tab）             |
| selectedTab     | `Ref<CustomTab>`            | 当前选中的 Tab                                    |
| isCollapse      | `ShallowRef<boolean>`       | 侧边栏折叠状态；`addCustomTab` 时自动设为 `false` |
| addCustomTab    | `(tab: CustomTab) => void`  | 添加 Tab（同名 Tab 不重复添加）                   |
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
}
```

## 设计特点

- `tabs` 使用 `shallowRef`，`addCustomTab` 通过展开新数组触发更新，避免 `UnwrapRef<T>` 类型问题
- 默认的「执行情况」Tab 始终存在且不可关闭
- `addCustomTab` 同时展开侧边栏（`isCollapse = false`）并在 `nextTick` 后自动选中新 Tab

## 关联组件

- [ChatContainer](../components/setup/chat-container) — 侧栏 Tab 与自定义面板
