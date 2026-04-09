<template>
  <div class="ai-error-content">
    <ErrorIcon />
    <div class="ai-error-content-text">
      {{ content }}
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ErrorIcon } from '../../../icons/messages';

  defineProps<{
    content?: string;
  }>();
</script>
<style lang="scss">
  .ai-error-content {
    position: relative;
    display: flex;
    align-items: center;

    .ai-error-icon {
      position: absolute;
      top: 2px;
      left: 0;
      flex: 0 0 14px;
      width: 14px;
      height: 14px;
      margin-right: 6px;
      font-size: 14px;
      color: #ea3636;
    }

    &-text {
      flex: 1;
      margin-left: 20px;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
    }
  }
</style>
