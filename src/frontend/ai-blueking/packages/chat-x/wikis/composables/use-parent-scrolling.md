---
name: useParentScrolling
slug: use-parent-scrolling
category: composable
description: >-
  向上递归查找**最近可滚动祖先**，监听其 `scroll` / `scrollend` 事件，提供 `isScrolling`
  状态。常用于滚动时自动关闭浮层、禁用交互等场景。
aiSummary: >
  useParentScrolling(domRef) 在挂载后通过 getScrollParent 找到最近可滚动祖先，监听 scroll 与 scrollend，返回 isScrolling 与 scrollParent。
  scroll 时将 isScrolling 置 true，300ms 无滚动或 scrollend 时置 false，适合滚动时隐藏浮层等交互。getScrollParent 可单独导出使用。
  当前源码无组件内引用，供业务或后续浮层组件按需集成。
relatedComponents: []
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { shallowRef, useTemplateRef } from 'vue';
  import { useParentScrolling, getScrollParent } from '../../src/composables/use-parent-scrolling';

  const targetRef = useTemplateRef<HTMLElement>('targetRef');
  const { isScrolling, scrollParent } = useParentScrolling(targetRef);

  const scrollParentTag = shallowRef<string>('（未挂载）');
  const updateTag = () => {
    const el = scrollParent.value;
    if (!el) { scrollParentTag.value = 'null'; return; }
    const id = el.id ? `#${el.id}` : '';
    const cls = el.className ? `.${el.className.split(' ')[0]}` : '';
    scrollParentTag.value = `<${el.tagName.toLowerCase()}${id}${cls}>`;
  };

  // onMounted 后 scrollParent 才有值
  import { onMounted, watch } from 'vue';
  onMounted(() => {
    watch(scrollParent, updateTag, { immediate: true });
  });
</script>

# useParentScrolling 父容器滚动监听

> **分类**：composable

向上递归查找**最近可滚动祖先**，监听其 `scroll` / `scrollend` 事件，提供 `isScrolling` 状态。常用于滚动时自动关闭浮层、禁用交互等场景。

同时导出辅助函数 `getScrollParent`，可单独使用。

## 工作原理

```
getScrollParent(node):
  ├── !node → null
  ├── !(node instanceof HTMLElement) → getScrollParent(parentElement) 或 document.body
  ├── scrollHeight > clientHeight
  │     && overflowY in ['scroll', 'auto', 'overlay'] → return node（找到）
  └── else → getScrollParent(parentElement) 或 document.body（fallback）

useParentScrolling(domRef):
  onMounted:
    scrollParent = getScrollParent(toValue(domRef))
    removeEventListener（防御性清理）
    addEventListener('scroll', handleScroll)    ← 非 passive
    addEventListener('scrollend', handleScrollEnd)

  handleScroll:
    isScrolling = true
    clearTimeout(timer)
    timer = setTimeout(() => isScrolling = false, 300)  ← 300ms 无滚动后重置

  handleScrollEnd:
    isScrolling = false  ← 原生 scrollend 事件立即重置（浏览器兼容性见下）

  onScopeDispose:
    removeEventListener（自动清理）
```

## 渲染示例

<div class="demo">
  <div style="display: flex; gap: 12px; align-items: flex-start;">
    <!-- 可滚动父容器 -->
    <div
      id="scroll-demo-box"
      style="width: 220px; height: 120px; overflow-y: auto; border: 1px solid #dcdee5; border-radius: 4px; padding: 8px;"
    >
      <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">↕ 在此区域内滚动</p>
      <!-- 监听目标元素 -->
      <div ref="targetRef" style="height: 1px;" />
      <div v-for="i in 15" :key="i" style="padding: 4px 0; font-size: 13px; border-bottom: 1px solid #f0f1f5;">
        内容行 {{ i }}
      </div>
    </div>
    <!-- 状态面板 -->
    <div style="font-size: 13px; font-family: monospace; line-height: 2;">
      <div>
        isScrolling：
        <strong :style="{ color: isScrolling ? '#3a84ff' : '#979ba5' }">
          {{ isScrolling }}
        </strong>
      </div>
      <div style="font-size: 12px; color: #63656e; word-break: break-all;">
        scrollParent：{{ scrollParentTag }}
      </div>
    </div>
  </div>
  <p style="margin-top: 8px; font-size: 12px; color: #979ba5;">滚动左侧容器，isScrolling 变为 true；停止 300ms 后恢复 false</p>
</div>

## 基础用法

```vue
<template>
  <!-- 浮层：滚动时隐藏 -->
  <div
    v-show="!isScrolling"
    ref="floatRef"
    class="float-panel"
  >
    浮动面板
  </div>
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { useParentScrolling } from '@blueking/chat-x';

  const floatRef = useTemplateRef<HTMLElement>('floatRef');

  // 自动查找 floatRef 最近的可滚动祖先并监听
  const { isScrolling, scrollParent } = useParentScrolling(floatRef);
</script>
```

## 传入普通元素（非 ref）

参数类型为 `MaybeRef`，支持直接传入 `HTMLElement`：

```typescript
import { getScrollParent, useParentScrolling } from '@blueking/chat-x';

// 独立使用 getScrollParent 查找可滚动父元素
const scrollable = getScrollParent(document.querySelector('.my-element'));
console.log(scrollable); // HTMLElement 或 null

// 直接传入元素（非 ref）
const el = document.getElementById('my-el');
const { isScrolling } = useParentScrolling(el);
```

## API

### useParentScrolling

```typescript
function useParentScrolling(domRef: MaybeRef<HTMLElement | null>): {
  isScrolling: ShallowRef<boolean>; // 初始值 false
  scrollParent: ShallowRef<HTMLElement | null>; // 最近可滚动祖先，onMounted 后填充
};
```

| 返回值         | 类型                              | 初始值  | 说明                                                                            |
| -------------- | --------------------------------- | ------- | ------------------------------------------------------------------------------- |
| `isScrolling`  | `ShallowRef<boolean>`             | `false` | 父容器是否正在滚动；`scroll` 触发置 `true`，300ms 后或 `scrollend` 后置 `false` |
| `scrollParent` | `ShallowRef<HTMLElement \| null>` | `null`  | `onMounted` 后由 `getScrollParent` 填充的最近可滚动祖先                         |

### getScrollParent（辅助函数）

```typescript
function getScrollParent(node: HTMLElement | null | ParentNode): HTMLElement | null;
```

递归向上查找**第一个满足条件**的祖先元素：

- 条件：`scrollHeight > clientHeight` 且 `overflowY` 为 `'scroll' | 'auto' | 'overlay'`
- 无满足条件的祖先时返回 `document.body`
- `node` 为 `null` 时返回 `null`

## 滚动状态重置时序

| 事件              | `isScrolling` 变化 | 说明                           |
| ----------------- | ------------------ | ------------------------------ |
| `scroll` 触发     | `false → true`     | 立即置 true，重置 300ms 计时器 |
| 持续滚动          | 保持 `true`        | 每次 scroll 事件重置计时器     |
| 停止滚动 300ms 后 | `true → false`     | `setTimeout` 回调触发          |
| `scrollend` 触发  | `true → false`     | 原生事件立即重置，不等 300ms   |

> **`scrollend` 兼容性**：Chrome 114+、Firefox 109+ 支持，Safari 暂不支持（2024）。Safari 中降级依赖 300ms 定时器。

## 注意事项

1. **仅监听最近可滚动祖先**：只找到**第一个**满足条件的祖先，不监听多层嵌套的所有滚动容器
2. **`onMounted` 后才绑定**：`scrollParent` 初始为 `null`，挂载后由 `getScrollParent` 填充；若 DOM 尚未渲染完成，`domRef.value` 为 `null` 时 `scrollParent` 保持 `null`
3. **非 passive 监听**：源码中未使用 `{ passive: true }`，`scroll` 处理函数内部不调用 `preventDefault`，实际无性能影响
4. **`oScopeDispose` 自动清理**：组件卸载时自动移除 `scroll` 和 `scrollend` 监听，无内存泄漏
5. **`overflowY: overlay` 支持**：适配旧版 WebKit 的 `-webkit-overflow-scrolling: touch` 场景

## 关联组件

（库内暂无直接引用；可在自定义浮层、下拉与消息列表联动场景自行接入。）
