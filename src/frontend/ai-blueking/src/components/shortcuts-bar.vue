<template>
  <div
    ref="containerRef"
    class="shortcuts-bar"
  >
    <!-- 可见的 shortcuts -->
    <div
      v-for="shortcut in visibleShortcuts"
      :key="shortcut.id"
      class="shortcut-item"
      @click="emit('shortcut-click', { shortcut, source: 'main' })"
    >
      <component
        :is="shortcut.iconRender ? shortcut.iconRender(h) : null"
        v-if="shortcut.iconRender"
      />
      <i
        v-else-if="shortcut.icon"
        :class="shortcut.icon"
      ></i>
      <span class="shortcut-text">{{ shortcut.alias ?? shortcut.name }}</span>
    </div>

    <!-- "更多"按钮 -->
    <div
      v-if="hiddenShortcuts.length > 0"
      ref="moreButtonRef"
      class="shortcut-item more-container"
    >
      <span class="shortcut-text">更多</span>
      <i class="bkai-icon bkai-angle-down"></i>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref, computed, h } from 'vue';

  import { useOverflowHandler } from '../composables/use-overflow-handler';
  import type { IShortcut } from '../types';

  // --- Props and Emits ---
  const props = defineProps<{
    shortcuts: IShortcut[];
  }>();
  const emit = defineEmits<{
    'shortcut-click': [{ shortcut: IShortcut; source: 'popup' | 'main' }];
  }>();

  const containerRef = ref<HTMLDivElement | null>(null);
  const moreButtonRef = ref<HTMLDivElement | null>(null);

  // 创建一个 computed ref 来传递给 useOverflowHandler
  const shortcutsRef = computed(() => props.shortcuts);

  // 使用 useOverflowHandler 处理溢出逻辑
  const { visibleItems: visibleShortcuts, hiddenItems: hiddenShortcuts } = useOverflowHandler(
    containerRef,
    shortcutsRef,
    moreButtonRef,
    {
      theme: 'ai-blueking-light light',
      placement: 'bottom',
      trigger: 'mouseenter',
      interactive: true,
      allowHTML: true,
      arrow: true,
      offset: [0, 4],
      onItemClick: shortcut => {
        emit('shortcut-click', { shortcut, source: 'main' });
      },
    }
  );
</script>

<style lang="scss" scoped>
  /* 样式与之前版本相同，这里不再赘述，只保留关键部分 */
  .shortcuts-bar {
    display: flex;
    gap: 4px;
    align-items: center; // 垂直居中对齐
    overflow: hidden; // 隐藏计算过程中的视觉溢出
  }

  .shortcut-item {
    display: inline-flex;
    flex-shrink: 0; // 防止 flex 布局压缩项目
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
    max-width: 200px;
    transition: all 0.2s ease;
    /* 强制不换行，以便正确获取宽度 */
    white-space: nowrap;

    .shortcut-text {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .bk-icon,
    .bkai-icon {
      font-size: 16px;
      color: #979ba5;
    }

    &:hover {
      color: #3a84ff;
      background: #e1ecff;
      border-color: #a3c5fd;

      .bk-icon,
      .bkai-icon {
        color: #3a84ff;
      }
    }
  }

  .more-container {
    gap: 0;
    .bkai-angle-down {
      transition: transform 0.2s ease-in-out;
      margin-right: 0;
      color: #979ba5;
    }

    &:hover {
      .bkai-angle-down {
        transform: rotate(180deg);
      }
    }
  }
</style>
