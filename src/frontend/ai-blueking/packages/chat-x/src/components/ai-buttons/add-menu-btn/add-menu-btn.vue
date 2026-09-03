<template>
  <span
    v-tippy="{
      ...tippyOptions,
      content: t('添加'),
      theme: 'ai-chat-box',
      offset: [0, 16],
    }"
    class="ai-add-menu-btn"
    :class="{ 'is-active': active }"
    @click="emit('toggle')"
    @mousedown.prevent
  >
    <slot>
      <AddIcon />
    </slot>
  </span>
</template>
<script setup lang="ts">
  import { directive as vTippy } from 'vue-tippy';

  import { AddIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  import type { AITippyProps } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  export type AddMenuBtnProps = {
    /** 聚合菜单是否处于展开态 */
    active?: boolean;
    tippyOptions?: AITippyProps;
  };
  defineProps<AddMenuBtnProps>();
  const emit = defineEmits<{
    (e: 'toggle'): void;
  }>();
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-add-menu-btn {
    display: flex;
    flex: 0 0 32px;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    font-size: var(--ai-icon-size-sm, 16px);
    color: variables.$color-text-secondary;
    cursor: pointer;
    border-radius: 99px;
    transition: background-color 0.2s;

    &:hover,
    &.is-active {
      background: variables.$color-bg-tab;
    }
  }
</style>
