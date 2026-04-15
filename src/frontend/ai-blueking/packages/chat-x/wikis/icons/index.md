# 图标

`@blueking/chat-x` 内置了 51 个 SVG 图标，通过 Vue `h()` 函数预创建为 VNode 对象，可直接用于模板渲染。

<script setup lang="ts">
import { ref, defineComponent, cloneVNode } from 'vue';
import {
  CopyIcon, CiteIcon, RebuildIcon, ShareIcon, LikeIcon, UnLikeIcon,
  DeleteIcon, EditIcon, ActiveLikeIcon, ActiveUnLikeIcon,
  SendMessageIcon, LoadingMessageIcon, ThinkingIcon, CollapsedIcon,
  ErrorIcon, ContentLoadingIcon, ArrowDownIcon,
  DocumentIcon, PreviewIcon, TargetIcon, RemoveIcon,
  ArrowRightIcon, LinkIcon, ImageErrorIcon,
  CloseIcon, MoreIcon, AgentIcon, MoreAgentIcon,
  AIBluekingIcon, AIBluekingBannerIcon,
  CloseCircleIcon, DocLinkIcon, DeleteCircleIcon, FileUploadIcon,
  ZoomInIcon, ZoomOutIcon, RotateIcon, FitScreenIcon, DownloadIcon,
  PreviewCloseIcon, ArrowLeftIcon, ArrowRightPreviewIcon, ReloadIcon,
  ImageBrokenIcon, ImageSizeIcon,
  BkFlowSuccessIcon, BkFlowFailedIcon, BkFlowSuspendedIcon,
  ExecutionIcon, NodeOutputIcon, NodeTabIcon,
} from '@blueking/chat-x';

const iconColor = ref('#63656e');
const iconSize = ref(24);
const copiedName = ref('');

const w = (vnode: any) => defineComponent({
  render() {
    return cloneVNode(vnode);
  },
});

const copyName = async (name: string) => {
  try {
    await navigator.clipboard.writeText(name);
    copiedName.value = name;
    setTimeout(() => { copiedName.value = ''; }, 1500);
  } catch {
    copiedName.value = '';
  }
};

const groups = [
  {
    title: '工具图标',
    source: 'tools.ts',
    items: [
      { name: 'CopyIcon', icon: w(CopyIcon) },
      { name: 'CiteIcon', icon: w(CiteIcon) },
      { name: 'RebuildIcon', icon: w(RebuildIcon) },
      { name: 'ShareIcon', icon: w(ShareIcon) },
      { name: 'LikeIcon', icon: w(LikeIcon) },
      { name: 'UnLikeIcon', icon: w(UnLikeIcon) },
      { name: 'DeleteIcon', icon: w(DeleteIcon) },
      { name: 'EditIcon', icon: w(EditIcon) },
      { name: 'ActiveLikeIcon', icon: w(ActiveLikeIcon) },
      { name: 'ActiveUnLikeIcon', icon: w(ActiveUnLikeIcon) },
    ],
  },
  {
    title: '消息图标',
    source: 'messages.ts',
    items: [
      { name: 'SendMessageIcon', icon: w(SendMessageIcon) },
      { name: 'LoadingMessageIcon', icon: w(LoadingMessageIcon) },
      { name: 'ThinkingIcon', icon: w(ThinkingIcon) },
      { name: 'CollapsedIcon', icon: w(CollapsedIcon) },
      { name: 'ErrorIcon', icon: w(ErrorIcon) },
      { name: 'ContentLoadingIcon', icon: w(ContentLoadingIcon) },
      { name: 'ArrowDownIcon', icon: w(ArrowDownIcon) },
    ],
  },
  {
    title: '内容图标',
    source: 'content.ts',
    items: [
      { name: 'DocumentIcon', icon: w(DocumentIcon), fixed: true },
      { name: 'PreviewIcon', icon: w(PreviewIcon) },
      { name: 'TargetIcon', icon: w(TargetIcon) },
      { name: 'RemoveIcon', icon: w(RemoveIcon), fixed: true },
      { name: 'ArrowRightIcon', icon: w(ArrowRightIcon) },
      { name: 'LinkIcon', icon: w(LinkIcon) },
      { name: 'ImageErrorIcon', icon: w(ImageErrorIcon) },
    ],
  },
  {
    title: '快捷指令图标',
    source: 'shortcuts.ts',
    items: [
      { name: 'CloseIcon', icon: w(CloseIcon) },
      { name: 'MoreIcon', icon: w(MoreIcon) },
      { name: 'AgentIcon', icon: w(AgentIcon) },
      { name: 'MoreAgentIcon', icon: w(MoreAgentIcon) },
    ],
  },
  {
    title: 'AI 图标',
    source: 'ai.ts',
    items: [
      { name: 'AIBluekingIcon', icon: w(AIBluekingIcon), fixed: true },
      { name: 'AIBluekingBannerIcon', icon: w(AIBluekingBannerIcon), fixed: true },
    ],
  },
  {
    title: '输入区图标',
    source: 'input.ts',
    items: [
      { name: 'CloseCircleIcon', icon: w(CloseCircleIcon) },
      { name: 'DocLinkIcon', icon: w(DocLinkIcon) },
      { name: 'DeleteCircleIcon', icon: w(DeleteCircleIcon) },
      { name: 'FileUploadIcon', icon: w(FileUploadIcon) },
    ],
  },
  {
    title: '图片预览图标',
    source: 'image-preview.ts',
    items: [
      { name: 'ZoomInIcon', icon: w(ZoomInIcon) },
      { name: 'ZoomOutIcon', icon: w(ZoomOutIcon) },
      { name: 'RotateIcon', icon: w(RotateIcon) },
      { name: 'FitScreenIcon', icon: w(FitScreenIcon) },
      { name: 'DownloadIcon', icon: w(DownloadIcon) },
      { name: 'PreviewCloseIcon', icon: w(PreviewCloseIcon) },
      { name: 'ArrowLeftIcon', icon: w(ArrowLeftIcon) },
      { name: 'ArrowRightPreviewIcon', icon: w(ArrowRightPreviewIcon) },
      { name: 'ReloadIcon', icon: w(ReloadIcon) },
      { name: 'ImageBrokenIcon', icon: w(ImageBrokenIcon), fixed: true },
      { name: 'ImageSizeIcon', icon: w(ImageSizeIcon) },
    ],
  },
  {
    title: '执行图标',
    source: 'execution.ts',
    items: [
      { name: 'BkFlowSuccessIcon', icon: w(BkFlowSuccessIcon), fixed: true },
      { name: 'BkFlowFailedIcon', icon: w(BkFlowFailedIcon), fixed: true },
      { name: 'BkFlowSuspendedIcon', icon: w(BkFlowSuspendedIcon), fixed: true },
      { name: 'ExecutionIcon', icon: w(ExecutionIcon) },
      { name: 'NodeOutputIcon', icon: w(NodeOutputIcon) },
      { name: 'NodeTabIcon', icon: w(NodeTabIcon) },
    ],
  },
];
</script>

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

<div class="demo">
  <div style="padding: 16px; display: flex; flex-direction: column; gap: 16px;">
    <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
      <label style="display: flex; align-items: center; gap: 6px; font-size: 13px;">
        颜色
        <input type="color" v-model="iconColor" style="width: 32px; height: 24px; border: none; cursor: pointer;" />
        <code style="padding: 2px 6px; background: #f0f1f5; border-radius: 3px;">{{ iconColor }}</code>
      </label>
      <label style="display: flex; align-items: center; gap: 6px; font-size: 13px;">
        大小
        <input type="range" v-model.number="iconSize" min="12" max="48" style="width: 100px;" />
        <code style="padding: 2px 6px; background: #f0f1f5; border-radius: 3px;">{{ iconSize }}px</code>
      </label>
    </div>
    <div style="font-size: 12px; color: #979ba5;">
      点击图标名称可复制 · 带 <b>*</b> 标记的图标内部有硬编码颜色，不受颜色选择器影响
    </div>
    <template v-for="group in groups" :key="group.source">
      <div style="font-weight: 600; font-size: 13px; color: #313238; border-bottom: 1px solid #dcdee5; padding-bottom: 6px;">
        {{ group.title }} / {{ group.source }}
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 8px;">
        <div
          v-for="item in group.items"
          :key="item.name"
          style="display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 12px 10px; background: #f5f7fa; border-radius: 6px; min-width: 100px; cursor: pointer; transition: background 0.2s;"
          :style="{ color: iconColor }"
          @click="copyName(item.name)"
        >
          <component :is="item.icon" :style="{ width: iconSize + 'px', height: iconSize + 'px' }" />
          <span style="font-size: 11px; color: #63656e; text-align: center;">
            {{ item.name }}<template v-if="item.fixed"> *</template>
            <span v-if="copiedName === item.name" style="color: #2dcb56; margin-left: 4px;">✓</span>
          </span>
        </div>
      </div>
    </template>
  </div>
</div>

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

### 输入区图标 `input.ts`

| 导出名             | class                   | 说明     |
| ------------------ | ----------------------- | -------- |
| `CloseCircleIcon`  | `ai-close-circle-icon`  | 圆形关闭 |
| `DocLinkIcon`      | `ai-doc-link-icon`      | 文档链接 |
| `DeleteCircleIcon` | `ai-delete-circle-icon` | 圆形删除 |
| `FileUploadIcon`   | `ai-delete-circle-icon` | 文件上传 |

### 执行图标 `execution.ts`

用于流程编排 / Agent 执行状态展示。

| 导出名                | class                       | viewBox         | 颜色                  | 说明     |
| --------------------- | --------------------------- | --------------- | --------------------- | -------- |
| `BkFlowSuccessIcon`   | `ai-bk-flow-success-icon`   | `0 0 16 16`     | 硬编码 `#18B456` + 白 | 流程成功 |
| `BkFlowFailedIcon`    | `ai-bk-flow-failed-icon`    | `0 0 16 16`     | 硬编码 `#EA3636` + 白 | 流程失败 |
| `BkFlowSuspendedIcon` | `ai-bk-flow-suspended-icon` | `0 0 16 16`     | 硬编码 `#F59500` + 白 | 流程暂停 |
| `ExecutionIcon`       | `ai-execution-icon`         | `0 0 1024 1024` | currentColor          | 执行时钟 |
| `NodeOutputIcon`      | `ai-node-output-icon`       | `0 0 1024 1024` | currentColor          | 节点输出 |
| `NodeTabIcon`         | `ai-node-tab-icon`          | `0 0 1024 1024` | currentColor          | 节点 Tab |

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
3. **非标准 viewBox**：`TargetIcon` / `RemoveIcon` 为 `0 0 64 64`，`ImageErrorIcon` 为 `0 0 24 18`，`AIBluekingIcon` 为 `0 0 24 24`，`AIBluekingBannerIcon` 为 `0 0 309 93`，`ImageBrokenIcon` 为 `0 0 200 180`，`BkFlowSuccessIcon` / `BkFlowFailedIcon` / `BkFlowSuspendedIcon` 为 `0 0 16 16`，设置 `width` / `height` 时注意比例
4. **`FileUploadIcon` 类名**：源码中 class 为 `ai-delete-circle-icon`（与 `DeleteCircleIcon` 相同），通过 CSS 定位时需注意
