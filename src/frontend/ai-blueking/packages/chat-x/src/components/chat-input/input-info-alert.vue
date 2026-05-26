<template>
  <div class="chat-input-info-alert">
    <InfoIcon class="chat-input-info-alert__icon" />
    <span class="chat-input-info-alert__text">{{ content }}</span>
  </div>
</template>

<script setup lang="ts">
  import { InfoIcon } from '../../icons';
  defineProps<{
    content: string;
  }>();
</script>

<style lang="scss">
  @use '../../styles/variables.scss' as variables;

  .chat-input-info-alert {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    width: 100%;
    min-width: variables.$chat-input-min-width;
    max-width: variables.$chat-input-max-width;
    padding: 6px 8px;
    margin-bottom: 6px;
    color: #4d4f56;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 4px;

    &__icon {
      display: inline-flex;
      flex: 0 0 16px;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      margin-top: 2px;
      font-size: 12px;
      font-weight: 600;
      line-height: 16px;
      color: #3a84ff;
    }

    &__text {
      flex: 1 1 auto;
      min-width: 0;
      font-size: 12px;
      line-height: 20px;
    }
  }
</style>
