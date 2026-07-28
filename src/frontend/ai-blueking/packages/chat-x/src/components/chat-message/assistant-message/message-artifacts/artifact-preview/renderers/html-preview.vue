<template>
  <iframe
    class="ai-artifact-html-preview"
    :srcdoc="content"
  />
</template>
<script setup lang="ts">
  defineProps<{ content: string }>();
</script>
<style lang="scss">
  .ai-artifact-html-preview {
    width: 100%;
    height: 100%;
    border: none;
  }
</style>
