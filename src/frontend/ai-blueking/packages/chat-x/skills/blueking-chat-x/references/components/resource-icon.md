# ResourceIcon 资源图标

> 能力域：辅助能力 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 0.0.51

ResourceIcon 统一渲染资源图标：icon 为字符串按 img 加载（加载失败回退内置图标）、 为 Vue 组件直接渲染、缺省时按 type 查内置图标表（artifact 交给 FileIcon 按文件名后缀推导， 未登记类型回退 ModuleIcon）；尺寸由 --ai-icon-size 控制，默认 16px。 源码位置：src/components/resource-icon/resource-icon.vue。

**关联**：input-menu-panel（菜单条目左侧图标）、mention-tag（输入框与消息中的资源标签图标）、model-selector（模型选择器的触发器与选项图标）、file-icon（artifact 类型委托给 FileIcon 按后缀推导）

---

# ResourceIcon 资源图标

> **能力域**：辅助能力

## 源码事实

- **源码位置**：`src/components/resource-icon/resource-icon.vue`
- **内置图标表**：`file` → `FileUploadIcon`、`mcp` → `McpIcon`、`tool` → `ToolIcon`、`knowledgebase` / `doc` → `KnowledgeBaseIcon`
- **特殊分支**：`artifact` 走 [FileIcon](/components/helper/file-icon) 按 `name` 的文件后缀推导
- **最终兜底**：以上都不命中时渲染 `ModuleIcon`（田字格）

## 渲染优先级

```
icon 有值？
├── 字符串 → <img :src="icon">
│             └── onerror → 降级到「按 type 兜底」
└── Vue 组件 → <component :is="icon">
icon 缺省
├── type === 'artifact' → FileIcon（按 name 后缀）
├── type 命中内置图标表 → 对应内置图标
└── 其他 → ModuleIcon
```

`icon` 变化时会重置失效标记，换成新的 URL 会重新尝试加载。

::: info 内部组件
本组件不在包入口导出，由菜单、标签与模型选择器内部使用。内置图标（`McpIcon` / `ToolIcon` / `KnowledgeBaseIcon` / `ModuleIcon` / `FileUploadIcon`）从包入口导出，可单独使用，见 [Icons 图标](/icons/)。
:::

## 用法

```vue
<template>
  <!-- 远程图标 -->
  <ResourceIcon icon="https://example.com/tool.png" name="天气查询" type="tool" />
  <!-- Vue 组件图标 -->
  <ResourceIcon :icon="McpIcon" name="database-server" type="mcp" />
  <!-- 按类型兜底 -->
  <ResourceIcon name="API 接口文档" type="knowledgebase" />
  <!-- 会话产物按后缀推导 -->
  <ResourceIcon name="巡检报告.pdf" type="artifact" />
</template>

<script setup lang="ts">
  import { McpIcon } from '@blueking/chat-x';
</script>
```

**渲染效果**（均未传 `icon`，展示按类型兜底的结果）

## 控制尺寸

容器宽高与 `font-size` 都取 `var(--ai-icon-size, 16px)`，图片以 `object-fit: contain` 填充并带 2px 圆角。需要改尺寸时覆盖该变量，不要直接改 svg：

```vue
<template>
  <span style="--ai-icon-size: 24px">
    <ResourceIcon name="巡检报告.pdf" type="artifact" />
  </span>
</template>
```

## API

### Props

| 属性名 | 类型                    | 必填 | 说明                                                     |
| ------ | ----------------------- | ---- | -------------------------------------------------------- |
| icon   | `Component \| string`   | -    | 图标 URL 或 Vue 组件；缺省时按 `type` 回退               |
| name   | `string`                | ✅   | 资源名称；`type` 为 `artifact` 时据此推导文件类型图标    |
| type   | `string`                | ✅   | 资源类型，决定兜底图标                                   |

### Emits / Slots / Expose

- 无。

## 扩展新类型

新增类型只需在组件内的 `TYPE_FALLBACK_ICONS` 表里补一行，不必往模板加分支。`model` 等未登记的类型会落到 `ModuleIcon`，因此 [ModelSelector](/components/input/model-selector) 在模型没有 `icon` 时不会缺图。

## 关联组件

- [InputMenuPanel](/components/input/input-menu-panel) — 菜单条目图标
- [MentionTag](/components/rendering/mention-tag) — 资源标签图标
- [ModelSelector](/components/input/model-selector) — 模型图标
- [FileIcon](/components/helper/file-icon) — `artifact` 类型的实际渲染者
