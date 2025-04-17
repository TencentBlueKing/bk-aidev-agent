<template>
  <div class="shortcuts-bar">
    <div
      v-for="shortcut in shortcuts"
      class="shortcut-item"
      :key="shortcut.key"
      @click="emit('shortcut-click', shortcut)"
    >
      <i
        class="bkai-icon"
        :class="shortcut.icon"
      ></i>
      <span class="shortcut-text">{{ shortcut.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { type ShortCut } from '@blueking/ai-ui-sdk';

  const emit = defineEmits<{
    'shortcut-click': [ShortCut];
  }>();

  defineProps<{
    shortcuts: ShortCut[];
  }>();
</script>

<style lang="scss" scoped>
  .shortcuts-bar {
    display: flex;
    gap: 4px;

    .shortcut-item {
      display: flex;
      gap: 4px;
      align-items: center;
      height: 24px;
      padding: 0 8px;
      font-size: 12px;
      color: #4d4f56;
      cursor: pointer;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 12px;

      .bkai-icon {
        margin-right: 0;
        font-size: 16px;
        color: #979ba5;
      }

      &:hover {
        color: #3a84ff;
        background: #e1ecff;
        border-color: #a3c5fd;

        .bkai-icon {
          color: #3a84ff;
        }
      }
    }
  }
</style>
