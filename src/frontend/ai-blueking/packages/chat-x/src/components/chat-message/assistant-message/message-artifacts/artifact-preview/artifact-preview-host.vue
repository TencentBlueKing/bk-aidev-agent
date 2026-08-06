<template>
  <div class="ai-artifact-preview-host">
    <div
      v-if="status === 'loading'"
      class="ai-artifact-preview-host-loading"
    >
      <MessageLoading />
    </div>
    <div
      v-else-if="status === 'error'"
      class="ai-artifact-preview-host-error"
    >
      <span>{{ t('预览加载失败') }}</span>
      <Button
        size="small"
        text
        theme="primary"
        @click="() => load({ force: true })"
      >
        {{ t('重试') }}
      </Button>
    </div>
    <div
      v-else-if="status === 'empty' || !file"
      class="ai-artifact-preview-host-empty"
    >
      {{ t('暂无可预览的文件') }}
    </div>
    <HtmlPreview
      v-else-if="renderer === 'html'"
      :content="content"
    />
    <TxtPreview
      v-else-if="renderer === 'txt'"
      :content="content"
    />
    <MarkdownPreview
      v-else-if="renderer === 'markdown'"
      :content="content"
    />
    <UrlIframePreview
      v-else
      :url="previewUrl"
    />
  </div>
</template>
<script setup lang="ts">
  import { watch } from 'vue';

  import { Button } from 'bkui-vue';

  import { useArtifactPreviewConsumer } from '../../../../../composables/use-artifact-preview';
  import { t } from '../../../../../lang/lang';
  import MessageLoading from '../../../../message-loading/message-loading.vue';
  import HtmlPreview from './renderers/html-preview.vue';
  import MarkdownPreview from './renderers/markdown-preview.vue';
  import TxtPreview from './renderers/txt-preview.vue';
  import UrlIframePreview from './renderers/url-iframe-preview.vue';
  import { useArtifactPreviewLoader } from './use-artifact-preview-loader';

  import type { AIFileInfo } from '../../../../../ag-ui/types/file';

  const props = defineProps<{ file?: AIFileInfo }>();
  const artifactPreview = useArtifactPreviewConsumer();

  const { content, load, previewUrl, renderer, status } = useArtifactPreviewLoader({
    canResolve: () => !!artifactPreview?.canResolveArtifactUrl.value,
    getFile: () => props.file,
    // 无 options 时不传第二参，避免 mock 断言收到 (file, undefined)
    resolveUrls: (file, options) =>
      (options ? artifactPreview?.resolveArtifactUrls(file, options) : artifactPreview?.resolveArtifactUrls(file)) ??
      Promise.resolve({}),
  });

  // 以 outputId 为唯一键；同文件类型变更时也需重新加载预览策略
  watch(
    () => (props.file ? `${props.file.outputId}:${props.file.type}` : ''),
    () => {
      load();
    },
    { immediate: true },
  );
</script>
<style lang="scss">
  @use '../../../../../styles/variables.scss' as variables;

  .ai-artifact-preview-host {
    width: 100%;
    height: 100%;
    font-size: var(--ai-font-size, 12px);

    &-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
    }

    &-error {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: variables.$color-text-secondary;
    }

    &-empty {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: variables.$color-text-secondary;
    }
  }
</style>
