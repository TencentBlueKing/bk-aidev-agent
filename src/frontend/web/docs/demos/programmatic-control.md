---
aside: false
---

# 编程式控制

通过 `ref` 拿到 `AIBlueking` 实例后，业务页面可以主动打开面板、带上下文提问、触发快捷指令。下面每个配方对应一个真实业务场景：上半部分是模拟的宿主页面，可以直接操作；下半部分可以查看**实际执行的代码**、组件抛出的事件，以及小鲸发出的请求。

```ts
import { ref } from 'vue';
import type { AIBluekingExpose } from '@blueking/ai-blueking';

const aiBluekingRef = ref<AIBluekingExpose>();
// <AIBlueking ref="aiBluekingRef" url="..." />
// 配方中的 ai 参数即 aiBluekingRef.value
```

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 打开与就绪

`show()` 会立即显示面板，并在会话初始化完成后 resolve。因此 `await show()` 之后即可安全读取 `getChatHelper()?.session`，无需监听额外事件。

<ClientOnly>
  <RecipeOpenAndReady />
</ClientOnly>

## 带上下文提问

业务页通常已经掌握了用户正在看的内容。与其让用户复制粘贴，不如直接把上下文交给小鲸：可以作为引用让用户补充问题（`setCiteText`），也可以替用户直接提问（`sendMessage`）；回复过长时可以用 `stopGeneration` 中止。

<ClientOnly>
  <RecipeAlertDiagnosis />
</ClientOnly>

## 快捷指令：三种触发方式

::: tip 从旧版迁移
旧版 `window.aiBlueking.handleShortcutClick` 已废弃。新版拆成 `selectShortcut`（打开表单，可预填）与 `sendShortcut`（跳过表单直接发送）两个方法，语义更清晰。
:::

「直接发送」还演示了**单次请求注入**：`requestOptions` 在初始化时传入一次稳定的函数引用，发送前通过 `scoped.runWith` 临时注入 Header，结束后在 `finally` 中自动清除，不会污染后续请求。完整实现见 `scoped-request-options.ts`：

```ts
import { shallowRef } from 'vue';

export function createScopedRequestOptions() {
  const active = shallowRef<ScopedOptions | undefined>();
  const requestOptions = {
    headers: (): Record<string, string> => active.value?.headers?.() ?? {},
    data: (): Record<string, unknown> => ({ ...(active.value?.data?.() ?? {}) }),
  };
  async function runWith(opts: ScopedOptions, fn: () => Promise<void>): Promise<void> {
    active.value = opts;
    try {
      await fn();
    } finally {
      active.value = undefined;
    }
  }
  return { requestOptions, runWith, getActive: () => active.value };
}

export const scoped = createScopedRequestOptions();
// <AIBlueking :request-options="scoped.requestOptions" />
```

<ClientOnly>
  <RecipeSqlShortcut />
</ClientOnly>

## 相关文档

- [编程式控制指南](/guide/advanced-usage/programmatic-control)：全部 expose 方法与 ChatBot 的对应用法
- [快捷指令](/guide/core-features/shortcuts)：快捷指令的配置与表单字段
- [自定义请求](/guide/advanced-usage/custom-requests)：`requestOptions` 的 headers / data / context
- [AIBlueking 组件 API](/api/ai-blueking/aiblueking)
