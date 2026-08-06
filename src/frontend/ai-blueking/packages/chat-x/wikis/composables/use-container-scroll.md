---
name: useContainerScroll
slug: use-container-scroll
category: composable
description: 为消息容器提供滚动控制的组合式函数对，通过 **Provider/Consumer** 模式在父子组件间共享滚动状态。
aiSummary: >
  useContainerScrollProvider 在滚动容器与底部锚点上绑定 IntersectionObserver、scroll、wheel，提供 isScrollBottom、scrollBottomHeight、autoScrollEnabled、jumpToBottom、toScrollBottom/toScrollTop 及防抖「返回底部」按钮状态。
  toScrollBottom 缺省按距底部距离自动选择行为：超过 INSTANT_SCROLL_DISTANCE（600px）时瞬时贴底，否则平滑滚动，避免切换会话时出现长距离平滑滚动动画。
  useContainerScrollConsumer 通过 inject 在子组件中获取同一套控制，无需 props 透传。
  典型用于流式输出时仅在用户位于底部时自动滚底。MessageContainer 与 ScrollBtn 配合使用。
relatedComponents:
  - slug: message-container
    relation: Provider 挂载于消息列表滚动区域
  - slug: scroll-btn
    relation: 使用 debouncedShowScrollBottomBtn 与 toScrollBottom
  - slug: chat-container
    relation: 组合消息区与输入区时的整体布局上下文
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref, useTemplateRef } from 'vue';
  import { useContainerScrollProvider } from '../../src/composables/use-container-scroll';

  const containerRef = useTemplateRef<HTMLElement>('containerRef');
  const bottomRef = useTemplateRef<HTMLElement>('bottomRef');

  const { isScrollBottom, scrollBottomHeight, autoScrollEnabled, jumpToBottom, toScrollBottom, toScrollTop } =
    useContainerScrollProvider(containerRef, bottomRef);

  const items = ref(Array.from({ length: 30 }, (_, i) => `消息 ${i + 1}：这是一条示例消息内容，用于撑开容器高度。`));

  const addItem = () => {
    items.value.push(`新消息 ${items.value.length + 1}：${new Date().toLocaleTimeString()} 追加的内容`);
    if (autoScrollEnabled.value) {
      toScrollBottom();
    }
  };
</script>

# useContainerScroll 容器滚动

> **分类**：composable

为消息容器提供滚动控制的组合式函数对，通过 **Provider/Consumer** 模式在父子组件间共享滚动状态。

- `useContainerScrollProvider`：在容器组件中调用，创建滚动控制并通过 `provide` 向下共享
- `useContainerScrollConsumer`：在任意后代组件中调用，通过 `inject` 获取滚动控制

## 工作原理

```
useContainerScrollProvider(containerRef, bottomRef)
  │
  ├── IntersectionObserver 监听 bottomRef
  │     可见 → isScrollBottom=true, scrollBottomHeight=0, autoScrollEnabled=true
  │     不可见 → isScrollBottom=false, calculateScrollBottom()
  │
  ├── scroll 事件（passive）→ calculateScrollBottom()
  │     scrollBottomHeight = max(0, scrollHeight - scrollTop - clientHeight)
  │
  ├── wheel 事件（passive）→ deltaY < 0 时 autoScrollEnabled=false
  │     （用户向上滚动时暂停自动滚动）
  │
  ├── jumpToBottom()   → autoScrollEnabled=true + container.scrollTop = scrollHeight（瞬时）
  ├── toScrollBottom(behavior?) → autoScrollEnabled=true；
  │     behavior 缺省时：距底部 > INSTANT_SCROLL_DISTANCE(600) → jumpToBottom()
  │     否则 / 显式 'smooth' → bottomRef.scrollIntoView({ behavior:'smooth', block:'end' })
  ├── toScrollTop()    → containerRef.scrollTo({ top:0, behavior:'smooth' })
  │
  └── provide(CONTAINER_SCROLL_TOKEN, computed(() => ({
            autoScrollEnabled: autoScrollEnabled.value,  // 解包为 boolean
            isScrollBottom,             // ShallowRef<boolean>（保持响应式）
            scrollBottomHeight,         // ShallowRef<number>（保持响应式）
            debouncedShowScrollBottomBtn, // customRef，防抖显示返回底部按钮
            jumpToBottom,
            toScrollBottom,
            toScrollTop,
        })))

useContainerScrollConsumer()
  └── inject(CONTAINER_SCROLL_TOKEN) → ComputedRef<ContainerScrollData> | undefined
```

> **注意**：Consumer 获得的 `ComputedRef` 中，`isScrollBottom` 和 `scrollBottomHeight` 是 `ShallowRef` 对象（非解包值），需要通过 `.value` 访问。

## 渲染示例

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 8px;">
    <!-- 状态面板 -->
    <div style="display: flex; gap: 16px; font-size: 12px; font-family: monospace; background: #f5f7fa; padding: 8px 12px; border-radius: 4px; flex-wrap: wrap;">
      <span>isScrollBottom: <strong :style="{ color: isScrollBottom ? '#2caf5e' : '#ea3636' }">{{ isScrollBottom }}</strong></span>
      <span>scrollBottomHeight: <strong style="color: #3a84ff;">{{ scrollBottomHeight }}px</strong></span>
      <span>autoScrollEnabled: <strong :style="{ color: autoScrollEnabled ? '#2caf5e' : '#f59500' }">{{ autoScrollEnabled }}</strong></span>
    </div>
    <!-- 滚动容器 -->
    <div
      ref="containerRef"
      style="height: 200px; overflow-y: auto; border: 1px solid #dcdee5; border-radius: 4px; padding: 8px;"
    >
      <div
        v-for="(item, i) in items"
        :key="i"
        style="padding: 6px 8px; margin-bottom: 4px; background: #fff; border-radius: 4px; font-size: 13px; border: 1px solid #f0f1f5;"
      >
        {{ item }}
      </div>
      <div ref="bottomRef" style="height: 1px;" />
    </div>
    <!-- 控制按钮 -->
    <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
      <button
        @click="addItem"
        style="padding: 4px 12px; font-size: 12px; border: 1px solid #3a84ff; color: #3a84ff; border-radius: 4px; cursor: pointer; background: #fff;"
      >
        追加消息
      </button>
      <button
        @click="() => toScrollBottom('smooth')"
        style="padding: 4px 12px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
      >
        滚动到底部
      </button>
      <button
        @click="toScrollTop"
        style="padding: 4px 12px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
      >
        滚动到顶部
      </button>
    </div>
    <p style="margin: 0; font-size: 12px; color: #979ba5;">
      向上滚动 → autoScrollEnabled 变为 false；回到底部 → 恢复 true。追加消息时若 autoScrollEnabled=true 则自动滚底。
    </p>
  </div>
</div>

## Provider（父组件）

```vue
<template>
  <div
    ref="containerRef"
    class="message-container"
  >
    <MessageItem
      v-for="msg in messages"
      :key="msg.id"
      :message="msg"
    />
    <div ref="bottomRef" />
  </div>

  <!-- 距离底部 > 100px 且防抖 300ms 后显示"返回底部"按钮；显式传 'smooth' 避免 MouseEvent 被当成 behavior -->
  <ScrollBtn
    v-show="debouncedShowScrollBottomBtn"
    @click="() => toScrollBottom('smooth')"
  >
    返回底部
  </ScrollBtn>
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { useContainerScrollProvider } from '@blueking/chat-x';

  const containerRef = useTemplateRef<HTMLElement>('containerRef');
  const bottomRef = useTemplateRef<HTMLElement>('bottomRef');

  const {
    isScrollBottom,
    scrollBottomHeight,
    debouncedShowScrollBottomBtn,
    autoScrollEnabled,
    jumpToBottom,
    toScrollBottom,
    toScrollTop,
  } = useContainerScrollProvider(containerRef, bottomRef);
</script>

<style scoped>
  .message-container {
    height: 400px;
    overflow-y: auto;
  }
</style>
```

## Consumer（子组件）

后代组件通过 `useContainerScrollConsumer` 获取滚动控制，无需 props 传递：

```vue
<script setup lang="ts">
  import { useContainerScrollConsumer } from '@blueking/chat-x';

  const containerScroll = useContainerScrollConsumer();

  // 组件挂载（如新消息渲染）后触发滚动
  const handleMounted = () => {
    containerScroll?.value?.toScrollBottom?.();
  };
</script>
```

> Consumer 的 `containerScroll` 是 `ComputedRef`，需要双层 `.value` 访问：
>
> ```typescript
> containerScroll?.value?.isScrollBottom?.value; // 读取 isScrollBottom 布尔值
> containerScroll?.value?.scrollBottomHeight?.value; // 读取距底部距离
> ```

## 流式输出自动滚动

`autoScrollEnabled` 配合流式更新实现"用户手动滚上去就暂停，回底部就恢复"的交互：

```vue
<script setup lang="ts">
  import { watch } from 'vue';
  import { useContainerScrollProvider } from '@blueking/chat-x';

  const { autoScrollEnabled, toScrollBottom } = useContainerScrollProvider(containerRef, bottomRef);

  // 监听流式内容更新
  watch(streamingContent, () => {
    if (autoScrollEnabled.value) {
      toScrollBottom();
    }
    // autoScrollEnabled=false 时用户正在向上查看，不打断
  });
</script>
```

## API

### useContainerScrollProvider

```typescript
function useContainerScrollProvider(
  containerRef: MaybeRef<HTMLElement | null>,
  bottomRef: MaybeRef<HTMLElement | null>,
): {
  autoScrollEnabled: ShallowRef<boolean>;
  isScrollBottom: ShallowRef<boolean>;
  scrollBottomHeight: ShallowRef<number>;
  debouncedShowScrollBottomBtn: Ref<boolean>;
  jumpToBottom: () => void;
  toScrollBottom: (behavior?: ScrollBehavior) => void;
  toScrollTop: () => void;
};
```

**参数：**

| 参数           | 类型                            | 说明                                                         |
| -------------- | ------------------------------- | ------------------------------------------------------------ |
| `containerRef` | `MaybeRef<HTMLElement \| null>` | 滚动容器引用；`watchEffect` 内响应式追踪，变化时重新绑定监听 |
| `bottomRef`    | `MaybeRef<HTMLElement \| null>` | 底部锚点元素引用；供 `IntersectionObserver` 检测可见性       |

**返回值：**

| 属性名                         | 类型                                    | 初始值  | 说明                                                                                                                  |
| ------------------------------ | --------------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------- |
| `isScrollBottom`               | `ShallowRef<boolean>`                   | `false` | 底部锚点是否可见（`IntersectionObserver` 驱动）                                                                       |
| `scrollBottomHeight`           | `ShallowRef<number>`                    | `0`     | 距底部像素距离（`scrollHeight - scrollTop - clientHeight`，≥ 0）                                                      |
| `autoScrollEnabled`            | `ShallowRef<boolean>`                   | `true`  | 是否允许自动滚底；向上滚时置 `false`，到达底部或调用 `toScrollBottom` / `jumpToBottom` 时恢复 `true`                  |
| `debouncedShowScrollBottomBtn` | `Ref<boolean>`                          | `false` | 防抖版"返回底部"按钮显隐标志：距底部 > `SHOW_SCROLL_BOTTOM_BTN_DISTANCE`（100px）时触发，显示延迟 300ms，隐藏立即生效 |
| `jumpToBottom`                 | `() => void`                            | —       | 瞬时贴底（直接写 `scrollTop`），不产生滚动动画                                                                        |
| `toScrollBottom`               | `(behavior?: ScrollBehavior) => void`   | —       | 滚动到底部。**缺省按距底部距离自动选择**：超过 `INSTANT_SCROLL_DISTANCE`（600px）时瞬时贴底，否则平滑滚动；可显式传 `'smooth'` / `'auto'` |
| `toScrollTop`                  | `() => void`                            | —       | 滚动到顶部（`scrollTo({ top: 0, behavior: 'smooth' })`）                                                              |

### useContainerScrollConsumer

```typescript
function useContainerScrollConsumer():
  | ComputedRef<{
      autoScrollEnabled: boolean; // 已解包为 boolean
      isScrollBottom: ShallowRef<boolean>; // ShallowRef，未解包
      scrollBottomHeight: ShallowRef<number>; // ShallowRef，未解包
      jumpToBottom: () => void;
      toScrollBottom: (behavior?: ScrollBehavior) => void;
      toScrollTop: () => void;
    }>
  | undefined;
```

- 无 Provider 时返回 `undefined`，需做非空判断
- 返回值是 `ComputedRef`，每次访问 `.value` 均为最新快照

## 类型定义

```typescript
// provide/inject 使用的 Symbol key
export const CONTAINER_SCROLL_TOKEN: unique symbol;

// 触发"返回底部"按钮显示的距底部阈值（px）
export const SHOW_SCROLL_BOTTOM_BTN_DISTANCE = 100;

// 距底部超过该阈值时，toScrollBottom 缺省走瞬时贴底（避免长距离 smooth 动画）
export const INSTANT_SCROLL_DISTANCE = 600;

export type ContainerScrollData = {
  autoScrollEnabled: boolean;
  isScrollBottom: boolean;
  scrollBottomHeight: number;
  debouncedShowScrollBottomBtn: Ref<boolean>;
  jumpToBottom: () => void;
  toScrollBottom: (behavior?: ScrollBehavior) => void;
  toScrollTop: () => void;
};
```

## 注意事项

1. **`isScrollBottom` 初始值为 `false`**：`IntersectionObserver` 在 `onMounted` 后才绑定，挂载前状态为 `false`
2. **`watchEffect` 在 `onMounted` 内**：`containerRef` / `bottomRef` 变化时自动清理旧监听、重新绑定，无需手动管理
3. **`onScopeDispose` 自动清理**：组件卸载时自动 `disconnect` observer、移除 `scroll`/`wheel` 监听
4. **Consumer 需两层 `.value`**：Consumer 获得 `ComputedRef`，其中 `isScrollBottom` 和 `scrollBottomHeight` 仍为 `ShallowRef`，访问时需 `containerScroll.value.isScrollBottom.value`
5. **`MessageContainer` 中的使用**：「返回底部」`ScrollBtn` 使用 `@click="() => toScrollBottom('smooth')"`（显式 smooth）；挂载时另调 `jumpToBottom()` 消除切换会话时的顶部闪烁
6. **不要把 `toScrollBottom` 直接绑到事件**：`@click="toScrollBottom"` 会把 `MouseEvent` 当成 `behavior` 传入，应写成 `@click="() => toScrollBottom('smooth')"`

## 关联组件

- [MessageContainer](../components/setup/message-container) — Provider 与返回底部交互
- [ScrollBtn](../components/feedback/scroll-btn) — 返回底部按钮
- [ChatContainer](../components/setup/chat-container) — 聊天主布局
