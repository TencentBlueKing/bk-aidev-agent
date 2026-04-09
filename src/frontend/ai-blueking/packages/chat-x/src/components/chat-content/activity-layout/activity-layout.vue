<template>
  <div class="ai-activity-message">
    <div
      class="ai-activity-message-title"
      @click="collapsed = !collapsed"
    >
      <slot
        name="title"
        v-bind="{ collapsed }"
      />
      <span
        v-if="activityType !== MessageContentType.FlowAgent"
        class="ai-activity-message-title-icon collapsed-icon"
        :class="{ 'is-collapsed': collapsed }"
      >
        <CollapsedIcon />
      </span>
    </div>
    <div
      v-show="!collapsed"
      class="ai-activity-message-content"
    >
      <slot />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { MessageContentType } from '../../../ag-ui/types/constants';
  import { CollapsedIcon } from '../../../icons/messages';

  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });
  defineProps<{
    activityType?: MessageContentType;
  }>();
</script>
<style lang="scss">
  .ai-activity-message {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12px;

    &-title {
      display: flex;
      align-items: center;
      width: fit-content;
      max-width: 100%;
      height: 28px;
      padding: 0 10px;
      color: #4d4f56;
      background: #f0f1f5;
      border-radius: 4px;

      &-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        font-size: 16px;

        &.collapsed-icon {
          width: 12px;
          height: 12px;
          margin-right: 0;
          margin-left: 8px;
          font-size: 10px;
          color: #4d4f56;
          transform: rotate(90deg);
        }

        &.is-collapsed {
          transform: rotate(-90deg);
        }
      }

      &-text {
        display: inline;
        flex: 1;
        width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &:hover {
        cursor: pointer;
        background: #eaebf0;
      }
    }

    &-content {
      display: flex;
      flex-direction: column;
      padding: 16px 0;
      font-size: 14px;
      background: #f5f7fa;
      border-radius: 2px;
    }
  }
</style>
