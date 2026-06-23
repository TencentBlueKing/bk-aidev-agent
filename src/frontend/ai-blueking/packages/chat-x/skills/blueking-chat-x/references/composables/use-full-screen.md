# useFullScreen

> 导入：`import { useFullScreen } from '@blueking/chat-x'` ｜ since 2.0.0

useFullScreen 将目标元素（或 document.documentElement）以浏览器原生全屏展示。 模块加载时一次性嗅探 requestFullscreen / webkitRequestFullscreen，返回 isSupported、只读 isFullScreen 与 enter/exit/toggle。 监听 fullscreenchange 同步 ESC 等外部退出；ChatContainer 侧栏全屏按钮使用此 composable。

**关联**：chat-container（侧栏 .ai-full-screen-wrapper 全屏切换）、tool-btn（全屏按钮通过插槽渲染 FullScreenIcon）

---

# useFullScreen 全屏控制

> **分类**：composable

基于浏览器原生 Fullscreen API 的全屏控制组合式函数。模块加载时一次性嗅探标准 API 与 `webkit` 前缀（兼容旧版 Safari），在组件作用域销毁时自动移除事件监听。

## 工作原理

```
useFullScreen(target?)
  │
  ├── resolveFullscreenApi()（模块级，仅执行一次）
  │     requestFullscreen / webkitRequestFullscreen
  │
  ├── isSupported = !!fullscreenApi
  ├── isFullScreen（readonly shallowRef，与浏览器真实状态同步）
  │
  ├── enter()  → target.requestFullscreen()
  ├── exit()   → document.exitFullscreen()
  ├── toggle() → isFullScreen ? exit() : enter()
  │
  └── document.addEventListener(fullscreenchange, syncState)
        syncState：指定 target 时，仅当 fullscreenElement === target 视为全屏
        onScopeDispose 时移除监听
```

> **注意**：`enter()` 可能因缺少用户手势等原因被浏览器拒绝，内部会静默捕获异常，避免未处理的 Promise rejection。

## 基础用法

```vue
<template>
  <div>
    <div ref="panelRef" class="demo-panel">
      <p>可全屏展示的面板内容</p>
    </div>
    <button :disabled="!isSupported" @click="enter">进入全屏</button>
    <button :disabled="!isFullScreen" @click="exit">退出全屏</button>
    <span>当前状态：{{ isFullScreen ? '全屏' : '窗口' }}</span>
  </div>
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { useFullScreen } from '@blueking/chat-x';

  const panelRef = useTemplateRef<HTMLElement>('panelRef');
  const { isSupported, isFullScreen, enter, exit } = useFullScreen(panelRef);
</script>
```

## 在 ChatContainer 中的使用

`ChatContainer` 将侧栏包裹在 `.ai-full-screen-wrapper` 中，通过 `useFullScreen(fullScreenRef)` 控制侧栏全屏；Tab 栏 `#setting` 插槽内的 `ToolBtn` 使用自定义插槽渲染 `FullScreenIcon` / `UnFullScreenIcon`。

详见 [ChatContainer 侧栏全屏](../components/setup/chat-container.md#侧栏全屏)。

## API

### 参数

| 参数名 | 类型 | 默认值 | 说明 |
| ------ | ---- | ------ | ---- |
| target | `MaybeRef<HTMLElement \| null>` | — | 需要全屏的目标元素；省略时回退到 `document.documentElement` |

### 返回值

| 属性名 | 类型 | 说明 |
| ------ | ---- | ---- |
| isSupported | `boolean` | 当前环境是否支持 Fullscreen API（SSR 或不支持时为 `false`） |
| isFullScreen | `Readonly<ShallowRef<boolean>>` | 只读响应式全屏状态；与浏览器真实状态同步（含 ESC 退出） |
| enter | `() => Promise<void>` | 进入全屏；已全屏或不受支持时无操作 |
| exit | `() => Promise<void>` | 退出全屏；当前无全屏元素时无操作 |
| toggle | `() => void` | 切换全屏状态 |

## 类型定义

```typescript
import { useFullScreen } from '@blueking/chat-x';
import type { MaybeRef, Readonly, ShallowRef } from 'vue';

type UseFullScreenReturn = {
  isSupported: boolean;
  isFullScreen: Readonly<ShallowRef<boolean>>;
  enter: () => Promise<void>;
  exit: () => Promise<void>;
  toggle: () => void;
};

// 调用签名
declare function useFullScreen(target?: MaybeRef<HTMLElement | null>): UseFullScreenReturn;
```

## 使用场景

- `ChatContainer` 侧栏执行情况 / 自定义 Tab 区域全屏查看
- 任意需要将局部 DOM 区域以浏览器原生全屏展示的交互面板

## 关联组件

- [ChatContainer](../components/setup/chat-container.md) — 内置侧栏全屏按钮
- [ToolBtn](../components/feedback/tool-btn.md) — 全屏按钮自定义插槽
