<template>
  <div class="history-group">
    <div class="history-group-title">
      <span>{{ props.title }}</span>
    </div>
    <div class="history-group-list">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
  import type { HistoryGroupProps } from './types';

  const props = defineProps<HistoryGroupProps>();
</script>

<style lang="scss" scoped>
  .history-group {
    .history-group-title {
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
      margin-bottom: 4px;
      padding: 0 8px;
    }

    .history-group-list {
      display: flex;
      flex-direction: column;
    }
  }
</style>
