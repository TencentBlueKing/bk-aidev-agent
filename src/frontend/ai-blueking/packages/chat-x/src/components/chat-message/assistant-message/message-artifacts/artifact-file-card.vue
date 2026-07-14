<template>
  <div
    class="ai-artifact-file-card"
    :class="{
      'is-active': active,
      'is-clickable': clickable,
      'is-list': variant === 'list',
    }"
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

  import { useArtifactPreviewConsumer } from '../../../../composables/use-artifact-preview';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadIcon } from '../../../../icons/file';
  import { t } from '../../../../lang/lang';
  import { getFileIcon } from './file-icon';

  import type { AIFileInfo } from '../../../../ag-ui/types/file';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    // 侧栏列表选中态（variant=list 时使用）
    active?: boolean;
    file: AIFileInfo;
    // 文件在所属消息 artifacts 中的下标，用于命中唯一文件（文件名不可靠）
    index?: number;
    // 所属 AssistantMessage 的 uid，用于命中唯一文件与「在对话中定位」
    messageUid?: string;
    // 下载回调，传入时覆盖组件内置的默认下载行为
    onDownload?: (file: AIFileInfo) => void;
    // 点击卡片主体的回调（可选，优先于内置侧栏预览，便于外部自定义 / 测试）
    onPreview?: (file: AIFileInfo) => void;
    // 展示形态：card=消息区卡片（默认），list=侧栏文件列表行
    variant?: 'card' | 'list';
  }>();

  // 文件产物侧栏预览上下文（由 ChatContainer 提供），无 Provider 时为 undefined
  const artifactPreview = useArtifactPreviewConsumer();

  // 有外部 onPreview 或处于可预览的侧栏上下文时，卡片可点击
  const clickable = computed(() => !!props.onPreview || !!artifactPreview);

  // 图标为共享 VNode，克隆后再渲染，避免同类型多卡复用同一实例
  const fileIcon = computed(() => getFileIcon(props.file.type));
  const downloadIcon = computed(() => cloneVNode(DownloadIcon));

  const downloadTippy = computed(() => ({
    content: t('下载'),
    theme: 'ai-chat-box',
    placement: 'top' as const,
  }));

  const handleCardClick = () => {
    if (props.onPreview) {
      props.onPreview(props.file);
      return;
    }
    artifactPreview?.openPreview({
      file: props.file,
      index: props.index ?? 0,
      messageUid: props.messageUid ?? '',
    });
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
  @use '../../../../styles/variables.scss' as variables;

  .ai-artifact-file-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    max-width: 368px;
    height: 42px;
    padding: 0 12px;
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
      // display: inline-flex;
      display: none;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      padding: 4px;
      margin-left: 4px;
      font-size: 16px;
      color: #979ba5;
      cursor: pointer;
      border-radius: 4px;

      &:hover {
        color: #3a84ff;
        background-color: #f0f1f5;
      }

      .ai-artifact-file-card:hover & {
        display: inline-flex;
      }
    }

    // 侧栏文件列表行：去边框/底色，由 hover / 选中态驱动背景
    &.is-list {
      width: 100%;
      height: 32px;
      padding: 0 8px;
      background-color: transparent;
      border: none;
      border-radius: 4px;

      &:hover {
        background-color: variables.$color-bg-hover;
      }

      &.is-active {
        background-color: variables.$color-bg-selected;
        border-radius: 2px;

        .ai-artifact-file-card-name {
          color: variables.$color-primary;
        }
      }
    }
  }
</style>
