<template>
  <div class="ai-selected-box">
    <i
      class="bkai-icon icon-close-circle-shape"
      @click="clearSelection"
    ></i>
    <div class="ai-selected-tip">
      <i class="bkai-icon icon-yinyong"></i>
      <span class="ai-selected-tip-text">
        {{ t('已框选内容') }}
      </span>
    </div>
    <div class="ai-selected-box-content">
      {{ props.selectedText }}
    </div>
    <div class="ai-selected-box-actions">
      <div
        v-for="action in props.actions"
        class="ai-selected-box-action"
        :key="action.key"
        @click="handleShortcutClick(action)"
      >
        <i
          class="bkai-icon"
          :class="action.icon"
        ></i>
        <span>{{ action.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { type ShortCut } from '@blueking/ai-ui-sdk';

  import { useSelect } from '../composables/use-select-pop';
  import { t } from '../lang';

  const emit = defineEmits<(e: 'shortcut-click', shortcut: ShortCut) => void>();

  const props = defineProps<{
    selectedText: string;
    actions: ShortCut[];
  }>();

  const { clearSelection } = useSelect(true);

  const handleShortcutClick = (shortcut: ShortCut) => {
    emit('shortcut-click', shortcut);
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

    .icon-close-circle-shape {
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

      .ai-selected-box-action {
        display: flex;
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

        .bkai-icon {
          font-size: 14px;
          color: #606060;
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
    }
  }
</style>
