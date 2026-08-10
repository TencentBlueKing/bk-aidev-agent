<template>
  <div class="ai-artifact-image-preview">
    <img
      :alt="name"
      :src="url"
    />
  </div>
</template>
<script setup lang="ts">
  defineProps<{ name?: string; url: string }>();
</script>
<style lang="scss">
  .ai-artifact-image-preview {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    overflow: auto;

    img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
  }
</style>
