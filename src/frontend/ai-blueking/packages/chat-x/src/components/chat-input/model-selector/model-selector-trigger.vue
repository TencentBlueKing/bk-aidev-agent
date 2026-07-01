<template>
  <div
    class="ai-model-selector-trigger"
    :class="{ 'is-expanded': expanded, 'is-disabled': disabled }"
  >
    <span
      v-if="model?.icon"
      class="ai-model-selector-trigger-icon"
    >
      <img
        v-if="typeof model.icon === 'string'"
        :src="model.icon"
        alt=""
      />
      <component
        :is="model.icon"
        v-else
      />
    </span>
    <span class="ai-model-selector-trigger-name">
      {{ model?.name || placeholder }}
    </span>
    <component
      :is="ArrowDownIcon"
      class="ai-model-selector-trigger-arrow"
    />
  </div>
</template>

<script setup lang="ts">
  import { ArrowDownIcon } from '../../../icons';

  import type { IModelOption } from './types';

  defineProps<{
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否展开（下拉打开），用于箭头翻转与背景态 */
    expanded?: boolean;
    /** 当前选中的模型 */
    model?: IModelOption;
    /** 无选中时的占位文案 */
    placeholder?: string;
  }>();
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-model-selector-trigger {
    display: flex;
    gap: 4px;
    align-items: center;
    height: 24px;
    padding: 0 8px;
    color: variables.$color-text;
    cursor: pointer;
    border-radius: 2px;
    transition: background-color 0.2s;

    &:hover,
    &.is-expanded {
      background: variables.$color-bg-tab;
    }

    &.is-disabled {
      color: #c4c6cc;
      cursor: not-allowed;
      background: transparent;
    }

    &-icon {
      display: flex;
      flex: 0 0 16px;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      font-size: 16px;

      img {
        width: 100%;
        height: 100%;
        object-fit: contain;
      }
    }

    &-name {
      overflow: hidden;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height, 20px);
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &-arrow {
      flex: 0 0 12px;
      font-size: 12px;
      color: variables.$color-text-secondary;
      transition: transform 0.2s;
    }

    &.is-expanded &-arrow {
      transform: rotate(180deg);
    }
  }
</style>
