# 指令总览

`@blueking/chat-x` 目前提供以下 Vue 自定义指令：

| 指令              | 说明                       | 关键特性                                                                | 文档                       |
| ----------------- | -------------------------- | ----------------------------------------------------------------------- | -------------------------- |
| `v-overflow-tips` | 水平溢出时悬浮显示完整内容 | `IntersectionObserver` 懒绑定，按需创建 Tippy 实例，`onHidden` 自动销毁 | [查看](./overflow-tips.md) |

## 引入方式

### 组件内局部使用（推荐）

```vue
<template>
  <div
    v-overflow-tips
    class="ellipsis"
  >
    这是一段很长的文本，超出容器宽度时悬浮显示完整内容
  </div>
</template>

<script setup lang="ts">
  import { OverflowTips as vOverflowTips } from '@blueking/chat-x';
</script>

<style scoped>
  .ellipsis {
    width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
```

### 全局注册

```typescript
import { createApp } from 'vue';
import { OverflowTips } from '@blueking/chat-x';

const app = createApp(App);
app.directive('overflow-tips', OverflowTips);
app.mount('#app');
```

全局注册后，所有组件可直接使用 `v-overflow-tips`，无需单独引入。

## 注意事项

- **仅检测水平溢出**：通过 `scrollWidth > clientWidth` 判断，多行 `-webkit-line-clamp` 截断不会触发 tooltip
- **无 `update` 钩子**：`binding.value` 运行时变化（如 `disabled` 切换）仅在下次 `mouseenter` 生效
- **勿覆盖 `onHidden`**：指令依赖 `onHidden` 回调自动销毁 Tippy 实例，覆盖会导致内存泄漏
- **默认主题**：`'ai-chat-box'`（组件库内置），替换为其他主题需引入对应 Tippy CSS
