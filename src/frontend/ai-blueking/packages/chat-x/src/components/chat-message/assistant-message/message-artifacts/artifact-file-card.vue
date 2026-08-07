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
    <!-- 右侧：有异步取链能力或外部 onDownload 时展示下载按钮 -->
    <div
      v-if="showDownload"
      v-tippy="downloadTippy"
      class="ai-artifact-file-card-download"
      :class="{ 'is-loading': downloadLoading }"
      @click.stop="handleDownload"
    >
      <Loading
        v-if="downloadLoading"
        mode="spin"
        size="mini"
        theme="primary"
      />
      <component
        :is="downloadIcon"
        v-else
      />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { cloneVNode, computed, shallowRef } from 'vue';

  import { Loading } from 'bkui-vue';
  import { directive as vTippy } from 'vue-tippy';

  import { triggerArtifactDownload, useArtifactPreviewConsumer } from '../../../../composables/use-artifact-preview';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadFileIcon } from '../../../../icons/file';
  import { t } from '../../../../lang/lang';
  import { getFileIcon } from './file-icon';

  import type { AIFileInfo } from '../../../../ag-ui/types/file';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    // 侧栏列表选中态（variant=list 时使用）
    active?: boolean;
    file: AIFileInfo;
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

  // 未传 onArtifactClick 时隐藏下载；有外部 onDownload 或可异步取链时展示
  const showDownload = computed(() => !!props.onDownload || !!artifactPreview?.canResolveArtifactUrl.value);

  // 图标为共享 VNode，克隆后再渲染，避免同类型多卡复用同一实例
  const fileIcon = computed(() => getFileIcon(props.file.type));
  const downloadIcon = computed(() => cloneVNode(DownloadFileIcon));

  const downloadLoading = shallowRef(false);

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
    artifactPreview?.openPreview({ file: props.file });
  };

  const handleDownload = async () => {
    if (downloadLoading.value) {
      return;
    }
    if (props.onDownload) {
      props.onDownload(props.file);
      return;
    }
    if (!artifactPreview?.canResolveArtifactUrl.value) {
      return;
    }
    downloadLoading.value = true;
    try {
      const { download_url: downloadUrl } = await artifactPreview.resolveArtifactUrls(props.file);
      if (downloadUrl) {
        triggerArtifactDownload(downloadUrl, props.file.name);
      }
    } finally {
      downloadLoading.value = false;
    }
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
      width: 24px;
      height: 24px;
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

      &.is-loading {
        display: inline-flex;
        pointer-events: none;
        cursor: default;
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
