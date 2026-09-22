# useCustomTab

> 导入：`import { useCustomTabConsumer, useCustomTabProvider } from '@blueking/chat-x'` ｜ since 1.0.0

useCustomTabProvider 返回 tabs、selectedTab、isCollapse 及 add/ensure/remove/selectCustomTab，并通过 provide 共享；可选 onTabChange 在切换时拉取数据、可选 collapsed 注入受控折叠态 ref。 ensureCustomTab 只挂载/合并元信息，不展开侧栏、不主动切换选中；addCustomTab 会展开并选中。 未被主动切换过时，选中态默认跟随 Tab 栏首位（order 最小），如常驻的「文件产物」。 useCustomTabConsumer 在后代注入同一套 API，常用于侧栏动态节点详情等。composable 不内建任何业务 Tab，常驻默认 Tab 由容器通过 defaultTab 注入（如「文件产物」）。 ChatContainer 侧栏集成 Provider 与 Tab UI。

**关联**：chat-container（Provider 与侧栏 Tab 主场景）

---

# useCustomTab 自定义 Tab 管理

> **分类**：composable

Provider/Consumer 模式的自定义 Tab 管理，用于 `ChatContainer` 侧边栏的 Tab 动态管理。Provider 在 `ChatContainer` 中创建，Consumer 在任意后代组件中注入使用。

## 函数签名

### useCustomTabProvider

```typescript
function useCustomTabProvider<T extends Record<string, unknown>>(options: {
  // 常驻默认 Tab：初始即挂载、作为选中态兜底、resetCustomTab 后仍保留
  defaultTab: CustomTab<T>;
  // 侧栏折叠态；由容器传入受控 ref（如 ChatContainer 的 v-model:asideCollapsed），缺省内部自持
  collapsed?: Ref<boolean>;
  onTabChange?: (tab: CustomTab<T>) => void;
}): {
  tabs: ShallowRef<CustomTab<T>[]>;
  displayTabs: ComputedRef<CustomTab<T>[]>;
  selectedTab: Ref<CustomTab<T>>;
  isCollapse: Ref<boolean>;
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
import { useCustomTabProvider, FILE_ARTIFACT_TAB_NAME } from '@blueking/chat-x';

const { tabs, selectedTab, isCollapse, addCustomTab, ensureCustomTab, removeCustomTab, selectCustomTab, resetCustomTab } =
  useCustomTabProvider({
  defaultTab: {
    name: FILE_ARTIFACT_TAB_NAME,
    label: '文件产物',
    closable: false,
    order: -1,
    loadOnSelect: false,
  },
  onTabChange: async tab => {
    const data = await fetchTabData(tab.name);
    return data;
  },
});
```

### Consumer（后代组件）

```typescript
import { useCustomTabConsumer } from '@blueking/chat-x';

const tabManager = useCustomTabConsumer();

tabManager?.addCustomTab({
  name: 'node-detail-123',
  label: '节点详情',
  data: {
    component: NodeDetailComponent,
    props: { nodeId: '123' },
  },
});
```

## 内置常量

| 常量名              | 值       | 说明                      |
| ------------------- | -------- | ------------------------- |
| `DEFAULT_TAB_ORDER` | `100`    | Tab 默认排序权重          |
| `CUSTOM_TAB_TOKEN`  | `Symbol` | provide/inject 注入 Token |

## 返回值说明

| 属性/方法名     | 类型                       | 说明                                                         |
| --------------- | -------------------------- | ------------------------------------------------------------ |
| tabs            | `ShallowRef<CustomTab[]>`  | 所有 Tab 列表（含容器注入的 defaultTab，保留隐藏项）         |
| displayTabs     | `ComputedRef<CustomTab[]>` | Tab 栏实际展示列表：过滤 `visible === false`，按 `order` 升序稳定排序 |
| selectedTab     | `Ref<CustomTab>`           | 当前选中的 Tab；未被主动切换过时跟随 Tab 栏首位              |
| isCollapse      | `Ref<boolean>`             | 侧边栏折叠状态                                               |
| addCustomTab    | `(tab: CustomTab) => void` | 添加/合并 Tab，展开侧栏并选中                                |
| ensureCustomTab | `(tab: CustomTab) => void` | 添加/合并 Tab，不展开、不主动切换选中                        |
| removeCustomTab | `(tabName: string) => void`| 移除指定 Tab                                                 |
| selectCustomTab | `(tab: CustomTab) => void` | 切换到指定 Tab                                               |
| resetCustomTab  | `() => void`               | 重置为仅保留 defaultTab                                      |

## 设计特点

- composable 不内建业务 Tab；常驻默认 Tab 由容器通过 `defaultTab` 注入（ChatContainer 注入「文件产物」）
- Tab 可携带 `icon`（组件）与 `loadOnSelect`；自持数据的 Tab 置 `loadOnSelect: false`
