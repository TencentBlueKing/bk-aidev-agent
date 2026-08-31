# CiteContent 引用内容

> 能力域：内容渲染 ｜ 导入：`import { CiteContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染输入或消息中的引用片段。 源码位置：src/components/chat-content/cite-content/cite-content.vue。

**关联**：chat-input（输入区展示待发送引用内容）

---

# CiteContent 引用内容
## 源码事实

- **源码位置**：`src/components/chat-content/cite-content/cite-content.vue`
- **能力域**：内容渲染
- **能力说明**：渲染输入或消息中的引用片段。

> **能力域**：内容渲染

展示被引用文本片段的紧凑条带组件。固定高度 28px，左侧引用图标 + 单行截断文本 + 可选关闭图标，背景灰色（`#f5f7fa`），hover 背景为 `#eaebf0`。

常见于两处：

- **`UserMessage`**：`property.extra.cite` 为字符串时，渲染在消息气泡上方
- **`ChatInput`**：通过 `v-model:cite` 绑定，渲染在输入框顶部，关闭后清空引用

## 组件结构

```
.ai-cite-content（flex，height: 28px，padding: 0 8px，gap: 4px，bg: #f5f7fa，hover: #eaebf0，border-radius: 4px，margin-bottom: 4px）
├── CiteIcon（14×14px，color: #979ba5，始终显示）
├── .ai-cite-content-text（flex: 1，单行截断，color: #979ba5，overflow: hidden，text-overflow: ellipsis）
│     {{ content }}（Vue 文本插值，XSS 安全）
└── CloseIcon（14×14px，color: #979ba5，v-if="onClose"，hover: #4d4f56）
      @click → onClose(content)
```

## 基础用法

```vue
<template>
  <CiteContent content="这是一段被引用的文本" />
</template>

<script setup lang="ts">
  import { CiteContent } from '@blueking/chat-x';
</script>
```

## 可关闭引用

传入 `onClose` 函数后，右侧显示关闭图标；点击时将当前 `content` 作为参数回传给 `onClose`：

```vue
<template>
  <CiteContent
    v-if="showCite"
    content="这是一段可关闭的引用文本"
    :on-close="handleClose"
  />
</template>

<script setup lang="ts">
  import { CiteContent } from '@blueking/chat-x';

  const handleClose = (content: string) => {
    // content 即当前引用文本，可用于日志或状态清除
    console.log('关闭引用:', content);
  };
</script>
```

## 长文本截断

文本超出容器宽度时自动单行截断（`text-overflow: ellipsis`），始终保持 28px 高度不变形：

## 与 ChatInput 配合

`ChatInput` 通过 `v-model:cite` 内置了 `CiteContent`，当 `cite` 有值时自动渲染在输入框顶部（`input-header` slot 位置）；用户点击关闭时，内部调用 `citeModel.value = ''` 清空引用：

```vue
<template>
  <ChatInput
    v-model="inputValue"
    v-model:cite="citeText"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput } from '@blueking/chat-x';

  const inputValue = ref('');
  const citeText = ref('');

  // 用户通过 AiSelection 划词后，将选中文本赋值给 citeText
  // ChatInput 会自动在顶部显示 CiteContent，用户点击关闭时 citeText 自动清空
  function onUserSelectText(selectedText: string) {
    citeText.value = selectedText;
  }
</script>
```

## 与 UserMessage 配合

`UserMessage` 在 `property.extra.cite` 为字符串时，自动在气泡上方渲染 `CiteContent`（不带关闭按钮）：

```typescript
const message = {
  role: 'user',
  content: '这段代码有什么性能问题？',
  property: {
    extra: {
      // 字符串类型 → 渲染 CiteContent（气泡外上方）
      cite: 'for (let i = 0; i < arr.length; i++) {\n  fetch(`/api/${arr[i]}`)\n}',
    },
  },
};
```

## API

### Props

| 属性名  | 类型                        | 必填 | 说明                                                      |
| ------- | --------------------------- | ---- | --------------------------------------------------------- |
| content | `string`                    | ✓    | 引用的文本内容；使用 Vue 文本插值渲染，XSS 安全           |
| onClose | `(content: string) => void` | —    | 关闭回调；传入后右侧显示关闭图标，点击时将 `content` 回传 |

> **XSS 安全**：`content` 通过 `{{ content }}` 文本插值渲染，不会执行 HTML 标签或脚本。

## 样式说明

| 元素                     | 关键样式                                                                                            |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| `.ai-cite-content`       | `height: 28px`，`padding: 0 8px`，`background: #f5f7fa`，hover `#eaebf0`，`margin-bottom: 4px`（为下方内容留出间距） |
| `.ai-cite-content-text`  | `flex: 1`，`white-space: nowrap`，`overflow: hidden`，`text-overflow: ellipsis`，`color: #979ba5`   |
| `CiteIcon` / `CloseIcon` | `14×14px`，`color: #979ba5`；CloseIcon hover 变为 `#4d4f56`                                         |

## 关联组件

- [ChatInput](/components/input/chat-input) — 引用区常见挂载位置
