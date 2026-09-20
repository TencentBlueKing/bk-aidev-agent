# useContainerScroll

> 导入：`import { useContainerScrollConsumer, useContainerScrollProvider } from '@blueking/chat-x'` ｜ since 1.0.0

useContainerScrollProvider 在滚动容器与底部锚点上绑定 IntersectionObserver、scroll、wheel，提供 isScrollBottom、scrollBottomHeight、autoScrollEnabled、jumpToBottom、toScrollBottom/toScrollTop 及防抖「返回底部」按钮状态。 toScrollBottom 缺省按距底部距离自动选择行为：超过 INSTANT_SCROLL_DISTANCE（600px）时瞬时贴底，否则平滑滚动，避免切换会话时出现长距离平滑滚动动画。 useContainerScrollConsumer 通过 inject 在子组件中获取同一套控制，无需 props 透传。 典型用于流式输出时仅在用户位于底部时自动滚底。MessageContainer 与 ScrollBtn 配合使用。

**关联**：message-container（Provider 挂载于消息列表滚动区域）、scroll-btn（使用 debouncedShowScrollBottomBtn 与 toScrollBottom）、chat-container（组合消息区与输入区时的整体布局上下文）

---

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
