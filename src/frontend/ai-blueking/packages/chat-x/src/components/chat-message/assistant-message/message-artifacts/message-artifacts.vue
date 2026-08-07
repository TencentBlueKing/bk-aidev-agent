<template>
  <div class="ai-message-artifacts">
    <ArtifactFileCard
      v-for="artifact in artifacts"
      :key="artifact.outputId"
      :file="artifact"
      :on-download="onDownload"
      :on-preview="onPreview"
    />
  </div>
</template>
<script setup lang="ts">
  import ArtifactFileCard from './artifact-file-card.vue';

  import type { AIFileInfo } from '../../../../ag-ui/types/file';

  defineProps<{
    // AI 生成的文件产物列表
    artifacts: AIFileInfo[];
    // 下载回调，透传给卡片以覆盖默认下载行为
    onDownload?: (file: AIFileInfo) => void;
    // 点击卡片主体的回调（可选，优先于内置侧栏预览）
    onPreview?: (file: AIFileInfo) => void;
  }>();
</script>
<style lang="scss">
  .ai-message-artifacts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    width: 100%;
  }
</style>
