<template>
  <div
    ref="panelRef"
    class="ai-input-menu"
  >
    <div
      v-for="group in groups"
      :key="group.key"
      class="ai-input-menu-group"
      :class="{ 'is-divided': group.divided }"
    >
      <div class="ai-input-menu-title">{{ t(group.name) }}</div>
      <InputMenuOption
        v-for="item in group.items"
        :key="item.id"
        :active="activeItem?.id === item.id"
        :item="item"
        @select="emit('select', $event)"
      />
      <div
        v-if="!group.items.length"
        class="ai-input-menu-empty"
      >
        {{ t('暂无数据') }}
      </div>
      <div
        v-if="group.restCount"
        class="ai-input-menu-toggle"
        @click="emit('toggleGroup', group.key)"
      >
        <ArrowLeftIcon
          class="ai-input-menu-toggle-icon"
          :class="{ 'is-expanded': group.expanded }"
        />
        <span>{{ group.expanded ? t('收起') : t('更多') }} +{{ group.restCount }}</span>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onMounted, onUnmounted, useTemplateRef, watch } from 'vue';

  import { useMenuKeydown } from '../../../composables/use-menu-keydown';
  import { ArrowLeftIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import InputMenuOption from './input-menu-option.vue';

  import type { IInputMenuGroup, IInputMenuItem } from '../../../types/input-menu';

  const props = defineProps<{
    /** 当前可见且可选中的条目，顺序与面板一致 */
    flatItems: IInputMenuItem[];
    groups: IInputMenuGroup[];
  }>();
  const emit = defineEmits<{
    (e: 'select', item: IInputMenuItem): void;
    (e: 'toggleGroup', key: string): void;
    (e: 'close'): void;
  }>();

  const panelRef = useTemplateRef<HTMLElement>('panelRef');

  const flatItems = computed(() => props.flatItems);
  const { activeIndex } = useMenuKeydown<IInputMenuItem>({
    items: flatItems,
    onSelect: item => emit('select', item),
    menuRef: panelRef,
  });
  const activeItem = computed(() => props.flatItems[activeIndex.value]);

  // 结果集变化后旧的高亮下标已无意义，回到首项
  watch(flatItems, () => {
    activeIndex.value = 0;
  });

  // Esc 关闭菜单：与 useMenuKeydown 一样用捕获阶段，避免被编辑器先行消费
  const handleEscape = (event: KeyboardEvent) => {
    if (event.key !== 'Escape') {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    emit('close');
  };
  onMounted(() => {
    window.addEventListener('keydown', handleEscape, true);
  });
  onUnmounted(() => {
    window.removeEventListener('keydown', handleEscape, true);
  });
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-input-menu {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
    max-height: 400px; // 设计稿标注：最大高度 400px，超出滚动
    padding: 8px;
    overflow-y: auto;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height-compact, 20px);
    background: #fff;
    border: 1px solid variables.$color-border;
    border-radius: 16px;
    box-shadow: 0 0 10px 0 rgb(0 0 0 / 10%);

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-thumb {
      background: variables.$color-border;
      border-radius: 888px;
    }

    &-group {
      display: flex;
      flex-direction: column;

      &.is-divided {
        padding-bottom: 4px;
        border-bottom: 1px solid variables.$color-bg-tab;
      }
    }

    &-title,
    &-empty {
      padding: 6px 12px;
      color: variables.$color-text-secondary;
    }

    &-toggle {
      display: flex;
      gap: 12px;
      align-items: center;
      padding: 6px 12px 6px 14px;
      color: variables.$color-text;
      color: #979ba5;
      cursor: pointer;
      border-radius: 8px;

      &:hover {
        background: variables.$color-bg-hover;
      }

      &-icon {
        flex: 0 0 12px;
        width: 12px;
        height: 12px;
        font-size: 12px;
        color: #c4c6cc;
        transform: rotate(-90deg);
        transition: transform 0.2s ease-in-out;

        path {
          stroke-width: 100;
        }

        &.is-expanded {
          transform: rotate(90deg);
        }
      }
    }
  }
</style>
