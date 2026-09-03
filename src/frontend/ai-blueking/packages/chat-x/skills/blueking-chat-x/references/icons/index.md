# 图标

`@blueking/chat-x` 内置了 74 个 SVG 图标：其中 69 个通过 Vue `h()` 预创建为 VNode 对象，可直接用于模板渲染；

---

# 图标

`@blueking/chat-x` 内置了 74 个 SVG 图标：其中 69 个通过 Vue `h()` 预创建为 VNode 对象，可直接用于模板渲染；`ai.ts` 与 `menu-item.ts` 下的 5 个是 `defineComponent` 组件（需要按实例生成唯一渐变 id 或保留多色品牌配色）。

## 快速开始

```typescript
import { CopyIcon, LikeIcon, ToolIconsMap } from '@blueking/chat-x';
```

图标是模块级预创建的 **VNode 对象**（非组件定义），使用 `<component :is>` 渲染：

```vue
<template>
  <component :is="CopyIcon" />
</template>

<script setup lang="ts">
  import { CopyIcon } from '@blueking/chat-x';
</script>
```

颜色通过父元素 `color` 继承（`fill: currentColor`），大小通过 `width` / `height` 控制：

```vue
<template>
  <div style="color: #3a84ff;">
    <component
      :is="CopyIcon"
      style="width: 24px; height: 24px;"
    />
  </div>
</template>
```

## 图标预览

## 图标参考

### 工具图标 `tools.ts`

用于 `MessageTools` 工具栏。`ToolIconsMap` 提供 id → VNode 的映射，`ToolIcons` 为其 key 类型。

| 导出名             | ToolIconsMap key | class                    | 说明             |
| ------------------ | ---------------- | ------------------------ | ---------------- |
| `CopyIcon`         | `copy`           | `ai-copy-icon`           | 复制             |
| `CiteIcon`         | `cite`           | `ai-cite-icon`           | 引用             |
| `RebuildIcon`      | `rebuild`        | `ai-rebuild-icon`        | 重新生成         |
| `ShareIcon`        | `share`          | `ai-share-icon`          | 分享             |
| `LikeIcon`         | `like`           | `ai-like-icon`           | 点赞（默认态）   |
| `UnLikeIcon`       | `unlike`         | `ai-un-like-icon`        | 不满意（默认态） |
| `DeleteIcon`       | `delete`         | `ai-delete-icon`         | 删除             |
| `EditIcon`         | `edit`           | `ai-edit-icon`           | 编辑             |
| `ActiveLikeIcon`   | `activeLike`     | `ai-active-like-icon`    | 点赞（激活态）   |
| `ActiveUnLikeIcon` | `activeUnLike`   | `ai-active-un-like-icon` | 不满意（激活态） |
| `CollapsedAsideIcon` | —              | `ai-collapsed-icon`      | 侧栏展开/收起入口（不在 `ToolIconsMap`；业务方自建折叠按钮时可用） |

```typescript
import { ToolIconsMap, type ToolIcons } from '@blueking/chat-x';

// 通过 key 动态获取图标
const icon = ToolIconsMap['copy']; // CopyIcon VNode

// 类型：'copy' | 'cite' | 'rebuild' | 'share' | 'like' | 'unlike' | 'delete' | 'edit' | 'activeLike' | 'activeUnLike'
type Key = ToolIcons;
```

### 消息图标 `messages.ts`

| 导出名               | class                     | 说明       |
| -------------------- | ------------------------- | ---------- |
| `SendMessageIcon`    | `ai-send-message-icon`    | 发送按钮   |
| `LoadingMessageIcon` | `ai-loading-message-icon` | 加载中环形 |
| `ThinkingIcon`       | `ai-thinking-icon`        | 思考中     |
| `CollapsedIcon`      | `ai-collapsed-icon`       | 折叠箭头   |
| `ErrorIcon`          | `ai-error-icon`           | 错误感叹号 |
| `ContentLoadingIcon` | `ai-content-loading-icon` | 内容加载中 |
| `ArrowDownIcon`      | `ai-arrow-down-icon`      | 返回底部   |

### 内容图标 `content.ts`

| 导出名           | class                 | viewBox         | 颜色             | 说明         |
| ---------------- | --------------------- | --------------- | ---------------- | ------------ |
| `DocumentIcon`   | `ai-document-icon`    | `0 0 1024 1024` | 硬编码           | 文档         |
| `PreviewIcon`    | `ai-preview-icon`     | `0 0 1024 1024` | currentColor     | 预览（眼睛） |
| `TargetIcon`     | `ai-target-icon`      | `0 0 64 64`     | currentColor     | 外链跳转     |
| `RemoveIcon`     | `ai-remove-icon`      | `0 0 64 64`     | 硬编码 `#737987` | 圆形关闭     |
| `ArrowRightIcon` | `ai-arrow-right-icon` | `0 0 1024 1024` | currentColor     | 右箭头       |
| `LinkIcon`       | `ai-link-icon`        | `0 0 1024 1024` | currentColor     | 链接         |
| `ImageErrorIcon` | `ai-image-error-icon` | `0 0 24 18`     | currentColor     | 图片加载失败 |

### 快捷指令图标 `shortcuts.ts`

| 导出名          | class                | 说明            |
| --------------- | -------------------- | --------------- |
| `CloseIcon`     | `ai-close-icon`      | 关闭 ✕          |
| `MoreIcon`      | `ai-more-icon`       | 更多（竖三点）  |
| `AgentIcon`     | `ai-agent-icon`      | 星形 Agent      |
| `MoreAgentIcon` | `ai-more-agent-icon` | 四格 Agent 列表 |

### AI 图标 `ai.ts`

| 导出名                 | class                     | viewBox      | 颜色       | 说明            |
| ---------------------- | ------------------------- | ------------ | ---------- | --------------- |
| `AIBluekingIcon`       | `ai-blueking-icon`        | `0 0 24 24`  | 硬编码渐变 | 小鲸品牌图标    |
| `AIBluekingBannerIcon` | `ai-blueking-banner-icon` | `0 0 309 93` | 硬编码渐变 | 小鲸品牌 Banner |

### 文件图标 `file.ts`

| 导出名             | class                       | viewBox         | 颜色         | 说明                 |
| ------------------ | --------------------------- | --------------- | ------------ | -------------------- |
| `ArtifactTabIcon`  | `ai-file-artifact-tab-icon` | `0 0 16 16`     | currentColor | 文件产物侧栏 Tab     |
| `DownloadFileIcon` | `ai-file-download-icon`     | `0 0 1024 1024` | currentColor | 文件下载             |

### 输入区图标 `input.ts`

| 导出名             | class                   | 说明     |
| ------------------ | ----------------------- | -------- |
| `CloseCircleIcon`  | `ai-close-circle-icon`  | 圆形关闭 |
| `DocLinkIcon`      | `ai-doc-link-icon`      | 文档链接 |
| `DeleteCircleIcon` | `ai-delete-circle-icon` | 圆形删除 |
| `FileUploadIcon`   | `ai-delete-circle-icon` | 文件上传（与上一项共用 class，源码如此） |
| `AddIcon`          | `ai-add-icon`           | 加号，[AddMenuBtn](/components/input/add-menu-btn) 唤起聚合菜单 |
| `ModuleIcon`       | `ai-module-icon`        | 田字格，菜单条目未提供图标时的最终兜底 |

### 菜单条目图标 `menu-item.ts`

菜单与资源标签的类型默认图标，由 [ResourceIcon](/components/helper/resource-icon) 按 `type` 选用。与其余图标不同，这三个是**设计给定的多色品牌图标**：

- 以 `defineComponent` 导出（不是 VNode），模板中直接 `<McpIcon />` 使用
- **不套用** `fill: currentColor`，各自配色原样保留，用 `color` 无法改色
- 尺寸统一 `1em`，跟随外层 `font-size`
- `McpIcon` 含两组 `linearGradient` 与一个 `clipPath`，每个实例用 `useId()` 生成独立 id 前缀，避免多实例共用 id 时渐变失效

| 导出名              | class                      | 说明   |
| ------------------- | -------------------------- | ------ |
| `ToolIcon`          | `ai-tool-icon`             | 工具   |
| `KnowledgeBaseIcon` | `ai-knowledge-base-icon`   | 知识库 |
| `McpIcon`           | `ai-mcp-icon`              | MCP    |

### 执行图标 `execution.ts`

用于流程编排 / Agent 执行状态与工具调用展示。

| 导出名                | class                       | viewBox         | 颜色                  | 说明     |
| --------------------- | --------------------------- | --------------- | --------------------- | -------- |
| `BkFlowSuccessIcon`   | `ai-bk-flow-success-icon`   | `0 0 16 16`     | 硬编码 `#18B456` + 白 | 流程成功 |
| `BkFlowFailedIcon`    | `ai-bk-flow-failed-icon`    | `0 0 16 16`     | 硬编码 `#EA3636` + 白 | 流程失败 |
| `BkFlowSuspendedIcon` | `ai-bk-flow-suspended-icon` | `0 0 16 16`     | 硬编码 `#F59500` + 白 | 流程暂停 |
| `ExecutionIcon`       | `ai-execution-icon`         | `0 0 1024 1024` | currentColor          | 执行时钟 |
| `NodeOutputIcon`      | `ai-node-output-icon`       | `0 0 1024 1024` | currentColor          | 节点输出 |
| `NodeTabIcon`         | `ai-node-tab-icon`          | `0 0 1024 1024` | currentColor          | 节点 Tab |
| `ToolCallIcon`        | `ai-toolcall-icon`          | `0 0 16 16`     | currentColor          | 工具调用（ToolcallRender 头部，16×16） |
| `ChevronRightIcon`    | `ai-chevron-right-icon`     | `0 0 10 10`     | currentColor          | 折叠箭头（10×10，展开态 rotate 90deg） |

### 图片预览图标 `image-preview.ts`

| 导出名                  | class                         | 说明             |
| ----------------------- | ----------------------------- | ---------------- |
| `ZoomInIcon`            | `ai-zoom-in-icon`             | 放大             |
| `ZoomOutIcon`           | `ai-zoom-out-icon`            | 缩小             |
| `RotateIcon`            | `ai-rotate-icon`              | 旋转             |
| `FitScreenIcon`         | `ai-fit-screen-icon`          | 适应屏幕         |
| `DownloadIcon`          | `ai-download-icon`            | 下载             |
| `PreviewCloseIcon`      | `ai-close-icon`               | 关闭预览         |
| `ArrowLeftIcon`         | `ai-arrow-left-icon`          | 上一张           |
| `ArrowRightPreviewIcon` | `ai-arrow-right-preview-icon` | 下一张           |
| `ReloadIcon`            | `ai-reload-icon`              | 重新加载         |
| `ImageBrokenIcon`       | `ai-image-broken-icon`        | 图片加载失败占位 |
| `ImageSizeIcon`         | `ai-image-size-icon`          | 图片尺寸         |

## 注意事项

1. **VNode 而非组件**：图标是 `h()` 预创建的 VNode 实例，同一个 VNode 不能被多处挂载。在列表渲染中使用 `cloneVNode()` 创建副本，或用 `defineComponent` 包装
2. **硬编码颜色**：`DocumentIcon`、`RemoveIcon`（`#737987`）、`AIBluekingIcon` / `AIBluekingBannerIcon`（渐变）、`ImageBrokenIcon`、`BkFlowSuccessIcon`（`#18B456`）、`BkFlowFailedIcon`（`#EA3636`）、`BkFlowSuspendedIcon`（`#F59500`）内部使用固定颜色，不响应父元素 `color` 继承
3. **非标准 viewBox**：`TargetIcon` / `RemoveIcon` 为 `0 0 64 64`，`ImageErrorIcon` 为 `0 0 24 18`，`AIBluekingIcon` 为 `0 0 24 24`，`AIBluekingBannerIcon` 为 `0 0 309 93`，`ImageBrokenIcon` 为 `0 0 200 180`，`BkFlowSuccessIcon` / `BkFlowFailedIcon` / `BkFlowSuspendedIcon` / `ArtifactTabIcon` / `ToolCallIcon` 为 `0 0 16 16`，`ChevronRightIcon` 为 `0 0 10 10`，设置 `width` / `height` 时注意比例
4. **`FileUploadIcon` 类名**：源码中 class 为 `ai-delete-circle-icon`（与 `DeleteCircleIcon` 相同），通过 CSS 定位时需注意
