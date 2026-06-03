---
name: useGlobalConfig
slug: use-global-config
category: composable
description: 在聊天根容器与子组件之间通过 provide/inject 共享全局展示配置（如是否支持上传）。
aiSummary: >
  useGlobalConfig 接收 GlobalConfig（含 supportUpload: ComputedRef<boolean>），以 GLOBAL_CONFIG_TOKEN provide 给后代；
  injectGlobalConfig 在子组件中取出配置，无 Provider 时返回 undefined。ChatContainer 在 setup 中调用 useGlobalConfig；
  UserMessage 等通过 injectGlobalConfig 读取 supportUpload。
relatedComponents:
  - slug: chat-container
    relation: 根容器调用 useGlobalConfig 注入 supportUpload
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { useGlobalConfig } from '../../src/composables/use-global-config';

  const uploadEnabled = ref(true);
  const supportUpload = computed(() => uploadEnabled.value);

  const { supportUpload: rootSupportUpload } = useGlobalConfig({ supportUpload });
</script>

# useGlobalConfig 全局配置

> **分类**：composable

在聊天容器根组件与子组件之间通过 Vue `provide` / `inject` 共享**全局展示相关配置**（当前主要为是否支持上传 `supportUpload`）。与 Teleport 插槽 ID 无关。

## 工作原理

```
ChatContainer（根）
  ├── useGlobalConfig({ supportUpload: computed(() => props.supportUpload ?? false) })
  │     └── provide(GLOBAL_CONFIG_TOKEN, { supportUpload })
  │
  └── MessageContainer → … → UserMessage 等

UserMessage（后代）
  ├── injectGlobalConfig()
  │     └── inject(GLOBAL_CONFIG_TOKEN) → GlobalConfig | undefined
  └── 模板中：globalConfig?.supportUpload.value ?? false
```

- **Provider**：必须在组件树的祖先（如 `ChatContainer`）的 `setup` 中调用 `useGlobalConfig`，否则后代 `injectGlobalConfig()` 得到 `undefined`。
- **Consumer**：任意后代在 `setup` 中调用 `injectGlobalConfig()`，拿到与 Provider 相同的 `GlobalConfig` 对象引用；`supportUpload` 为 `ComputedRef<boolean>`，可随根 props 响应式更新。

## 渲染示例

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 8px; font-size: 13px; font-family: monospace;">
    <label style="display: flex; align-items: center; gap: 8px;">
      <input type="checkbox" v-model="uploadEnabled" />
      模拟 supportUpload 为 true
    </label>
    <div style="background: #f5f7fa; padding: 10px 14px; border-radius: 4px; line-height: 1.8;">
      <div><strong>useGlobalConfig 返回值：</strong></div>
      <div>rootSupportUpload.value = <span style="color: #3a84ff;">{{ rootSupportUpload }}</span></div>
    </div>
    <div style="font-size: 12px; color: #979ba5;">
      子组件（如 UserMessage）在自身 <code>setup</code> 中调用 <code>injectGlobalConfig()</code> 即可读取同一套
      <code>supportUpload</code>（本页 demo 仅在根层演示 <code>useGlobalConfig</code> 返回值）。
    </div>
  </div>
</div>

## 根容器用法（ChatContainer）

```vue
<script setup lang="ts">
  import { computed } from 'vue';
  import { useGlobalConfig } from '@blueking/chat-x';

  const props = defineProps<{
    supportUpload?: boolean;
  }>();

  useGlobalConfig({
    supportUpload: computed(() => props.supportUpload ?? false),
  });
</script>
```

## 子组件用法（UserMessage）

```vue
<script setup lang="ts">
  import { injectGlobalConfig } from '@blueking/chat-x';

  const globalConfig = injectGlobalConfig();
</script>

<template>
  <ChatInput :support-upload="globalConfig?.supportUpload.value ?? false" />
</template>
```

## API

### 类型与函数签名（摘要）

```typescript
import type { ComputedRef } from 'vue';

export const GLOBAL_CONFIG_TOKEN: unique symbol;

export type GlobalConfig = {
  supportUpload: ComputedRef<boolean>;
};

export function useGlobalConfig(options: GlobalConfig): {
  supportUpload: ComputedRef<boolean>;
};

export function injectGlobalConfig(): GlobalConfig | undefined;
```

### `GLOBAL_CONFIG_TOKEN`

| 名称                  | 说明                                   |
| --------------------- | -------------------------------------- |
| `GLOBAL_CONFIG_TOKEN` | `provide` / `inject` 使用的 Symbol key |

### `GlobalConfig`

| 字段            | 说明                                                                     |
| --------------- | ------------------------------------------------------------------------ |
| `supportUpload` | 是否支持上传，与根容器 `ChatContainer` 的 `supportUpload` 等展示策略对齐 |

### `useGlobalConfig(options)`

| 参数                    | 说明                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------- |
| `options.supportUpload` | 是否支持上传，建议使用 `computed(() => props.supportUpload ?? false)` 与根 props 同步 |

- 调用后立即 `provide(GLOBAL_CONFIG_TOKEN, options)`。
- 必须在具有组件实例上下文的 `setup` 中调用（与 Vue `provide` 要求一致）。

### `injectGlobalConfig()`

| 返回值         | 说明                                                        |
| -------------- | ----------------------------------------------------------- |
| `GlobalConfig` | 祖先已调用 `useGlobalConfig` 时，与 Provider 传入的同一对象 |
| `undefined`    | 组件树中无对应 `provide` 时                                 |

## 注意事项

1. **Provider 须在祖先调用**：子组件的 `injectGlobalConfig` 依赖同一组件树内的 `useGlobalConfig`。
2. **可选链访问**：无 Provider 时返回 `undefined`，模板中建议使用 `globalConfig?.supportUpload.value ?? false`。
3. **扩展配置**：后续若在 `GlobalConfig` 中增加字段，应在根容器统一传入并在文档中说明。

## 关联组件

- [ChatContainer](../components/setup/chat-container) — 调用 `useGlobalConfig` 注入 `supportUpload`
