---
name: useToast
slug: use-toast
category: composable
description: 统一的 toast 出口。宿主通过 useToastContainerProvider 声明挂载容器，后代组件经 useToast 弹出的 bkui Message 会挂进该容器，避免被高层级浮层挡住。
aiSummary: >
  showToast(options, container?) 是纯函数，container 存在时以 getContainer 挂入，否则挂 document.body。
  useToastContainerProvider(container) 以 TOAST_CONTAINER_TOKEN provide 一个 HTMLElement / ref / getter；
  useToast() 在 setup 中 inject 该容器，返回 (options) => void，每次弹出时才读取容器。
  无 Provider 或不在 setup 上下文中时回退 document.body。ChatContainer 在浏览器全屏时会把容器覆盖为全屏元素。
relatedComponents:
  - slug: chat-container
    relation: 全屏时把 toast 容器覆盖为全屏元素
  - slug: chat-input
    relation: 附件个数/大小/格式校验失败时弹出提示
  - slug: use-clipboard
    relation: 复制结果提示走 useToast
sinceVersion: 3.1.2
---

# useToast 统一提示

> **分类**：composable

chat-x 内部所有提示（复制结果、附件校验失败等）都经 `useToast` 弹出，不直接调用 bkui-vue 的 `Message()`。

bkui `Message` 默认挂在 `document.body`，层级从约 6000 起算。宿主如果把聊天界面放在一个更高层级的 fixed 浮层里（例如 AIBlueking 的 `z-index: 10000`），提示会被浮层挡住。宿主可以提供一个位于自己层叠上下文内的容器，chat-x 的提示就会挂进去。

## 导出

| 名称 | 说明 |
| --- | --- |
| `showToast(options, container?)` | 纯函数。有 `container` 时传给 Message 的 `getContainer`（Message 改为 `absolute` 定位），否则挂 `document.body` |
| `useToastContainerProvider(container)` | 由宿主调用，向后代声明 toast 容器。接收 `HTMLElement`、`Ref` 或 getter |
| `useToastContainerInject()` | 取出祖先声明的容器；无 Provider 或不在 setup 中时返回 `undefined` |
| `useToast()` | 返回绑定了注入容器的 `(options: ShowToastOptions) => void`；容器在每次弹出时读取 |
| `TOAST_CONTAINER_TOKEN` | 注入 key |
| `ShowToastOptions` / `ToastFn` / `ToastContainer` | 类型 |

## 宿主接入

```vue
<template>
  <div class="my-overlay">
    <ChatContainer ... />
    <div ref="toastHostRef" class="my-toast-host" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useToastContainerProvider } from '@blueking/chat-x';

  const toastHostRef = ref<HTMLElement>();
  useToastContainerProvider(toastHostRef);
</script>

<style scoped>
  .my-overlay {
    position: fixed;
    inset: 0;
    z-index: 10000;
    pointer-events: none;
  }

  /* 铺满浮层，Message 以 absolute 相对它定位，视觉上与挂 body 时一致 */
  .my-toast-host {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  /* 浮层的 pointer-events: none 会被继承，Message 需要恢复才能点击关闭 */
  .my-toast-host :deep(.bk-message) {
    pointer-events: auto;
  }
</style>
```

宿主自身的 setup 里 inject 不到自己 provide 的值。如果宿主组件本身也要弹提示，直接调用 `showToast(options, toastHostRef.value)`。

## 全屏

`ChatContainer` 侧栏全屏使用浏览器原生全屏 API，此时只渲染全屏元素的子树。`ChatContainer` 会在全屏期间把 toast 容器覆盖为全屏元素，退出全屏后恢复为上层注入的容器，与 tippy `appendTo` 的处理方式一致。

## 不注入时

独立使用 `ChatContainer` / `ChatInput` 且没有 Provider 时，提示仍挂 `document.body`，行为与直接调用 `Message()` 相同。
