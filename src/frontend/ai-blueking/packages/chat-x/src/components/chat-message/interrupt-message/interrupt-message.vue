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
        :on-interrupt-resume="onInterruptResume"
      />
      <!-- UserQuestion 的交互浮层渲染在 chat-input 上方，不在会话内渲染 -->
      <div
        v-else-if="!isSlotRenderedInterrupt(item)"
        class="ai-interrupt-message__fallback"
      >
        {{ item.message || t('暂不支持的中断消息') }}
      </div>
    </template>
    <!-- outcome.success 时在会话内回显用户已回答内容（含跳过=已取消态） -->
    <UserQuestionAnsweredCard
      v-if="userQuestionResume"
      :answers="answeredUserQuestion"
      :status="userQuestionResume.status"
    >
      <template
        v-if="$slots.answeredQuestion"
        #answer="slotProps"
      >
        <slot
          name="answeredQuestion"
          v-bind="slotProps"
        />
      </template>
    </UserQuestionAnsweredCard>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import type { Component } from 'vue';

  import { InterruptReason } from '../../../ag-ui/types/constants';
  import { t } from '../../../lang/lang';
  import ToolApprovalCard from './tool-approval-card.vue';
  import { UserQuestionAnsweredCard } from './user-question';

  import type {
    Interrupt,
    InterruptMessage,
    OnInterruptResume,
    UserQuestionAnswerItem,
  } from '../../../ag-ui/types/interrupt';
  import type { UserQuestionAnsweredCardSlots } from './user-question/user-question-answered-card.vue';

  defineSlots<{
    // 已回答内容回显的自定义 slot，透传给 UserQuestionAnsweredCard 的 #answer
    answeredQuestion: UserQuestionAnsweredCardSlots['answer'];
  }>();

  const interruptRenderers: Partial<Record<InterruptReason, Component>> = {
    [InterruptReason.AIDevToolApproval]: ToolApprovalCard,
  };

  // 这些中断类型的交互 UI 不在会话内渲染（如 UserQuestion 渲染在 chat-input 上方）
  const slotRenderedReasons = new Set<InterruptReason>([InterruptReason.UserQuestion]);

  const props = defineProps<Partial<InterruptMessage> & { onInterruptResume?: OnInterruptResume }>();

  const interruptList = computed(() =>
    props.content?.outcome?.type === 'interrupt' ? props.content.outcome.interrupts : [],
  );
  const displayMessage = computed(() => props.content?.message);

  const getRenderer = (item: Interrupt) => interruptRenderers[item.reason];
  const isSlotRenderedInterrupt = (item: Interrupt) => slotRenderedReasons.has(item.reason);

  // outcome.success 时定位 UserQuestion 的 resume 结果（用于回显问题与 已回复/已取消 状态）
  const userQuestionResume = computed(() => {
    if (props.content?.outcome?.type !== 'success') return undefined;
    const result = props.content?.result;
    return result?.reason === InterruptReason.UserQuestion ? result : undefined;
  });

  // 从 resume 结果中提取用户对各问题的回答用于回显（跳过态为空数组）
  const answeredUserQuestion = computed<UserQuestionAnswerItem[]>(
    () => (userQuestionResume.value?.payload?.answers ?? []) as UserQuestionAnswerItem[],
  );
</script>

<style lang="scss">
  .ai-interrupt-message {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
    width: 100%;
    min-width: 326px;
    max-width: 500px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height-compact, 20px);
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
