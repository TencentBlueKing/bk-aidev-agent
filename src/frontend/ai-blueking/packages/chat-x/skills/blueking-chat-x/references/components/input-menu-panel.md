# InputMenuPanel 输入框菜单

> 能力域：输入交互 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 0.0.51

InputMenuPanel 渲染输入框菜单：分组标题 + InputMenuOption 条目 + 「更多 +N」折叠开关， 内置键盘上下导航与 Esc 关闭；分组数据由 useInputMenu 纯数据逻辑算出（按触发方式筛类型 → 关键字过滤 → 分组 → 折叠 → 扁平化）。 源码位置：src/components/chat-input/input-menu/（input-menu-panel.vue、input-menu-option.vue、use-input-menu.ts、constants.ts）。

**关联**：chat-input（上层持有触发态与数据源并渲染本面板）、ai-slash-input（触发方式与过滤关键字由编辑器 menuChange 抛出）、add-menu-btn（+ 号唤起 plus 触发的聚合菜单）、resource-icon（条目左侧图标由 ResourceIcon 渲染）

---

# InputMenuPanel 输入框菜单

> **能力域**：输入交互

## 源码事实

- **面板**：`src/components/chat-input/input-menu/input-menu-panel.vue`
- **条目**：`src/components/chat-input/input-menu/input-menu-option.vue`
- **数据逻辑**：`src/components/chat-input/input-menu/use-input-menu.ts`
- **分组定义**：`src/components/chat-input/input-menu/constants.ts`
- **能力说明**：`@` `/` `\` 与左下角 + 号共用同一个面板与同一份 `menuSources`，差异只体现在「展示哪些分组」。

## 布局与交互

- 面板由 [ChatInput](/components/input/chat-input) 绝对定位在输入框**正上方 8px**、与输入框等宽，**不跟随光标**；最大高度 400px，超出滚动。
- 键盘导航由 [useMenuKeydown](/composables/use-menu-keydown) 提供：`↑` / `↓` 移动高亮，`Enter` 选中，高亮项滚动进可视区；结果集变化后高亮回到首项。
- `Esc` 在**捕获阶段**监听并 emit `close`，避免被编辑器先行消费。
- 面板滚动时关闭条目描述气泡，防止气泡与列表错位。
- 条目 `disabled` 时不可选中，也不进入键盘导航序列。
- 条目名称过长时用 `v-overflow-tips` 展示完整名称；`description` 非空时 hover 弹出「类型：名称 + 描述」气泡（与 [MentionTag](/components/rendering/mention-tag) 同一套气泡）。

## 分组与触发方式

| 触发方式 | 分组顺序                                                  |
| -------- | --------------------------------------------------------- |
| `/`      | Skill、MCP、工具                                          |
| `@`      | 知识库、会话产物                                          |
| `\`      | Prompt                                                    |
| `plus`   | 添加、Skill、MCP、工具、知识库、会话产物、Prompt          |

分组静态定义（`MENU_GROUP_DEFS`）：

| `key`           | 标题     | 覆盖 `type`            | `keepWhenEmpty` |
| --------------- | -------- | ---------------------- | --------------- |
| `add`           | 添加     | `file`                 | `false`         |
| `skill`         | Skill    | `skill`                | `false`         |
| `mcp`           | MCP      | `mcp`                  | `false`         |
| `tool`          | 工具     | `tool`                 | `false`         |
| `knowledgebase` | 知识库   | `knowledgebase`、`doc` | `false`         |
| `artifact`      | 会话产物 | `artifact`             | `true`          |
| `prompt`        | Prompt   | `prompt`               | `false`         |

- `keepWhenEmpty` 为 `true` 的分组在无数据时仍渲染并展示「暂无数据」，且**不计入**「面板是否有内容」的判断——只有这类分组时面板不会弹出。
- `DIVIDED_GROUP_KEYS` 决定哪些分组下方画分隔线，目前为 `['add']`。
- `getMenuTypeLabel(type)` 由分组定义反查生成，菜单分组标题与标签气泡标题共用一份映射。

## 渲染示例

## useInputMenu

面板只负责渲染，分组结果由 `useInputMenu` 计算，可脱离 UI 单独单测。流程为：**按触发方式筛类型 → 按关键字过滤 → 分组 → 应用折叠阈值 → 扁平化供键盘导航**。

::: info 内部模块
面板、条目与 `useInputMenu` 都不在包入口导出，仅供 [ChatInput](/components/input/chat-input) 内部使用；`IInputMenuItem`、`MenuTrigger` 等类型从包入口导出。
:::

```typescript
import { computed, shallowRef } from 'vue';

const trigger = shallowRef<MenuTrigger | null>(null);
const keyword = shallowRef('');

const { groups, flatItems, hasContent, toggleGroup } = useInputMenu({
  sources: computed(() => availableSources.value),
  keyword,
  trigger,
  groupItemLimit: computed(() => props.menuGroupItemLimit),
});
```

### 参数

| 参数             | 类型                                          | 说明                                     |
| ---------------- | --------------------------------------------- | ---------------------------------------- |
| `sources`        | `Ref<IInputMenuItem[]>`                       | 全部可选项                               |
| `keyword`        | `Ref<string>`                                 | 过滤关键字（触发符之后用户输入的文本）   |
| `trigger`        | `Ref<MenuTrigger \| null>`                    | 当前触发方式，`null` 表示菜单未激活      |
| `groupItemLimit` | `Ref<number>`                                 | 每个分组默认展示条数上限（内部下限为 1） |

### 返回值

| 字段          | 类型                            | 说明                                             |
| ------------- | ------------------------------- | ------------------------------------------------ |
| `groups`      | `ComputedRef<IInputMenuGroup[]>` | 渲染用分组（已应用过滤与折叠）                   |
| `flatItems`   | `ComputedRef<IInputMenuItem[]>` | 当前可见且可选中的条目，顺序与面板一致           |
| `hasContent`  | `ComputedRef<boolean>`          | 面板是否有内容，供上层决定显隐                   |
| `toggleGroup` | `(key: MenuGroupKey) => void`   | 切换某个分组的展开 / 折叠                        |

> 关键字或触发方式变化时，内部会清空手动展开状态——结果集已完全不同，沿用旧状态会造成误导。

## API

### InputMenuPanel Props

| 属性名    | 类型                 | 必填 | 说明                                   |
| --------- | -------------------- | ---- | -------------------------------------- |
| groups    | `IInputMenuGroup[]`  | ✅   | 分组数据                               |
| flatItems | `IInputMenuItem[]`   | ✅   | 可选中条目的扁平序列，供键盘导航       |

### InputMenuPanel Emits

| 事件名      | 参数                       | 触发时机                     |
| ----------- | -------------------------- | ---------------------------- |
| select      | `(item: IInputMenuItem)`   | 点击条目或按 Enter 选中      |
| toggleGroup | `(key: string)`            | 点击「更多 +N / 收起」       |
| close       | `()`                       | 按下 Esc                     |

### InputMenuOption Props / Emits

| 名称     | 类型                     | 说明                       |
| -------- | ------------------------ | -------------------------- |
| `item`   | `IInputMenuItem`         | 条目数据                   |
| `active` | `boolean`                | 键盘导航选中态             |
| `select` | `(item: IInputMenuItem)` | 条目未禁用时点击触发       |

### 类型定义

```typescript
/** 面板渲染用的分组（已应用关键字过滤与折叠阈值） */
interface IInputMenuGroup {
  key: string;
  /** 分组标题的中文文案 key，渲染时经 t() 转换 */
  name: string;
  /** 当前可见条目 */
  items: IInputMenuItem[];
  /** 被折叠隐藏的条数，为 0 表示无需折叠 */
  restCount: number;
  /** 是否已展开全部条目 */
  expanded: boolean;
  /** 分组下方是否需要分隔线 */
  divided: boolean;
}

type MenuGroupKey = 'add' | 'skill' | 'mcp' | 'tool' | 'knowledgebase' | 'artifact' | 'prompt';

/** 字符触发符，plus 由按钮唤起不在其中 */
const CHAR_TRIGGERS = ['@', '/', '\\'] as const;

/** 分组默认最多展示的条数 */
const DEFAULT_GROUP_ITEM_LIMIT = 4;
```

`IInputMenuItem` 与 `MenuTrigger` 见 [ChatInput 类型定义](/components/input/chat-input#类型定义)。

## 关联组件

- [ChatInput](/components/input/chat-input) — 菜单数据源、触发态与选中后的动作分发
- [AiSlashInput](/components/input/ai-slash-input) — 触发方式与关键字的来源
- [AddMenuBtn](/components/input/add-menu-btn) — `plus` 触发入口
- [ResourceIcon](/components/helper/resource-icon) — 条目图标
- [useMenuKeydown](/composables/use-menu-keydown) — 键盘导航
