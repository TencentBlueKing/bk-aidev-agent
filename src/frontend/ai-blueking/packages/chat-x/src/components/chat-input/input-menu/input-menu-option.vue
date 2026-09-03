<template>
  <div
    v-tippy="tippyOptions"
    class="ai-input-menu-option"
    :class="{ 'is-active': active, 'is-disabled': item.disabled }"
    @click="handleSelect"
  >
    <ResourceIcon
      :icon="item.icon"
      :name="item.name"
      :type="item.type"
    />
    <span
      v-overflow-tips="{ text: item.name, zIndex: EDITOR_MENU_Z_INDEX }"
      class="ai-input-menu-option-name"
    >
      {{ item.name }}
    </span>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { directive as vTippy } from 'vue-tippy';

  import { EDITOR_MENU_Z_INDEX } from '../../../common';
  import { OverflowTips as vOverflowTips } from '../../../directives';
  import { t } from '../../../lang/lang';
  import { createMentionTippy } from '../../mention';
  import { ResourceIcon } from '../../resource-icon';
  import { getMenuTypeLabel } from './constants';

  import type { IInputMenuItem } from '../../../types/input-menu';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    /** 键盘导航选中态 */
    active?: boolean;
    item: IInputMenuItem;
  }>();
  const emit = defineEmits<{
    (e: 'select', item: IInputMenuItem): void;
  }>();

  // 与输入框内标签共用同一套气泡，标题格式与类型名同源
  const tippyOptions = computed(() => {
    if (!props.item.description) {
      return { content: '', onShow: () => false };
    }
    const typeLabel = getMenuTypeLabel(props.item.type);
    return createMentionTippy({
      title: typeLabel ? `${t(typeLabel)}：${props.item.name}` : props.item.name,
      description: props.item.description,
    });
  });

  const handleSelect = () => {
    if (props.item.disabled) {
      return;
    }
    emit('select', props.item);
  };
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-input-menu-option {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 6px 12px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height-compact, 20px);
    color: variables.$color-text;
    cursor: pointer;
    border-radius: 8px;

    .ai-resource-icon {
      color: variables.$color-text-secondary;
    }

    &-name {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &.is-active,
    &:hover {
      background: variables.$color-bg-hover;
    }

    &.is-disabled {
      color: variables.$color-text-secondary;
      cursor: not-allowed;
      background: transparent;
    }
  }
</style>
