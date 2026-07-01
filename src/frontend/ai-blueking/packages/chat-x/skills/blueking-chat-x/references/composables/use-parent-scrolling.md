# useParentScrolling

> 导入：`import { useParentScrolling } from '@blueking/chat-x'` ｜ since 1.0.0

useParentScrolling(domRef) 在挂载后通过 getScrollParent 找到最近可滚动祖先，监听 scroll 与 scrollend，返回 isScrolling 与 scrollParent。 scroll 时将 isScrolling 置 true，300ms 无滚动或 scrollend 时置 false，适合滚动时隐藏浮层等交互。getScrollParent 可单独导出使用。 当前源码无组件内引用，供业务或后续浮层组件按需集成。

---

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
