<template>
  <div class="ai-cite-content">
    <CiteIcon />
    <span class="ai-cite-content-text">
      {{ content }}
    </span>
    <CloseIcon
      v-if="onClose"
      @click="onClose?.(content)"
    />
  </div>
</template>
<script setup lang="ts">
  import { CiteIcon, CloseIcon } from '../../../icons';
  defineProps<{
    content: string;
    onClose?: (content: string) => void;
  }>();
</script>
<style lang="scss">
  .ai-cite-content {
    display: flex;
    gap: 4px;
    align-items: center;
    justify-content: flex-end;

    // width: 100%;
    max-width: 100%;
    height: 28px;
    padding: 0 8px;
    margin-bottom: 4px;
    font-size: 12px;
    color: #4d4f56;
    background: #f5f7fa;
    border-radius: 4px;

    .ai-cite-content-text {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      color: #979ba5;
      white-space: nowrap;
    }

    .ai-cite-icon {
      width: 14px;
      height: 14px;
      font-size: 14px;
      color: #979ba5;
    }

    .ai-close-icon {
      width: 14px;
      height: 14px;
      font-size: 14px;
      color: #979ba5;

      &:hover {
        color: #4d4f56;
        cursor: pointer;
      }
    }
  }
</style>
