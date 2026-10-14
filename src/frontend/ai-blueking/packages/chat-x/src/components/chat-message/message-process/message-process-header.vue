<template>
  <div
    class="ai-message-process-header"
    :class="{ 'is-collapsible': collapsible }"
    @click="handleClick"
  >
    <span
      class="ai-message-process-header-text"
      :class="{ 'is-loading': loading }"
      >{{ label }}<template v-if="elapsedText">，{{ t('耗时') }}：{{ elapsedText }}</template></span
    >
    <ChevronRightIcon
      v-if="collapsible"
      :class="{ 'is-expanded': expanded }"
    />
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { ChevronRightIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { formatProcessElapsed, resolveProcessElapsed } from './resolve-process-elapsed';

  export type MessageProcessHeaderProps = {
    /** 可折叠时才显示箭头并响应点击 */
    collapsible?: boolean;
    endAt?: number;
    expanded?: boolean;
    label: string;
    /** 生成中，文案显示渐变闪动 */
    loading?: boolean;
    startAt?: number;
  };

  const props = withDefaults(defineProps<MessageProcessHeaderProps>(), {
    collapsible: false,
    expanded: false,
    loading: false,
  });

  const emit = defineEmits<{
    (e: 'toggle'): void;
  }>();

  // 只在调用方传入起止时间时展示；进行中不传，因此不会出现耗时
  const elapsedText = computed(() => {
    const elapsed = resolveProcessElapsed(props.startAt, props.endAt);
    return elapsed === undefined ? '' : formatProcessElapsed(elapsed);
  });

  const handleClick = () => {
    if (!props.collapsible) {
      return;
    }
    emit('toggle');
  };
</script>
<style lang="scss">
  @use '../../../styles/text-shimmer.scss' as shimmer;
  @use '../../../styles/variables.scss' as variables;

  .ai-message-process-header {
    display: flex;
    gap: 4px;
    align-items: center;
    width: 100%;
    height: 32px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    color: variables.$color-text-secondary;
    border-bottom: 1px solid variables.$color-border-light;

    &.is-collapsible {
      cursor: pointer;
    }

    &-text {
      white-space: nowrap;

      &.is-loading {
        @include shimmer.text-shimmer;
      }
    }

    .ai-chevron-right-icon {
      flex-shrink: 0;
      width: 10px;
      height: 10px;
      transition: transform 0.2s ease-in-out;

      &.is-expanded {
        transform: rotate(90deg);
      }
    }
  }
</style>
