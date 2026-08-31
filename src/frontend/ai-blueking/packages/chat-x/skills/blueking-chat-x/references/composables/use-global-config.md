# useGlobalConfig

> 导入：`import { useGlobalConfig } from '@blueking/chat-x'` ｜ since 1.0.0

useGlobalConfig 接收 GlobalConfig（含 size?: ComputedRef<AiSizeMode>、supportUpload: ComputedRef<boolean>、timezone?: ComputedRef<string | undefined>），以 GLOBAL_CONFIG_TOKEN provide 给后代； injectGlobalConfig 在子组件中取出配置，无 Provider 时返回 undefined。ChatContainer 在 setup 中调用 useGlobalConfig 注入 size、supportUpload 与 timezone； 后代组件可通过 injectGlobalConfig 读取配置；字号主题主要通过根节点 data-ai-size 与 CSS 变量生效。

**关联**：chat-container（根容器调用 useGlobalConfig 注入 supportUpload）、message-time（消息时间组件读取 timezone）

---

# useGlobalConfig 全局配置

> **分类**：composable

在聊天容器根组件与子组件之间通过 Vue `provide` / `inject` 共享**全局展示相关配置**（当前包括字号主题档位 `size`、是否支持上传 `supportUpload`、消息时间时区 `timezone`）。与 Teleport 插槽 ID 无关。

> 字号主题主要通过 `ChatContainer` 根节点的 `data-ai-size` 与 CSS 变量（`--ai-font-size` 等）生效；`GlobalConfig.size` 供后代在逻辑层读取当前档位，样式层无需逐组件传参。

## 工作原理

```
ChatContainer（根）
  ├── :data-ai-size="size"（CSS 变量作用域）
  ├── useGlobalConfig({
  │     size: computed(() => props.size ?? 'small'),
  │     supportUpload: computed(() => props.supportUpload ?? false),
  │     timezone: computed(() => props.timezone),
  │   })
  │     └── provide(GLOBAL_CONFIG_TOKEN, { size, supportUpload, timezone })
  │
  └── MessageContainer → … → UserMessage / MessageTime 等

UserMessage（后代）
  ├── injectGlobalConfig()
  │     └── inject(GLOBAL_CONFIG_TOKEN) → GlobalConfig | undefined
  └── 模板中：globalConfig?.supportUpload.value ?? false
```

- **Provider**：必须在组件树的祖先（如 `ChatContainer`）的 `setup` 中调用 `useGlobalConfig`，否则后代 `injectGlobalConfig()` 得到 `undefined`。
- **Consumer**：任意后代在 `setup` 中调用 `injectGlobalConfig()`，拿到与 Provider 相同的 `GlobalConfig` 对象引用；`supportUpload` 为 `ComputedRef<boolean>`，可随根 props 响应式更新。

## 渲染示例

## 根容器用法（ChatContainer）

```vue
<script setup lang="ts">
  import { computed } from 'vue';
  import { useGlobalConfig } from '@blueking/chat-x';

  const props = defineProps<{
    size?: 'normal' | 'small';
    supportUpload?: boolean;
    timezone?: string;
  }>();

  useGlobalConfig({
    size: computed(() => props.size ?? 'small'),
    supportUpload: computed(() => props.supportUpload ?? false),
    // 无默认值：未配置时由 MessageTime 回退到浏览器时区
    timezone: computed(() => props.timezone),
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

export type AiSizeMode = 'normal' | 'small';

export type GlobalConfig = {
  size?: ComputedRef<AiSizeMode>;
  supportUpload: ComputedRef<boolean>;
  timezone?: ComputedRef<string | undefined>;
};

export function useGlobalConfig(options: GlobalConfig): {
  size?: ComputedRef<AiSizeMode>;
  supportUpload: ComputedRef<boolean>;
  timezone?: ComputedRef<string | undefined>;
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
| `size`          | 可选。字号主题档位 `normal`（14px）/ `small`（12px），与 `ChatContainer.size` 对齐 |
| `supportUpload` | 是否支持上传，与根容器 `ChatContainer` 的 `supportUpload` 等展示策略对齐 |
| `timezone`      | 可选。消息时间展示所用的 IANA 时区名，与 `ChatContainer.timezone` 对齐；未配置时 `MessageTime` 按浏览器时区展示 |

### `useGlobalConfig(options)`

| 参数                    | 说明                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------- |
| `options.size`          | 可选。字号主题档位，建议使用 `computed(() => props.size ?? 'small')` 与根 props 同步 |
| `options.supportUpload` | 是否支持上传，建议使用 `computed(() => props.supportUpload ?? false)` 与根 props 同步 |
| `options.timezone`      | 可选。消息时间时区，建议使用 `computed(() => props.timezone)` 与根 props 同步；不设默认值，交由 `MessageTime` 回退浏览器时区 |

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

- [ChatContainer](../components/setup/chat-container) — 调用 `useGlobalConfig` 注入 `size`、`supportUpload` 与 `timezone`
- [MessageTime](../components/feedback/message-time) — 读取 `timezone` 展示消息时间
- [主题配置](../theme/theme) — `data-ai-size` 与 CSS 变量说明
