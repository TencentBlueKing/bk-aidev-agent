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
        @click="() => load()"
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
    <CodePreview
      v-else-if="renderer === 'code'"
      :content="content"
      :extension="extension"
    />
    <TxtPreview
      v-else-if="renderer === 'txt'"
      :content="content"
    />
    <MarkdownPreview
      v-else-if="renderer === 'markdown'"
      :content="content"
    />
    <ImagePreview
      v-else-if="renderer === 'image'"
      :name="file?.name"
      :url="previewUrl"
    />
    <UrlIframePreview
      v-else
      :url="previewUrl"
    />
  </div>
</template>
<script setup lang="ts">
  import { computed, watch } from 'vue';

  import { Button } from 'bkui-vue';

  import { useArtifactPreviewConsumer } from '../../../../../composables/use-artifact-preview';
  import { t } from '../../../../../lang/lang';
  import { normalizeFileExtension } from '../../../../../utils/file-type';
  import MessageLoading from '../../../../message-loading/message-loading.vue';
  import CodePreview from './renderers/code-preview.vue';
  import HtmlPreview from './renderers/html-preview.vue';
  import ImagePreview from './renderers/image-preview.vue';
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
    resolveUrls: file => artifactPreview?.resolveArtifactUrls(file) ?? Promise.resolve({}),
  });

  const extension = computed(() => normalizeFileExtension(props.file?.type, props.file?.name));

  // 以 outputId 为唯一键；同文件类型变更时也需重新加载预览策略
  watch(
    () => (props.file ? `${props.file.outputId}:${props.file.type}` : ''),
    () => {
      load();
    },
    { immediate: true },
  );

  // 供侧栏 header 复制按钮读取预览正文与状态
  defineExpose({ content, renderer, status });
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
