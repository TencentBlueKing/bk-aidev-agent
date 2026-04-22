<template>
  <button
    class="ai-interrupt-option-btn"
    :class="{
      'is-selected': selected,
      'is-disabled': disabled,
    }"
    :disabled="disabled"
    type="button"
    @click="handleClick"
  >
    <span class="ai-interrupt-option-btn-label">{{ label }}</span>
    <span
      v-if="description"
      class="ai-interrupt-option-btn-desc"
    >
      {{ description }}
    </span>
  </button>
</template>

<script setup lang="ts">
  import type { InterruptOptionBtnProps } from './types';

  const props = defineProps<InterruptOptionBtnProps>();

  const emit = defineEmits<{
    (e: 'click'): void;
  }>();

  const handleClick = () => {
    if (props.disabled) {
      return;
    }
    emit('click');
  };
</script>

<style lang="scss">
  .ai-interrupt-option-btn {
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: flex-start;
    width: 100%;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #4d4f56;
    text-align: left;
    cursor: pointer;
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    transition:
      color 0.15s ease,
      background-color 0.15s ease,
      border-color 0.15s ease;

    &:hover {
      background-color: #f0f1f5;
    }

    &.is-selected {
      color: #3a84ff;
      background-color: #e1ecff;
      border-color: #3a84ff;
    }

    &.is-disabled {
      cursor: not-allowed;
      opacity: 0.6;
    }

    // &-label {
    //   font-weight: 700;
    // }

    &-desc {
      font-weight: 400;
      color: inherit;
      opacity: 0.85;
    }
  }
</style>
