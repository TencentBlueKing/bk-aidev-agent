<template>
  <div class="ai-info-message">
    <div class="ai-info-message-body">
      <div
        v-for="(text, index) in Array.isArray(content) ? content : [content]"
        :key="index"
        class="ai-info-message-content"
      >
        {{ text }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import type { InfoMessage } from '../../../ag-ui/types/messages';
  defineProps<Partial<InfoMessage>>();
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-info-message {
    display: flex;
    align-items: center;
    width: 100%;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    color: variables.$color-text-secondary;

    // 左右虚线夹中间文案，整块居中占位，避免 height:0 溢出被遮挡
    &::before,
    &::after {
      flex: 1;
      min-width: 16px;
      content: '';
      border-bottom: 1px dashed variables.$color-border;
    }

    &-body {
      display: flex;
      flex-shrink: 0;
      flex-direction: column;
      gap: 4px;
      align-items: center;
      max-width: calc(100% - 32px);
      padding: 0 12px;
      text-align: center;
    }

    &-content {
      max-width: 100%;
      word-break: break-word;
    }
  }
</style>
