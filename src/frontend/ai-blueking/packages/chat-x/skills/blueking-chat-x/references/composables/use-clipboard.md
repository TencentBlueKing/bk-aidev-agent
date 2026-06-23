# useClipboard

> 导入：`import { useClipboard } from '@blueking/chat-x'` ｜ since 1.0.0

useClipboard 返回 { copy }，copy(text) 将字符串写入剪贴板，返回 Promise<void>。 优先使用 navigator.clipboard.writeText，失败或不支持时降级为隐藏 textarea + execCommand('copy')。 成功/失败均通过 bkui-vue Message 提示，调用方无需处理结果。CodeContent、MessageContainer、UserMessage 的复制能力内部使用。

**关联**：code-content（复制代码块时取 innerText 后调用 copy）、message-container（AI 消息复制工具回调）、user-message（用户消息复制工具回调）

---

# useClipboard 剪贴板

> **分类**：composable

复制文本到剪贴板的组合式函数。内置两级降级策略，并自动通过 bkui-vue `Message` 提示复制结果，调用方无需关心成功/失败处理。

## 执行流程

```
copy(text)
  │
  ├── isClipboardApiSupported（模块加载时判断一次）
  │     = typeof navigator !== 'undefined' && 'clipboard' in navigator
  │
  ├── true → navigator.clipboard.writeText(text)
  │           ├── 成功 → success = true
  │           └── 失败（权限拒绝等）→ legacyCopy(text)
  │
  └── false → legacyCopy(text)
              （创建隐藏 textarea，document.execCommand('copy')，finally 清理 DOM）
  │
  └── Message({ message: t('复制成功/失败'), theme: 'success/error' })
```

> **注意**：`copy` 返回 `Promise<void>`，调用方无法获取成功/失败结果；通知由内部自动弹出，不可关闭或自定义。

## 基础用法

```vue
<template>
  <button @click="handleCopy">复制文本</button>
</template>

<script setup lang="ts">
  import { useClipboard } from '@blueking/chat-x';

  const { copy } = useClipboard();

  const handleCopy = () => {
    copy('Hello, World!');
    // 自动弹出"复制成功/失败"提示，无需额外处理
  };
</script>
```

## 复制代码块内容

`CodeContent` 组件内部的实际用法，取 DOM 元素的 `innerText` 避免 HTML 实体：

```vue
<template>
  <div class="code-block">
    <pre ref="codeRef"><code>{{ code }}</code></pre>
    <button @click="handleCopyCode">复制代码</button>
  </div>
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { useClipboard } from '@blueking/chat-x';

  const codeRef = useTemplateRef<HTMLElement>('codeRef');
  const { copy } = useClipboard();

  // 使用 innerText 获取渲染后的纯文本，而非原始 token.content
  const handleCopyCode = () => {
    copy(codeRef.value?.innerText ?? '');
  };
</script>
```

## 复制消息内容

`MessageContainer` 和 `UserMessage` 内部的实际用法：

```vue
<script setup lang="ts">
  import { useClipboard } from '@blueking/chat-x';

  const { copy } = useClipboard();

  // 在 onAction 工具回调中调用
  const onAction = tool => {
    if (tool.id === 'copy') {
      copy(props.content ?? '');
    }
  };
</script>
```

## API

### 返回值

| 属性名 | 类型                              | 说明                                                 |
| ------ | --------------------------------- | ---------------------------------------------------- |
| copy   | `(text: string) => Promise<void>` | 复制文本；内部自动弹出结果提示，调用方无需处理返回值 |

### copy(text)

```typescript
const copy: (text: string) => Promise<void>;
```

**参数：**

- `text: string`：要复制的文本内容

**内部行为：**

| 步骤         | 说明                                                                                                           |
| ------------ | -------------------------------------------------------------------------------------------------------------- |
| 1. 能力检测  | 模块导入时执行一次：`typeof navigator !== 'undefined' && 'clipboard' in navigator`                             |
| 2a. 现代路径 | `navigator.clipboard.writeText(text)`，捕获异常后降级到步骤 2b                                                 |
| 2b. 降级路径 | 创建隐藏 `textarea`（`position: fixed; left: -9999px; opacity: 0`），`execCommand('copy')`，`finally` 清理 DOM |
| 3. 通知      | 始终调用 `Message({ message: t('复制成功/失败'), theme: 'success/error' })`                                    |

## 实现源码

```typescript
import { Message } from 'bkui-vue';
import { t } from '../lang/lang';

// 模块加载时检测一次，SSR 安全
const isClipboardApiSupported = typeof navigator !== 'undefined' && 'clipboard' in navigator;

const legacyCopy = (text: string): boolean => {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea); // 无论成败都清理 DOM
  }
};

export const useClipboard = () => {
  const copy = async (text: string) => {
    let success = false;
    if (isClipboardApiSupported) {
      try {
        await navigator.clipboard.writeText(text);
        success = true;
      } catch {
        success = legacyCopy(text); // Clipboard API 失败时降级
      }
    } else {
      success = legacyCopy(text);
    }
    Message({
      message: success ? t('复制成功') : t('复制失败'),
      theme: success ? 'success' : 'error',
    });
  };

  return { copy };
};
```

## 兼容性

| 策略                            | 触发条件                                      | 要求                                           |
| ------------------------------- | --------------------------------------------- | ---------------------------------------------- |
| `navigator.clipboard.writeText` | 浏览器支持 Clipboard API                      | HTTPS 或 localhost；用户需授权剪贴板权限       |
| `document.execCommand('copy')`  | 不支持 Clipboard API，或 `writeText` 抛出异常 | 需由用户事件（如 click）直接触发，否则可能失败 |

## 内部使用场景

| 组件               | 用途                                      |
| ------------------ | ----------------------------------------- |
| `CodeContent`      | 复制代码块，取 `codeRef.value?.innerText` |
| `MessageContainer` | 复制 AI 消息内容                          |
| `UserMessage`      | 复制用户消息内容                          |

## 注意事项

1. **结果不对外暴露**：`copy` 返回 `Promise<void>`，调用方无法获知成功/失败；如需自定义通知，不应使用此 composable
2. **通知使用 i18n**：消息文本通过 `t()` 函数处理，在多语言环境下自动切换，无法在外部覆盖
3. **`isClipboardApiSupported` 模块级检测**：在文件 import 时执行一次（非响应式），SSR 环境下 `navigator` 为 `undefined` 时安全降级
4. **`execCommand` 已废弃**：降级路径依赖 `document.execCommand('copy')`，该 API 在部分浏览器已标记废弃，但目前仍广泛可用
5. **用户手势要求**：在没有用户交互上下文时（如定时器回调），两种方式都可能失败

## 关联组件

- [CodeContent](../components/rendering/code-content) — 代码块复制
- [MessageContainer](../components/setup/message-container) — 助手消息复制
- [UserMessage](../components/message/user-message) — 用户消息复制
