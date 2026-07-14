<template>
  <div
    class="ai-artifact-file-card"
    :class="{ 'is-clickable': !!onPreview }"
    @click="handleCardClick"
  >
    <!-- 左侧：文件类型图标 + 文件名 -->
    <div class="ai-artifact-file-card-info">
      <span class="ai-artifact-file-card-icon">
        <component :is="fileIcon" />
      </span>
      <span
        v-overflow-tips="{
          text: file.name,
          placement: 'top' as const,
        }"
        class="ai-artifact-file-card-name"
      >
        {{ file.name }}
      </span>
    </div>
    <!-- 右侧：下载按钮（有下载地址时才展示） -->
    <div
      v-if="file.url"
      v-tippy="downloadTippy"
      class="ai-artifact-file-card-download"
      @click.stop="handleDownload"
    >
      <component :is="downloadIcon" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { cloneVNode, computed } from 'vue';

  import { directive as vTippy } from 'vue-tippy';

  import { AIFileType } from '../../../../ag-ui/types/file';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadIcon, HtmlIcon, JpgIcon, JsonIcon, MarkdownIcon, PdfIcon, TxtIcon } from '../../../../icons/file';
  import { t } from '../../../../lang/lang';

  import type { AIFileInfo } from '../../../../ag-ui/types/file';

  import 'tippy.js/dist/tippy.css';

  // 文件类型 → 图标映射；未命中类型兜底用文本图标
  const FILE_ICON_MAP = {
    [AIFileType.Html]: HtmlIcon,
    [AIFileType.Jpg]: JpgIcon,
    [AIFileType.Json]: JsonIcon,
    [AIFileType.Markdown]: MarkdownIcon,
    [AIFileType.Pdf]: PdfIcon,
    [AIFileType.Txt]: TxtIcon,
  } as const;

  const props = defineProps<{
    file: AIFileInfo;
    // 下载回调，传入时覆盖组件内置的默认下载行为
    onDownload?: (file: AIFileInfo) => void;
    // 点击卡片主体的回调（预览交互后续实现，当前仅透传）
    onPreview?: (file: AIFileInfo) => void;
  }>();

  // 图标为共享 VNode，克隆后再渲染，避免同类型多卡复用同一实例
  const fileIcon = computed(() => cloneVNode(FILE_ICON_MAP[props.file.type] ?? TxtIcon));
  const downloadIcon = computed(() => cloneVNode(DownloadIcon));

  const downloadTippy = computed(() => ({
    content: t('下载'),
    theme: 'ai-chat-box',
    placement: 'top' as const,
  }));

  const handleCardClick = () => {
    props.onPreview?.(props.file);
  };

  const handleDownload = () => {
    if (props.onDownload) {
      props.onDownload(props.file);
      return;
    }
    // 默认下载：使用 url 字段，通过临时 <a> 触发浏览器下载
    const link = document.createElement('a');
    link.href = props.file.url;
    link.download = props.file.name;
    link.target = '_blank';
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
</script>
<style lang="scss">
  .ai-artifact-file-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 368px;
    padding: 10px 12px;
    cursor: pointer;
    background-color: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 4px;

    &.is-clickable {
      cursor: pointer;
    }

    &:hover {
      background-color: #f5f7fa;
    }

    &-info {
      display: flex;
      flex: 1;
      gap: 8px;
      align-items: center;
      min-width: 0;
    }

    &-icon {
      display: inline-flex;
      flex-shrink: 0;
      font-size: 16px;
    }

    &-name {
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height, 20px);
      color: #4d4f56;
      white-space: nowrap;
    }

    &-download {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      padding: 4px;
      margin-left: 4px;
      font-size: 16px;
      cursor: pointer;
      border-radius: 4px;

      &:hover {
        background-color: #f0f1f5;
      }
    }
  }
</style>
