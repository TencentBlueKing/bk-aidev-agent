# ShortcutBtns 快捷指令按钮组

> 能力域：输入交互 ｜ 导入：`import { ShortcutBtns } from '@blueking/chat-x'` ｜ since 1.0.0

快捷指令列表入口，内部组合多个 ShortcutBtn。 源码位置：src/components/ai-shortcut/shortcut-btns/shortcut-btns.vue。

**关联**：shortcut-btn（列表中每一项由 ShortcutBtn 渲染）、chat-input（默认嵌入输入框底部附件区）、shortcut-render（表单类快捷指令选中后的表单渲染）

---

# ShortcutBtns 快捷指令按钮组
## 源码事实

- **源码位置**：`src/components/ai-shortcut/shortcut-btns/shortcut-btns.vue`
- **能力域**：输入交互
- **能力说明**：快捷指令列表入口，内部组合多个 ShortcutBtn。

> **能力域**：输入交互

快捷指令按钮列表，内置**响应式溢出收起**：根据容器实际宽度动态计算可见数量，超出部分自动收入"更多"下拉菜单。

通常由 `ChatInput` 内部使用，一般不需要手动引入。

## 组件结构

```
div.ai-shortcut-btns（flex，gap: 4px，width: 100%，min-width: 168px，max-width: 1000px，overflow: hidden）
  │
  ├── ShortcutBtn.ai-shortcut-btns-item × N（每个快捷指令）
  │     height: 24px，padding: 0 6px，white-space: nowrap，background: #fff，border-radius: 4px
  │     溢出时追加 .ai-shortcut-btns-item-hidden（position: absolute; visibility: hidden; pointer-events: none; opacity: 0）
  │       注意：隐藏项仍在 DOM 中，仅通过 CSS 不可见，offsetWidth 仍可读
  │
  └── [hiddenShortcuts.length > 0] Tippy（trigger="manual"，append-to="body"，interactive）
        │  offset=[0,6]，z-index=SHORTCUT_MENU_Z_INDEX，theme="ai-chat-box-light light"
        ├── ShortcutBtn.ai-shortcut-btns-more（触发按钮）
        │     MoreAgentIcon（rotate(90deg)） + "更多"
        └── #content: div.ai-shortcut-menu
              ShortcutBtn（mode="menu"） × 隐藏数量
```

## 响应式溢出机制（useObserverVisibleList）

组件使用 `ResizeObserver` 监听容器宽度变化，自动计算可见按钮列表：

```
calculateVisibleMenuItems 执行逻辑：
  1. 遍历 shortcuts（按顺序）
  2. 每项计算：neededWidth = totalWidth + itemWidth + gap（非首项才加 gap）
  3. 判断：neededWidth + gap + moreButtonWidth ≤ containerWidth
       → true：加入 visibleItems，更新 totalWidth
       → false：break（后续项全部进入"更多"菜单）
  4. 触发时机：ResizeObserver 回调 / itemRefs 变化 / moreItemRef 变化
```

- `shortcuts` prop 通过 `computed(() => props.shortcuts)` 包装为 `ComputedRef` 传入 `useObserverVisibleList`，确保 items 变化时计算逻辑能访问到最新数据
- `shortcuts` prop 更新时（深度 watch），`itemRefs` 重置为同等长度的 null 数组，再等待下一帧重新计算
- 隐藏项 = `shortcuts.filter(s => !visibleItems.includes(s))`，保持原始顺序
- `ResizeObserver` 在 `onScopeDispose` 时断开，无内存泄漏

## 基础用法

```vue
<template>
  <ShortcutBtns
    :shortcuts="shortcuts"
    @select-shortcut="handleSelectShortcut"
  />
</template>

<script setup lang="ts">
  import { ShortcutBtns } from '@blueking/chat-x';
  import type { Shortcut } from '@blueking/chat-x';

  const shortcuts: Shortcut[] = [
    { id: 'ask', name: '问问小鲸' },
    { id: 'translate', name: '翻译' },
    { id: 'summarize', name: '总结' },
    { id: 'explain', name: '解释代码' },
    { id: 'code-review', name: '代码审查' },
  ];

  const handleSelectShortcut = (shortcut: Shortcut) => {
    console.log('选择了:', shortcut.name);
  };
</script>
```

## 带描述的快捷指令

`description` 字段由 `ShortcutRender` 表单弹窗使用（悬浮提示或说明文字），本组件不直接渲染：

```vue
<template>
  <ShortcutBtns
    :shortcuts="shortcuts"
    @select-shortcut="handleSelectShortcut"
  />
</template>

<script setup lang="ts">
  import { ShortcutBtns } from '@blueking/chat-x';
  import type { Shortcut } from '@blueking/chat-x';

  const shortcuts: Shortcut[] = [
    { id: 'translate', name: '翻译', description: '将文本翻译成指定语言' },
    { id: 'summarize', name: '总结', description: '自动总结长文本的核心要点' },
    { id: 'explain', name: '解释', description: '解释代码或概念' },
  ];
</script>
```

## 带表单的快捷指令

配置 `components` 后，`@select-shortcut` 事件仍正常触发，**表单弹窗逻辑需由父组件配合 `ShortcutRender` 实现**：

```vue
<template>
  <ShortcutBtns
    :shortcuts="shortcuts"
    @select-shortcut="handleSelectShortcut"
  />
  <ShortcutRender
    v-if="activeShortcut"
    :shortcut="activeShortcut"
    @submit="handleFormSubmit"
    @cancel="activeShortcut = null"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ShortcutBtns, ShortcutRender } from '@blueking/chat-x';
  import type { Shortcut } from '@blueking/chat-x';

  const activeShortcut = ref<Shortcut | null>(null);

  const shortcuts: Shortcut[] = [
    {
      id: 'translate',
      name: '翻译',
      description: '将文本翻译成指定语言',
      components: [
        {
          type: 'select',
          key: 'targetLang',
          name: '目标语言',
          props: {
            options: [
              { label: '英文', value: 'en' },
              { label: '中文', value: 'zh' },
            ],
          },
        },
        { type: 'textarea', key: 'content', name: '翻译内容', fillBack: true },
      ],
    },
    {
      id: 'code-gen',
      name: '代码生成',
      components: [
        { type: 'input', key: 'language', name: '编程语言' },
        { type: 'textarea', key: 'description', name: '功能描述', fillBack: true },
      ],
    },
  ];

  const handleSelectShortcut = (shortcut: Shortcut) => {
    if (shortcut.components?.length) {
      activeShortcut.value = shortcut; // 打开表单弹窗
    } else {
      sendMessage(shortcut); // 直接发送
    }
  };
</script>
```

## 响应式溢出（"更多"菜单）

当按钮数量超出容器可用宽度时，自动显示"更多"按钮，点击展开下拉菜单：

> 该 Demo 容器较窄时会自动触发溢出收起效果。`manyShortcuts` 共 12 项，超出容器宽度的按钮进入"更多"下拉菜单。

## API

### Props

| 属性名    | 类型         | 必填 | 说明                                                                |
| --------- | ------------ | ---- | ------------------------------------------------------------------- |
| shortcuts | `Shortcut[]` | 是   | 快捷指令列表；`v-for` 使用 `shortcut.key \|\| shortcut.id` 作为 key |

### Events

| 事件名          | 参数                   | 说明                                                                         |
| --------------- | ---------------------- | ---------------------------------------------------------------------------- |
| select-shortcut | `(shortcut: Shortcut)` | 点击任意快捷指令（含"更多"菜单中的项）时触发；从"更多"菜单选择后菜单自动关闭 |

## 类型定义

```typescript
interface Shortcut {
  id: string;
  name: string;
  key?: string; // 自定义 v-for key，优先于 id
  description?: string;
  icon?: string | VNode | ((h: typeof h) => Component | VNode);
  components?: ShortcutComponent[];
  formModel?: Record<string, unknown>;
}

type ShortcutComponent =
  | InputShortcutComponent // type: 'input'
  | TextareaShortcutComponent // type: 'textarea'
  | NumberShortcutComponent // type: 'number'
  | SelectShortcutComponent // type: 'select'
  | CheckboxGroupShortcutComponent // type: 'checkboxGroup'
  | RadioGroupShortcutComponent // type: 'radioGroup'
  | SwitcherShortcutComponent // type: 'switcher'
  | TextShortcutComponent; // type: 'text'（纯文本展示）

interface BaseShortcutComponent<T> {
  type: T;
  key: string; // 表单字段 key，对应 formModel 中的属性名
  name?: string; // 表单项 label
  fillBack?: boolean; // true 时，该字段值在提交后回填至聊天输入框
  props?: Record<string, any>; // 传给底层 bkui-vue 组件的 props
  formItemProps?: Record<string, any>; // 传给 bkui-vue Form.Item 的 props
}
```

### 表单组件类型

| type 值         | 底层组件                  | 说明                                    |
| --------------- | ------------------------- | --------------------------------------- |
| `input`         | bkui-vue Input            | 单行文本输入                            |
| `textarea`      | bkui-vue Input (textarea) | 多行文本输入                            |
| `number`        | bkui-vue Input (number)   | 数字输入                                |
| `select`        | bkui-vue Select           | 下拉选择，通过 `props.options` 配置选项 |
| `checkboxGroup` | bkui-vue Checkbox.Group   | 多选框组                                |
| `radioGroup`    | bkui-vue Radio.Group      | 单选框组                                |
| `switcher`      | bkui-vue Switcher         | 开关                                    |
| `text`          | 纯文本                    | 仅展示说明文字，不收集值                |

## 样式说明

| 类名                         | 样式                                                                       | 说明                                               |
| ---------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------- |
| `.ai-shortcut-btns`             | `width: 100%; min-width: 168px; max-width: 1000px; overflow: hidden`       | 容器，宽度撑满父元素，超出 1000px 截断             |
| `.ai-shortcut-btns-item`        | `height: 24px; padding: 0 6px; background: #fff; border-radius: 4px`       | 每个快捷指令按钮的外层包装 class                   |
| `.ai-shortcut-btns-item-hidden` | `position: absolute; visibility: hidden; pointer-events: none; opacity: 0` | 溢出按钮的隐藏态；仍在 DOM 中以便 offsetWidth 计算 |
| `.ai-shortcut-btns-more`        | `flex-shrink: 0; padding: 0 6px`                                           | "更多"按钮，`MoreAgentIcon` 旋转 90°               |
| `.ai-shortcut-menu`             | `@include menu.ai-common-menu-style`                                       | 下拉菜单容器样式                                   |

## 注意事项

1. **`key` 字段优先于 `id`**：`v-for` 使用 `shortcut.key || shortcut.id`，当多个指令 `id` 相同但代表不同实例时，可通过 `key` 字段区分
2. **溢出项不可交互**：`.ai-shortcut-btns-item-hidden` 通过 `pointer-events: none` 屏蔽点击，不会误触发事件
3. **"更多"菜单 Teleport 至 body**：Tippy 使用 `append-to="body"`，避免被父容器的 `overflow: hidden` 裁剪
4. **容器宽度限制**：`min-width: 168px` 和 `max-width: 1000px` 来自 `$chat-input-min-width` / `$chat-input-max-width` 变量，与输入框宽度保持一致
5. **表单流程在外部**：`ShortcutBtns` 只负责显示和触发事件，`components` 的表单弹窗逻辑需配合 `ShortcutRender` 实现（`ChatInput` 已内置此流程）

## 关联组件

- [ShortcutBtn](/components/input/shortcut-btn) — 列表项基础组件
- [ChatInput](/components/input/chat-input) — 默认嵌入输入框底部
- [ShortcutRender](/components/input/shortcut-render) — 表单类快捷指令的表单渲染
