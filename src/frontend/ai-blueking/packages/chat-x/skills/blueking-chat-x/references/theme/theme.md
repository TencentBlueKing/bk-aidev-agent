# 主题配置

> since 1.0.0

说明通过 SCSS 变量（尺寸、颜色、z-index）、字号主题 CSS 变量（data-ai-size 切换 small/normal）与 CSS 类覆盖自定义主题。 ChatContainer.size 控制根节点 data-ai-size；浮层同步 document.body.dataset.aiSize。含渐变边框 mixin、骨架屏类 ai-skeleton-element 等。

**关联**：chat-container（整体布局与侧栏）、chat-input（输入区与渐变边框）、message-container（消息区样式上下文）

---

# 主题配置

> **分类**：theme

`@blueking/chat-x` 使用 SCSS 变量和 CSS 类来控制样式，支持通过覆盖变量或样式来自定义主题。

## 样式引入

组件库的样式会在引入组件时自动加载，无需单独引入：

```typescript
// 引入组件时会自动引入样式
import { ChatInput, MessageContainer } from '@blueking/chat-x';
```

## 字号主题

组件库通过根节点 `[data-ai-size]` 切换两档字号主题，内部组件统一引用 CSS 变量（均带兜底值，无 provider 时退回 `small`）。

### 切换方式

| 方式 | 说明 |
| ---- | ---- |
| `ChatContainer` 的 `size` prop | 推荐。根节点 `.ai-chat-container` 设置 `data-ai-size`；同时通过 `useGlobalConfig` 注入 `size` 供逻辑层读取 |
| 手动设置 `data-ai-size` | 在任意祖先元素上设置 `data-ai-size="small"` 或 `data-ai-size="normal"`，后代继承 CSS 变量 |
| `document.body.dataset.aiSize` | `ChatContainer` 会自动同步，供 Tippy / Teleport 等挂载到 `body` 的浮层继承字号变量；容器卸载时清理 |

```vue
<template>
  <ChatContainer v-model="input" :messages="messages" size="normal" />
</template>
```

### CSS 变量

定义于 `src/styles/size-theme.scss`，随 `global.scss` 自动引入：

| 变量名 | `small`（默认） | `normal` | 说明 |
| ------ | --------------- | -------- | ---- |
| `--ai-font-size` | `12px` | `14px` | 基准字号 |
| `--ai-line-height` | `20px` | `24px` | 标准行高 |
| `--ai-line-height-compact` | `20px` | `22px` | 紧凑行高 |
| `--ai-spacing-comfortable` | `8px` | `12px` | 舒适间距（如消息气泡水平内边距） |
| `--ai-icon-size` | `16px` | `20px` | 标准图标尺寸 |
| `--ai-icon-size-sm` | `16px` | `18px` | 小号图标尺寸 |

组件样式中统一使用 `var(--ai-font-size, 12px)` 等形式引用，保证无 `data-ai-size` 时仍退回 small 档位。

```scss
// 示例：在自定义样式中复用字号主题变量
.my-custom-panel {
  font-size: var(--ai-font-size, 12px);
  line-height: var(--ai-line-height, 20px);
}
```

### 骨架屏

全局类 `.ai-skeleton-element` 用于加载占位（如 FlowAgent 节点详情、UserFeedback 原因列表）。可通过 `.skeleton-element-lg` 修饰尺寸。详见各业务组件文档中的加载态说明。

## SCSS 变量

组件库在 `src/styles/variables.scss` 中定义了以下 SCSS 变量（构建期生效，仅供库内组件 `@use` 复用；消费方无法在运行时覆盖，需要改色请用 CSS 变量或类名覆盖）：

### 尺寸变量

```scss
// 输入框宽度（.chat-input-wrapper）
$chat-input-min-width: 168px;
$chat-input-max-width: 1000px;
```

### 语义色变量

```scss
$color-title: #313238; // 标题 / 主文字
$color-text: #4d4f56; // 常规文字
$color-text-secondary: #979ba5; // 次要文字 / 占位
$color-primary: #3a84ff; // 主题色
$color-border: #dcdee5; // 边框
$color-border-light: #eaebf0; // 浅边框 / 线条中
$color-bg-light: #fafbfd; // 浅背景
$color-bg-tab: #f0f1f5; // 分段控件 / tab 背景
$color-bg-hover: #f5f7fa; // 列表 / 卡片 hover 背景
$color-bg-selected: #e1ecff; // 选中态背景（背景蓝）
$content-loading-icon-color-list: (#cddffe, #699df4, #1768ef); // 内容加载动画三色
```

> 旧版用于 `@` 资源标签配色的 `$resourceTypeMap`（tool / skill / shortcut / doc / knowledgebase / mcp 六组配色）随输入区重构一并移除——现在资源标签统一为「图标 + 主题蓝文字」，不再按类型分配底色，详见 [MentionTag](/components/rendering/mention-tag)。

> 其余色值（如 hover 边框 `#c4c6cc`）目前直接写在各组件样式中，未抽为变量。

### Z-Index 分层

层级由 TS 常量维护（`src/common/constants.ts`），从包入口导出，组件通过 inline style 写成 CSS 变量下发：

```typescript
import { CHAT_Z_INDEX, EDITOR_MENU_Z_INDEX, SELECTION_Z_INDEX } from '@blueking/chat-x';

CHAT_Z_INDEX; //           9999  对话主层
EDITOR_Z_INDEX; //         10000 编辑器
EDITOR_MENU_Z_INDEX; //    10001 编辑器菜单 / 资源标签气泡
SHORTCUT_MENU_Z_INDEX; //  10002 快捷指令菜单
SELECTION_Z_INDEX; //      10003 划词浮窗
```

## CSS 类覆盖

### 输入框样式

```scss
// 覆盖输入框容器样式
.ai-chat-input-container {
  .chat-input {
    min-height: 120px; // 自定义最小高度
    max-height: 250px; // 自定义最大高度
    background: #fafafa; // 自定义背景色

    // 覆盖边框渐变
    &::before {
      background: linear-gradient(180deg, #ff6b6b, #ff8e53);
    }
  }
}
```

### 消息样式

```scss
// 用户消息样式
.ai-user-message {
  &-content {
    background-color: #d4edda; // 自定义背景色
    border-radius: 8px;
  }
}

// AI 消息样式
.assistant-message {
  &-content {
    background-color: #f8f9fa;
    border-left: 3px solid #3a84ff;
    padding-left: 12px;
  }
}
```

### 快捷指令按钮样式

```scss
// 快捷指令按钮
.ai-shortcut-btns {
  &-item {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    // 移除默认渐变边框
    &::before {
      display: none;
    }
  }
}
```

### 消息工具栏样式

```scss
// 工具按钮
.tool-btn {
  width: 24px;
  height: 24px;
  font-size: 16px;

  &:hover {
    background-color: #e1ecff;
    color: #3a84ff;
  }
}
```

### Markdown 内容样式

```scss
// Markdown 内容
.ai-markdown-content {
  .ai-markdown-body {
    font-size: 14px;
    line-height: 1.6;

    // 代码块样式
    pre code.hljs {
      background-color: #1e1e1e;
      border-radius: 8px;
    }

    // 表格样式
    table {
      border-collapse: collapse;

      th,
      td {
        border: 1px solid #dcdee5;
        padding: 8px 12px;
      }

      th {
        background-color: #f5f7fa;
      }
    }
  }
}
```

## 主题切换示例

### 暗色主题

```scss
// 暗色主题变量
.dark-theme {
  // 输入框
  .ai-chat-input-container .chat-input {
    background: #2d2d2d;

    &::before {
      background: linear-gradient(180deg, #4a90d9, #357abd);
    }
  }

  // 用户消息
  .ai-user-message-content {
    background-color: #3d5a80;
    color: #fff;
  }

  // AI 消息
  .assistant-message {
    color: #e0e0e0;
  }

  // Markdown 内容
  .ai-markdown-content .ai-markdown-body {
    color: #e0e0e0;

    h1,
    h2,
    h3,
    h4,
    h5,
    h6 {
      color: #fff;
    }

    a {
      color: #6cb2eb;
    }

    code {
      background-color: #3d3d3d;
      color: #e0e0e0;
    }
  }

  // 快捷指令
  .ai-shortcut-btns-item {
    background: #3d3d3d;
    color: #e0e0e0;

    &::before {
      background: linear-gradient(105deg, #4a90d940, #9b59b640);
    }
  }

  // 工具按钮
  .tool-btn {
    color: #9e9e9e;

    &:hover {
      background-color: #424242;
      color: #fff;
    }
  }
}
```

### 使用暗色主题

```vue
<template>
  <div :class="{ 'dark-theme': isDark }">
    <ChatInput v-model="input" />
    <MessageContainer :messages="messages" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageContainer } from '@blueking/chat-x';

  const isDark = ref(false);
  const input = ref('');
  const messages = ref([]);
</script>
```

## 渐变边框

组件库使用 CSS mask 实现渐变边框效果：

```scss
// 渐变边框 mixin
@mixin linear-gradient-border($angle: 105deg, $start-color: #235dfa40, $end-color: #bc81ef40) {
  content: '';
  position: absolute;
  inset: 0;
  padding: 1px;
  background: linear-gradient($angle, $start-color, $end-color);
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: xor;
  mask-composite: exclude;
  border-radius: inherit;
  pointer-events: none;
}
```

使用示例：

```scss
.custom-card {
  position: relative;
  border-radius: 8px;

  &::before {
    @include linear-gradient-border(180deg, #6cbaff, #3a84ff);
  }
}
```

## 动画效果

### 淡入动画

```scss
// 全局淡入动画
@keyframes ai-markdown-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.ai-blueking-markdown-fade-in {
  animation: ai-markdown-fade-in 0.2s ease-out forwards;
}
```

### 弹窗过渡

```scss
// 选择弹窗过渡
.ai-fade-enter-active,
.ai-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.ai-fade-enter-from,
.ai-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
```

## 响应式设计

```scss
// 移动端适配
@media (max-width: 768px) {
  .ai-chat-input-container .chat-input {
    min-width: 100%;
    max-width: 100%;
  }

  .ai-shortcut-btns {
    min-width: 100%;
    max-width: 100%;
  }
}
```

## 注意事项

1. **样式优先级**：覆盖样式时可能需要使用更高优先级的选择器
2. **变量位置**：SCSS 变量需要在组件样式之前定义
3. **构建配置**：确保项目配置支持 SCSS 处理
4. **组件隔离**：使用 scoped 样式时，深度选择器 `::v-deep` 或 `:deep()` 可能需要

## 关联组件

- [ChatContainer](../components/setup/chat-container) — 布局与字号主题根节点（`size` prop）
- [useGlobalConfig](../composables/use-global-config) — 注入 `size` 供后代读取
- [ChatInput](../components/input/chat-input) — 输入区变量与类名
- [MessageContainer](../components/setup/message-container) — 消息列表区域
