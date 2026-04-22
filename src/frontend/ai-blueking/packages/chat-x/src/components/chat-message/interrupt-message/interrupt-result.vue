<template>
  <div class="ai-interrupt-result">
    <span class="ai-interrupt-result-icon">
      <BkFlowSuccessIcon />
    </span>
    <div class="ai-interrupt-result-body">
      <p class="ai-interrupt-result-title">{{ title }}</p>
      <p
        v-for="(label, index) in selectedLabels"
        :key="index"
        class="ai-interrupt-result-item"
      >
        {{ label }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { BkFlowSuccessIcon } from '../../../icons';

  import type { InterruptResultProps } from './types';

  defineProps<InterruptResultProps>();
</script>

<style lang="scss">
  .ai-interrupt-result {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    width: 100%;
    padding: 12px;
    font-size: 12px;
    line-height: 20px;
    background-color: #f5f7fa;
    border-radius: 2px;

    &-icon {
      display: flex;
      flex: 0 0 16px;
      align-items: center;
      padding-top: 2px;
      font-size: 14px;
    }

    &-body {
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-width: 0;
    }

    &-title {
      margin: 0;
      font-weight: 700;
      color: #000;
    }

    &-item {
      margin: 0;
      color: #4d4f56;
    }
  }
</style>
