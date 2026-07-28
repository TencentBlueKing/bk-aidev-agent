<template>
  <pre class="ai-artifact-txt-preview">{{ content }}</pre>
</template>
<script setup lang="ts">
  defineProps<{ content: string }>();
</script>
<style lang="scss">
  @use '../../../../../../styles/variables.scss' as variables;

  .ai-artifact-txt-preview {
    width: 100%;
    height: 100%;
    margin: 0;
    overflow: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    color: variables.$color-title;
    word-break: break-all;
    white-space: pre-wrap;
  }
</style>
