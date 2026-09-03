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
      <FileIcon
        class="ai-artifact-file-card-icon"
        :file-name="file.name"
        :file-type="file.type"
      />
      <span
        v-overflow-tips="{
          ...commonTippyOptions,
          text: file.name,
          placement: 'top' as const,
        }"
        class="ai-artifact-file-card-name"
      >
        {{ file.name }}
      </span>
    </div>
    <!-- 右侧操作区：hover 显示，设计稿中引用在下载左侧 -->
    <div class="ai-artifact-file-card-actions">
      <div
        v-if="inputMention"
        v-tippy="citeTippy"
        class="ai-artifact-file-card-action ai-artifact-file-card-cite"
        @click.stop="handleCite"
      >
        <component :is="citeIcon" />
      </div>
      <div
        v-if="showDownload"
        v-tippy="downloadTippy"
        class="ai-artifact-file-card-action ai-artifact-file-card-download"
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
  </div>
</template>
<script setup lang="ts">
  import { cloneVNode, computed, shallowRef } from 'vue';

  import { Loading } from 'bkui-vue';
  import { directive as vTippy } from 'vue-tippy';

  import { triggerArtifactDownload, useArtifactPreviewConsumer } from '../../../../composables/use-artifact-preview';
  import { useCommonTippyInject } from '../../../../composables/use-common';
  import { useInputMentionConsumer } from '../../../../composables/use-input-mention';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadFileIcon } from '../../../../icons/file';
  import { CiteIcon } from '../../../../icons/tools';
  import { t } from '../../../../lang/lang';
  import { toArtifactMenuItem } from '../../../../utils/collect-message-artifacts';
  import FileIcon from '../../../file-icon/file-icon.vue';

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
  const commonTippyOptions = useCommonTippyInject();
  // 无输入框上下文（只读 / 分享态）时不展示引用入口
  const inputMention = useInputMentionConsumer();

  // 有外部 onPreview 或处于可预览的侧栏上下文时，卡片可点击
  const clickable = computed(() => !!props.onPreview || !!artifactPreview);

  // 未传 onArtifactClick 时隐藏下载；有外部 onDownload 或可异步取链时展示
  const showDownload = computed(() => !!props.onDownload || !!artifactPreview?.canResolveArtifactUrl.value);

  // 图标为共享 VNode，克隆后再渲染，避免多卡复用同一实例
  const downloadIcon = computed(() => cloneVNode(DownloadFileIcon));
  const citeIcon = computed(() => cloneVNode(CiteIcon));

  const downloadLoading = shallowRef(false);

  const downloadTippy = computed(() => ({
    ...commonTippyOptions?.value,
    content: t('下载'),
    theme: 'ai-chat-box',
    placement: 'top' as const,
  }));

  const citeTippy = computed(() => ({
    ...commonTippyOptions?.value,
    content: t('引用'),
    theme: 'ai-chat-box',
    placement: 'top' as const,
  }));

  const handleCite = () => {
    inputMention?.insertMention(toArtifactMenuItem(props.file));
  };

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

    // 操作区默认隐藏，hover 卡片时整体出现；下载中的 loading 需常驻
    &-actions {
      display: none;
      flex-shrink: 0;
      gap: 4px;
      align-items: center;
      margin-left: 4px;

      &:has(.is-loading) {
        display: inline-flex;
      }

      .ai-artifact-file-card:hover & {
        display: inline-flex;
      }
    }

    &-action {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      padding: 4px;
      font-size: 16px;
      color: #979ba5;
      cursor: pointer;
      border-radius: 4px;

      &:hover {
        color: #3a84ff;
        background-color: #f0f1f5;
      }

      &.is-loading {
        pointer-events: none;
        cursor: default;
      }
    }

    // 侧栏文件列表行：去边框/底色，由 hover / 选中态驱动背景
    &.is-list {
      flex: 0 0 32px;
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
