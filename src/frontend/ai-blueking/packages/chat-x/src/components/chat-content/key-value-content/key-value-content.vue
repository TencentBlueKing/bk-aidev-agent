<template>
  <div class="ai-key-value-content">
    <div
      v-if="title"
      class="ai-key-value-title"
    >
      <ThinkingIcon />
      {{ title }}
    </div>
    <div class="ai-key-value-content">
      <div
        v-for="item in content"
        :key="item.key"
        class="key-value-item"
      >
        <div class="item-key">{{ item.key }}</div>
        :
        <div class="item-value">{{ item.value }}</div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ThinkingIcon } from '../../../icons';
  defineProps<{
    content: {
      key: string;
      value: string;
    }[];
    title?: string;
  }>();
</script>
<style lang="scss">
  .ai-key-value-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12px;
    color: #4d4f56;

    .ai-key-value-title {
      display: flex;
      gap: 4px;
      align-items: center;
      font-size: 12px;
      font-weight: 700;
      color: #3a84ff;

      .ai-thinking-icon {
        width: 14px;
        height: 14px;
        font-size: 14px;
      }
    }

    .ai-key-value-content {
      display: flex;
      flex-direction: column;
    }

    .key-value-item {
      display: flex;
      flex-direction: row;
      gap: 3px;
      align-items: center;
      height: 20px;
    }

    .item-key {
      font-weight: bold;
      color: #333;
    }

    .item-value {
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 12px;
      white-space: nowrap;
    }
  }
</style>
