<template>
  <span
    class="ai-upload-spinner"
    aria-hidden="true"
  />
</template>
<script setup lang="ts">
  defineOptions({ name: 'UploadSpinner' });
</script>
<style lang="scss">
  .ai-upload-spinner {
    box-sizing: border-box;
    flex: 0 0 16px;
    width: 16px;
    height: 16px;
    border: 2px solid rgb(255 255 255 / 35%);
    border-top-color: #fff;
    border-radius: 50%;
    animation: ai-upload-spin 0.8s linear infinite;
  }

  @keyframes ai-upload-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
