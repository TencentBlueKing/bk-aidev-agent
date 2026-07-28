<template>
  <div class="ai-artifact-markdown-preview">
    <MarkdownContent
      :content="content"
      :status="MessageStatus.Success"
    />
  </div>
</template>
<script setup lang="ts">
  import { MessageStatus } from '../../../../../../ag-ui/types/constants';
  import MarkdownContent from '../../../../../chat-content/markdown-content/markdown-content.vue';

  defineProps<{ content: string }>();
</script>
<style lang="scss">
  @import 'highlight.js/styles/github-dark.css';

  .ai-artifact-markdown-preview {
    width: 100%;
    height: 100%;
    overflow: auto;

    .ai-markdown-content {
      height: fit-content;
      min-height: 100%;
    }
  }
</style>
