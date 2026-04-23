---
name: useObserverVisibleList
slug: use-observer-visible-list
category: composable
description: >-
  基于 `ResizeObserver` 的容器宽度感知组合式函数：遍历列表项的实际
  `offsetWidth`，使用贪心算法计算在容器中能完整显示的项目子集，并为"更多"按钮动态预留空间。
aiSummary: >
  useObserverVisibleList 根据 containerRef、itemRefs、gap、ComputedRef items 与可选 moreItemRef，用 ResizeObserver + 贪心算法得到 visibleItems。
  依赖每项真实 offsetWidth，隐藏项需仍挂载于 DOM。返回 calculateVisibleMenuItems 供必要时手动触发。
  ShortcutBtns 内部用于快捷指令溢出收入「更多」菜单。
relatedComponents:
  - slug: shortcut-btns
    relation: 唯一内置使用方
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import ShortcutBtns from '../../src/components/ai-shortcut/shortcut-btns/shortcut-btns.vue';

  const shortcuts = Array.from({ length: 10 }, (_, i) => ({
    id: `cmd-${i + 1}`,
    name: `快捷指令 ${i + 1}`,
  }));

  const handleSelectShortcut = (shortcut) => {
    alert(`选中：${shortcut.name}`);
  };
</script>

# useObserverVisibleList 可见列表计算

> **分类**：composable

基于 `ResizeObserver` 的容器宽度感知组合式函数：遍历列表项的实际 `offsetWidth`，使用贪心算法计算在容器中能完整显示的项目子集，并为"更多"按钮动态预留空间。

> 该 composable 仅在 `ShortcutBtns` 内部使用，**通常直接使用 `ShortcutBtns` 组件即可**。

## 工作原理

```
calculateVisibleMenuItems():
  await nextTick()
  containerWidth = containerRef.value.offsetWidth

  Set<T> list = {}
  totalWidth = 0

  for i in params.items.value:   // items 是 ComputedRef<T[]>，通过 .value 访问
    itemRef = itemRefs.value[i]
    buttonWidth = itemRef.offsetWidth
    gap = list.size > 0 ? params.gap : 0          // 首项不加 gap
    neededWidth = totalWidth + buttonWidth + gap
    moreItemWidth = moreItemRef?.value?.$el?.offsetWidth ?? 0  // 动态读取

    if neededWidth + params.gap + moreItemWidth <= containerWidth:
      list.add(item)
      totalWidth = neededWidth
    else:
      break  ← 立即中止，不跳过尝试后续项

  visibleItems.value = Array.from(list)

触发时机：
  ├── onMounted：ResizeObserver.observe(containerRef) + nextTick 初始计算
  ├── watch([itemRefs, moreItemRef])：DOM 引用更新时（nextTick 后）重新计算
  └── onScopeDispose：ResizeObserver.disconnect()
```

## 渲染示例

`ShortcutBtns` 内部使用 `useObserverVisibleList`，缩放浏览器窗口观察溢出效果：

<div class="demo">
  <ShortcutBtns :shortcuts="shortcuts" @select-shortcut="handleSelectShortcut" />
  <p style="margin-top: 8px; font-size: 12px; color: #979ba5;">共 10 个快捷指令，容器宽度不足时自动收入"更多"菜单</p>
</div>

## 直接使用示例

```vue
<template>
  <div
    ref="containerRef"
    class="btn-bar"
  >
    <!-- 所有项始终渲染，溢出项用 CSS 隐藏（offsetWidth 仍可读） -->
    <template
      v-for="(item, i) in items"
      :key="item.id"
    >
      <button
        :ref="el => setItemRef(el as HTMLElement, i)"
        :class="['btn-item', { 'btn-item--hidden': !visibleItems.includes(item) }]"
        @click="handleClick(item)"
      >
        {{ item.name }}
      </button>
    </template>

    <!-- 更多按钮：仅在有隐藏项时显示 -->
    <MoreBtn
      v-show="hiddenItems.length > 0"
      ref="moreBtnRef"
      @click="showMoreMenu"
    />
  </div>
</template>

<script setup lang="ts">
  import { computed, shallowRef, useTemplateRef } from 'vue';
  import { useObserverVisibleList } from '@blueking/chat-x';

  interface Item {
    id: string;
    name: string;
  }

  const containerRef = useTemplateRef<HTMLElement>('containerRef');
  const moreBtnRef = useTemplateRef('moreBtnRef');

  // 必须是 ShallowRef，由调用方维护（DOM 更新后写入）
  const itemRefs = shallowRef<(HTMLElement | null)[]>([]);

  const items = shallowRef<Item[]>([
    { id: '1', name: '按钮 1' },
    { id: '2', name: '按钮 2' },
    { id: '3', name: '按钮 3' },
    { id: '4', name: '按钮 4' },
    { id: '5', name: '按钮 5' },
  ]);

  const { visibleItems, calculateVisibleMenuItems } = useObserverVisibleList<Item>(containerRef, itemRefs, {
    gap: 4, // 按钮间距（必填）
    items: computed(() => items.value), // 需传入 ComputedRef<T[]>，内部通过 .value 访问
    moreItemRef: moreBtnRef, // 可选，动态读取"更多"按钮宽度
  });

  const hiddenItems = computed(() => items.value.filter(i => !visibleItems.value.includes(i)));

  const setItemRef = (el: HTMLElement | null, index: number) => {
    itemRefs.value[index] = el;
  };

  // items 变化时：重置 itemRefs（触发 watch → 重新计算）
  watch(items, () => {
    itemRefs.value = new Array(items.value.length).fill(null);
  });
</script>

<style scoped>
  .btn-bar {
    display: flex;
    gap: 4px;
    overflow: hidden;
  }

  /* 隐藏项必须保持在 DOM 中（offsetWidth 才可读），用定位脱离文档流 */
  .btn-item--hidden {
    position: absolute;
    visibility: hidden;
    pointer-events: none;
    opacity: 0;
  }
</style>
```

## API

```typescript
function useObserverVisibleList<T>(
  containerRef: TemplateRef<HTMLElement>,
  itemRefs: ShallowRef<(HTMLElement | null)[]>,
  params: {
    gap: number; // 必填，按钮间距（px）
    items: ComputedRef<T[]>; // 必填，响应式项目数组（ComputedRef）
    moreItemRef?: TemplateRef<InstanceType<typeof ShortcutBtn>>; // 可选，"更多"按钮引用
  },
): {
  visibleItems: ShallowRef<T[]>;
  calculateVisibleMenuItems: () => Promise<void>;
};
```

### 参数说明

| 参数                 | 类型                                  | 必填 | 说明                                                                                                        |
| -------------------- | ------------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------- |
| `containerRef`       | `TemplateRef<HTMLElement>`            | 是   | 容器 DOM 引用；`ResizeObserver` 监听此元素宽度变化                                                          |
| `itemRefs`           | `ShallowRef<(HTMLElement \| null)[]>` | 是   | 各项 DOM 引用数组；`watch` 监听其变化触发重新计算                                                           |
| `params.gap`         | `number`                              | 是   | 相邻按钮间距（px）；首项不加 gap                                                                            |
| `params.items`       | `ComputedRef<T[]>`                    | 是   | **响应式**项目数组，需传入 `ComputedRef`（如 `computed(() => list.value)`）；内部通过 `.value` 访问最新数据 |
| `params.moreItemRef` | `TemplateRef<ShortcutBtn>`            | 否   | "更多"按钮引用；每次计算从 `$el.offsetWidth` 动态读取宽度；缺省时按 0 计算                                  |

### 返回值

| 属性名                      | 类型                  | 说明                                                               |
| --------------------------- | --------------------- | ------------------------------------------------------------------ |
| `visibleItems`              | `ShallowRef<T[]>`     | 当前能完整放入容器的项目子集（引用与 `params.items` 中的对象一致） |
| `calculateVisibleMenuItems` | `() => Promise<void>` | 手动触发计算（内部有 `await nextTick()`）；一般无需调用            |

## 注意事项

1. **`items` 必须为 `ComputedRef`**：`params.items` 现在接受 `ComputedRef<T[]>` 类型，内部通过 `.value` 读取最新数据。建议使用 `computed(() => props.shortcuts)` 包装后传入，确保 items 变化时计算逻辑能访问到最新数据。注意 `itemRefs` 的重置仍需在外部维护（`itemRefs.value = new Array(items.value.length).fill(null)`），以触发 `watch([itemRefs, moreItemRef])` 重新计算
2. **隐藏项必须留在 DOM**：算法依赖 `itemRef.offsetWidth` 读取每项实际宽度；使用 `position: absolute; visibility: hidden` 隐藏而非 `display: none`
3. **算法贪心且单调**：遇到第一个放不下的项就立即 `break`，不跳过继续尝试后续较短的项
4. **`moreItemRef` 宽度动态读取**：每次计算循环中实时读取 `$el.offsetWidth`，宽度可以随内容变化（如显示隐藏数量文字时）
5. **`ResizeObserver` 仅在 `onMounted` 时绑定一次**：若 `containerRef.value` 在挂载时为 `null`，则不会监听容器宽度变化
6. **`moreItemRef` 类型限定为 `ShortcutBtn`**：强依赖内部 `$el` expose，若用于其他组件需确保 expose 了 `$el`

## 关联组件

- [ShortcutBtns](../components/atomic/shortcut-btns.md) — 快捷指令条与「更多」
