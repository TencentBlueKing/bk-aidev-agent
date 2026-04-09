<template>
  <div
    :class="['ai-scroll-btn', { 'is-loading': loading, 'is-disabled': disabled }]"
    @click="handleClick"
  >
    <Loading
      v-if="loading"
      mode="spin"
      size="mini"
      theme="primary"
    />
    <template v-else>
      <slot name="icon"></slot>
    </template>
    <slot name="title">
      {{ title }}
    </slot>
  </div>
</template>

<script setup lang="ts">
  import { Loading } from 'bkui-vue';

  const props = defineProps<{
    disabled?: boolean;
    loading?: boolean;
    title?: string;
  }>();

  const emit = defineEmits<{
    (e: 'click', event: MouseEvent): void;
  }>();

  const handleClick = (event: MouseEvent) => {
    if (props.loading || props.disabled) return;
    emit('click', event);
  };
</script>

<style lang="scss">
  .ai-scroll-btn {
    display: flex;
    gap: 4px;
    align-items: center;
    justify-content: center;
    width: fit-content;
    min-width: 84px;
    height: 24px;
    font-size: 12px;
    color: #4d4f56;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 26px;
    box-shadow: 0 -2px 6px 0 #0000001a;

    &:hover {
      cursor: pointer;
      border: 1px solid #c4c6cc;
      box-shadow: 0 -2px 6px 0 #00000026;
    }

    &.is-loading,
    &.is-disabled {
      cursor: not-allowed;
      opacity: 0.65;
    }

    .ai-common-icon {
      width: 14px;
      height: 14px;
      font-size: 14px;
    }
  }
</style>
