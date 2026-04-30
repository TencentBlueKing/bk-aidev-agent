<template>
  <div class="ai-interrupt-message">
    <div
      v-if="displayMessage"
      class="ai-interrupt-message__content"
    >
      {{ displayMessage }}
    </div>
    <template
      v-for="item in interruptList"
      :key="item.toolCallId"
    >
      <component
        :is="getRenderer(item)"
        v-if="getRenderer(item)"
        :interrupt="item"
      />
      <div
        v-else
        class="ai-interrupt-message__fallback"
      >
        {{ item.message || t('暂不支持的中断消息') }}
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import type { Component } from 'vue';

  import { InterruptReason } from '../../../ag-ui/types/constants';
  import { t } from '../../../lang/lang';
  import ToolApprovalCard from './tool-approval-card.vue';

  import type { InterruptItem, InterruptMessage, OnInterruptResume } from '../../../ag-ui/types/interrupt';

  const interruptRenderers: Partial<Record<InterruptReason, Component>> = {
    [InterruptReason.AIDevToolApproval]: ToolApprovalCard,
  };

  const props = defineProps<
    Partial<InterruptMessage> & {
      interrupt?: InterruptItem[];
      onInterruptResume?: OnInterruptResume;
    }
  >();

  const interruptList = computed(() => props.interrupt ?? []);
  const displayMessage = computed(() => props.message || props.content);

  const getRenderer = (item: InterruptItem) => interruptRenderers[item.reason];
</script>

<style lang="scss">
  .ai-interrupt-message {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
    width: 100%;
    font-size: 12px;
    line-height: 20px;
    color: #4d4f56;

    &__content {
      width: 100%;
      color: #4d4f56;
    }

    &__fallback {
      width: min(100%, 326px);
      padding: 12px 16px;
      color: #4d4f56;
      background: #f5f7fa;
      border: 1px solid #dcdee5;
      border-radius: 4px;
    }
  }
</style>
