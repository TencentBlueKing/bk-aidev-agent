<template>
  <iframe
    class="ai-artifact-url-iframe-preview"
    :src="url"
  />
</template>
<script setup lang="ts">
  defineProps<{ url: string }>();
</script>
<style lang="scss">
  .ai-artifact-url-iframe-preview {
    width: 100%;
    height: 100%;
    border: none;
  }
</style>
