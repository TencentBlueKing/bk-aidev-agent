<template>
  <div
    v-tippy="tippyProps"
    class="ai-tool-btn"
    :class="{ 'is-active': active, 'is-disabled': disabled }"
    :style="{ '--ai-tool-btn-active-color': id === 'like' || id === 'activeLike' ? '#3a84ff' : '#E71818' }"
    @click="handleClick"
  >
    <template v-if="id in ToolIconsMap">
      <component :is="ToolIconsMap[id]" />
    </template>
    <template v-else>
      <div>{{ name }}</div>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { type TippyOptions, directive as vTippy } from 'vue-tippy';

  import { ToolIconsMap } from '../../../icons/tools';

  import type { IToolBtn } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<
    IToolBtn & {
      active?: boolean;
      disabled?: boolean;
      tippyOptions?: Partial<Omit<TippyOptions, 'getReferenceClientRect' | 'triggerTarget'>>;
    }
  >();
  const emit = defineEmits<{
    (e: 'click', data: IToolBtn, event: MouseEvent): void;
  }>();

  const tippyProps = computed(() => {
    return {
      content: props.description,
      theme: 'ai-chat-box',
      ...(props.tippyOptions || {}),
      onShow: () => {
        if (props.disabled) return false;
      },
    };
  });
  const handleClick = (e: MouseEvent) => {
    if (props.disabled) return;
    emit('click', props, e);
  };
</script>
<style lang="scss">
  .ai-tool-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    max-width: fit-content;
    height: 20px;
    font-size: 16px;
    color: #a8aab2;
    background-color: transparent;
    border-radius: 4px;

    &.is-active {
      color: var(--ai-tool-btn-active-color, #3a84ff) !important;

      // background-color: #eaebf0;
    }

    &.is-disabled {
      color: #979ba5;
      pointer-events: hover;
      cursor: not-allowed !important;
    }

    &:not(.is-disabled):hover {
      color: #4d4f56;
      cursor: pointer;
      background-color: #eaebf0;
    }
  }
</style>
