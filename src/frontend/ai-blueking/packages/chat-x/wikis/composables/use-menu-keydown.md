---
name: useMenuKeydown
slug: use-menu-keydown
category: composable
description: >-
  为弹出菜单提供键盘导航能力的组合式函数。在 `onMounted` 时于 **`window` 捕获阶段**注册 `keydown` 监听，在
  `onScopeDispose` 时自动移除，通过 `menuRef.offsetParent` 检测菜单可见性来决定是否响应按键。
aiSummary: >
  useMenuKeydown 接收 items、menuRef、onSelect，在 window 捕获阶段监听 keydown；菜单不可见（offsetParent 为空）或列表为空时不响应。
  维护 activeIndex，处理 ArrowUp/ArrowDown 循环与 Enter 选中，并 scrollIntoView 当前 .is-active 项。
  AiSlashMenu、AiPromptList（ChatInput 子模块）内部使用。
relatedComponents:
  - slug: chat-input
    relation: AiSlashMenu / AiPromptList 键盘导航
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { shallowRef, useTemplateRef } from 'vue';
  import { useMenuKeydown } from '../../src/composables/use-menu-keydown';

  const menuRef = useTemplateRef<HTMLElement>('menuRef');
  const items = shallowRef([
    { id: 1, name: '问问小鲸', desc: '向 AI 提问' },
    { id: 2, name: '翻译文本', desc: '将内容翻译为目标语言' },
    { id: 3, name: '代码审查', desc: '分析代码质量与安全性' },
    { id: 4, name: '摘要总结', desc: '提取文本核心要点' },
    { id: 5, name: '润色文字', desc: '优化语言表达' },
  ]);
  const selected = shallowRef<(typeof items.value)[0] | null>(null);

  const { activeIndex } = useMenuKeydown({
    items,
    menuRef,
    onSelect: item => {
      selected.value = item;
    },
  });
</script>

# useMenuKeydown 菜单键盘导航

> **分类**：composable

为弹出菜单提供键盘导航能力的组合式函数。在 `onMounted` 时于 **`window` 捕获阶段**注册 `keydown` 监听，在 `onScopeDispose` 时自动移除，通过 `menuRef.offsetParent` 检测菜单可见性来决定是否响应按键。

内部维护 `activeIndex`（高亮项索引），由调用方将其绑定到列表的 `.is-active` 样式；`handleKeydown` 完全内部管理，**无需手动绑定到模板**。

## 工作原理

```
onMounted：window.addEventListener('keydown', handleKeydown, true)  ← 捕获阶段
onScopeDispose：window.removeEventListener('keydown', handleKeydown, true)

handleKeydown(e):
  ├── !menuRef.value?.offsetParent → return（菜单不可见，忽略）
  ├── !items.value?.length        → return（列表为空，忽略）
  │
  ├── ArrowUp   → e.preventDefault/stopPropagation
  │               activeIndex = (activeIndex - 1 + length) % length  ← 循环到末尾
  │               scrollToActive()
  ├── ArrowDown → e.preventDefault/stopPropagation
  │               activeIndex = (activeIndex + 1) % length           ← 循环到开头
  │               scrollToActive()
  └── Enter / NumpadEnter → e.preventDefault/stopPropagation
                            onSelect(items[activeIndex])

scrollToActive()：nextTick → menuRef.querySelector('.is-active')?.scrollIntoView({ block: 'nearest' })
```

> **`.is-active` 依赖**：`scrollToActive` 通过 CSS 类名 `.is-active` 定位当前高亮项，调用方必须在模板中将 `activeIndex` 对应的项加上此类名。

## 渲染示例

使用 ↑ ↓ 键移动高亮，Enter 选中：

<div class="demo">
  <div style="display: flex; gap: 16px; align-items: flex-start;">
    <div
      ref="menuRef"
      style="width: 220px; border: 1px solid #dcdee5; border-radius: 6px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.08);"
    >
      <div
        v-for="(item, i) in items"
        :key="item.id"
        :class="['is-item', { 'is-active': activeIndex === i }]"
        :style="{
          padding: '8px 12px',
          cursor: 'pointer',
          fontSize: '13px',
          background: activeIndex === i ? '#e1ecff' : '#fff',
          color: activeIndex === i ? '#1768ef' : '#313238',
          borderBottom: i < items.length - 1 ? '1px solid #f0f1f5' : 'none',
          transition: 'background 0.15s',
        }"
        @click="() => { activeIndex = i; selected = item; }"
        @mouseenter="activeIndex = i"
      >
        <div style="font-weight: 500;">{{ item.name }}</div>
        <div style="font-size: 11px; color: #979ba5; margin-top: 2px;">{{ item.desc }}</div>
      </div>
    </div>
    <div style="flex: 1; font-size: 13px;">
      <div style="color: #979ba5; margin-bottom: 4px;">activeIndex = <strong style="color: #3a84ff;">{{ activeIndex }}</strong></div>
      <div v-if="selected" style="padding: 8px 12px; background: #f0fff4; border: 1px solid #a1e3ba; border-radius: 4px; color: #2caf5e;">
        ✓ 已选中：{{ selected.name }}
      </div>
      <div v-else style="padding: 8px 12px; background: #f5f7fa; border-radius: 4px; color: #979ba5;">
        用键盘 ↑↓ 导航，Enter 选中
      </div>
    </div>
  </div>
</div>

## 基础用法

```vue
<template>
  <!-- 菜单容器，ref 传给 useMenuKeydown 用于可见性检测 -->
  <div
    ref="menuRef"
    class="prompt-menu"
  >
    <div
      v-for="(item, i) in items"
      :key="item.id"
      :class="['menu-item', { 'is-active': activeIndex === i }]"
      @click="onSelect(item)"
      @mouseenter="activeIndex = i"
    >
      {{ item.name }}
    </div>
  </div>
</template>

<script setup lang="ts">
  import { shallowRef, useTemplateRef } from 'vue';
  import { useMenuKeydown } from '@blueking/chat-x';

  const menuRef = useTemplateRef<HTMLElement>('menuRef');
  const items = shallowRef([
    { id: 'ask', name: '问问小鲸' },
    { id: 'translate', name: '翻译文本' },
    { id: 'review', name: '代码审查' },
  ]);

  const onSelect = (item: (typeof items.value)[0]) => {
    console.log('选中：', item.name);
  };

  // activeIndex 由 composable 内部管理，无需手动传入
  // window keydown 监听自动注册，无需手动绑定 @keydown
  const { activeIndex } = useMenuKeydown({ items, menuRef, onSelect });
</script>

<style scoped>
  .menu-item.is-active {
    background: #e1ecff;
    color: #3a84ff;
  }
</style>
```

## 在 AiSlashInput 内部的实际用法

`useMenuKeydown` 被 `AiSlashMenu`（`@` 资源菜单）和 `AiPromptList`（`/` 提示词列表）内部使用：

```typescript
// AiPromptList 中
const promptListRef = useTemplateRef<HTMLElement>('promptListRef');
const { activeIndex } = useMenuKeydown<string>({
  items: computed(() => props.prompts), // ComputedRef 也可传入
  onSelect: props.onSelect,
  menuRef: promptListRef,
});

// AiSlashMenu 中
const menuRef = useTemplateRef<HTMLElement>('menuRef');
const { activeIndex } = useMenuKeydown<IAiSlashMenuItem>({
  items: sortedResourceList,
  onSelect: props.onSelect,
  menuRef,
});
```

## API

### 参数

```typescript
useMenuKeydown<T>(props: {
  items: ShallowRef<T[]>;                          // 菜单项列表
  menuRef: Readonly<ShallowRef<HTMLElement | null>>; // 菜单容器 DOM 引用（用于可见性检测和滚动定位）
  onSelect: (item: T) => void;                     // 选中回调
}): { activeIndex: ShallowRef<number> }
```

### 参数说明

| 参数       | 类型                              | 说明                                                        |
| ---------- | --------------------------------- | ----------------------------------------------------------- |
| `items`    | `ShallowRef<T[]>`                 | 菜单项数组；为空时所有按键均不响应                          |
| `menuRef`  | `ShallowRef<HTMLElement \| null>` | 菜单容器引用；`offsetParent === null`（不可见）时按键不响应 |
| `onSelect` | `(item: T) => void`               | Enter 确认时触发，传入当前 `activeIndex` 对应的项           |

### 返回值

| 属性名        | 类型                 | 初始值 | 说明                                                                           |
| ------------- | -------------------- | ------ | ------------------------------------------------------------------------------ |
| `activeIndex` | `ShallowRef<number>` | `0`    | 当前高亮项索引；需在模板中绑定 `.is-active` 类；鼠标 `mouseenter` 也可修改此值 |

### 按键行为（硬编码，不可自定义）

| 按键                    | 行为                                   |
| ----------------------- | -------------------------------------- |
| `ArrowUp`               | 高亮上一项（从第 0 项循环到末尾）      |
| `ArrowDown`             | 高亮下一项（从末尾循环到第 0 项）      |
| `Enter` / `NumpadEnter` | 选中当前高亮项，调用 `onSelect`        |
| `Escape`                | 无处理（不在此 composable 负责范围内） |

## 注意事项

1. **`handleKeydown` 内部自动注册**：在 `window` 捕获阶段（第三参数 `true`）绑定，优先于页面其他元素；调用方**无需**手动绑定 `@keydown`
2. **`.is-active` 类名约定**：`scrollToActive` 通过 `menuRef.querySelector('.is-active')` 定位元素，项目模板必须在 `activeIndex === i` 时添加此类
3. **`activeIndex` 不自动重置**：列表内容（`items`）变化时，`activeIndex` 保持不变。如需重置（如过滤后），需在外部 `watch` items 并手动将 `activeIndex.value = 0`
4. **可见性检测依赖 `offsetParent`**：元素通过 `display:none` 隐藏时 `offsetParent === null`，按键会被忽略；`visibility:hidden` 或 `opacity:0` 不会被忽略
5. **捕获阶段拦截**：`ArrowUp`/`ArrowDown`/`Enter` 均调用 `e.preventDefault()` 和 `e.stopPropagation()`，防止方向键滚动页面或 Enter 提交表单

## 关联组件

- [ChatInput](../components/molecular/chat-input.md) — `@` 菜单与 `/` 提示词列表
