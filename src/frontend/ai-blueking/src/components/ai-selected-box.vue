<template>
  <div class="ai-selected-box">
    <i
      class="bkai-icon bkai-close-circle-shape"
      @click="clearSelection"
    ></i>
    <div class="ai-selected-tip">
      <i class="bkai-icon bkai-yinyong"></i>
      <span class="ai-selected-tip-text">
        {{ t('已框选内容') }}
      </span>
    </div>
    <div class="ai-selected-box-content">
      {{ props.selectedText }}
    </div>
    <div
      ref="actionsContainerRef"
      class="ai-selected-box-actions"
    >
      <!-- 可见的操作项 -->
      <div
        v-for="action in visibleActions"
        :key="action.id"
        class="ai-selected-box-action"
        @click="handleShortcutClick(action)"
      >
        <i
          class="bkai-icon"
          :class="action.icon"
        ></i>
        <span>{{ action.name }}</span>
      </div>

      <!-- "更多"按钮 -->
      <div
        v-if="hiddenActions.length > 0"
        ref="moreButtonRef"
        class="ai-selected-box-action more-container"
      >
        <span>更多</span>
        <i class="bkai-icon bkai-angle-down"></i>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref, computed } from 'vue';

  import { useOverflowHandler } from '../composables/use-overflow-handler';
  import { useSelect } from '../composables/use-select-pop';
  import { t } from '../lang';
  import type { IShortcut } from '../types';

  const emit =
    defineEmits<
      (
        e: 'shortcut-click',
        data: { shortcut: IShortcut; source: 'popup' | 'main' | 'ai-selected' }
      ) => void
    >();

  const props = defineProps<{
    selectedText: string;
    actions: IShortcut[];
  }>();

  const { clearSelection } = useSelect(true);

  const actionsContainerRef = ref<HTMLElement | null>(null);
  const moreButtonRef = ref<HTMLElement | null>(null);

  // 创建一个 computed ref 来传递给 useOverflowHandler
  const actionsRef = computed(() => props.actions);

  const { visibleItems: visibleActions, hiddenItems: hiddenActions } = useOverflowHandler(
    actionsContainerRef,
    actionsRef,
    moreButtonRef,
    {
      theme: 'ai-blueking-light light',
      placement: 'top',
      trigger: 'mouseenter',
      interactive: true,
      allowHTML: true,
      arrow: true,
      offset: [0, 4],
      onItemClick: item => {
        emit('shortcut-click', { shortcut: item, source: 'ai-selected' });
      },
    }
  );

  const handleShortcutClick = (shortcut: IShortcut) => {
    emit('shortcut-click', { shortcut, source: 'ai-selected' });
  };
</script>

<style lang="scss" scoped>
  .ai-selected-box {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 16px;
    background: #ffffff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 6px 2px #1919290f;

    .bkai-close-circle-shape {
      position: absolute;
      top: -8px;
      right: -10px;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;

      &:hover {
        color: #979ba5;
      }
    }

    .ai-selected-tip {
      display: flex;
      gap: 10px;
      align-items: center;
      color: #979ba5;

      .bkai-icon {
        margin-right: 0;
        font-size: 14px;
      }

      .ai-selected-tip-text {
        font-size: 12px;
      }
    }

    .ai-selected-box-content {
      display: -webkit-box;
      max-height: 80px; /* 行高20px，4行共80px */
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      text-overflow: ellipsis;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 4;
      line-clamp: 4;
    }

    .ai-selected-box-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      overflow: hidden;
      flex-wrap: nowrap;
      width: 100%;
      min-width: 0;

      .ai-selected-box-action {
        display: inline-flex;
        flex-shrink: 0;
        align-items: center;
        justify-content: center;
        height: 26px;
        padding: 0 12px;
        font-size: 12px;
        color: #4d4f56;
        cursor: pointer;
        background: #ffffff;
        border: 1px solid #c4c6cc;
        border-radius: 13px;
        white-space: nowrap;
        max-width: 120px;
        min-width: 0;

        span {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          min-width: 0;
        }

        .bkai-icon {
          font-size: 14px;
          color: #606060;
          margin-right: 4px;
        }

        &:hover {
          color: #ffffff;
          background: #3a84ff;
          border-color: #3a84ff;

          .bkai-icon {
            color: #ffffff;
          }
        }
      }

      .more-container {
        gap: 4px;

        .bkai-angle-down {
          transition: transform 0.2s ease-in-out;
          color: #606060;
        }

        &:hover {
          .bkai-angle-down {
            transform: rotate(180deg);
          }
        }
      }
    }
  }
</style>
