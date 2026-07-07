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
    <!-- outcome.success 时按 reason 在会话内回显 resume 结果（审批单 / 已回答内容等） -->
    <component
      :is="resultRender.component"
      v-if="resultRender"
      v-bind="resultRender.props"
    >
      <!-- #answer 仅 UserQuestionAnsweredCard 消费，其它结果卡片忽略此 slot -->
      <template
        v-if="$slots.answeredQuestion"
        #answer="slotProps"
      >
        <slot
          name="answeredQuestion"
          v-bind="slotProps"
        />
      </template>
    </component>
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
    AIDevToolApprovalInterrupt,
    AIDevToolApprovalResume,
    Interrupt,
    InterruptMessage,
    InterruptResult,
    OnInterruptResume,
    UserQuestionResume,
  } from '../../../ag-ui/types/interrupt';
  import type { UserQuestionAnsweredCardSlots } from './user-question/user-question-answered-card.vue';

  defineSlots<{
    // 已回答内容回显的自定义 slot，透传给 UserQuestionAnsweredCard 的 #answer
    answeredQuestion: UserQuestionAnsweredCardSlots['answer'];
  }>();

  const interruptRenderers: Partial<Record<InterruptReason, Component>> = {
    [InterruptReason.AIDevToolApproval]: ToolApprovalCard,
  };

  // 由审批结果还原出 interrupt 形态，复用 ToolApprovalCard 渲染（回显态只读）
  const toApprovalInterrupt = (result: AIDevToolApprovalResume): AIDevToolApprovalInterrupt => ({
    id: result.interruptId || result.id || '',
    reason: InterruptReason.AIDevToolApproval,
    toolCallId: '',
    metadata: result.payload.metadata,
  });

  // outcome.success 时按 reason 分发 result 渲染：component + 组件 props 适配
  // 新增结果类型只需在此扩展一条映射，模板与透传链路保持不变
  type ResultRenderer = (result: InterruptResult) => { component: Component; props: Record<string, unknown> };
  const resultRenderers: Partial<Record<InterruptReason, ResultRenderer>> = {
    [InterruptReason.AIDevToolApproval]: result => ({
      component: ToolApprovalCard,
      props: { interrupt: toApprovalInterrupt(result as AIDevToolApprovalResume), readonly: false },
    }),
    [InterruptReason.UserQuestion]: result => ({
      component: UserQuestionAnsweredCard,
      props: {
        answers: (result as UserQuestionResume).payload?.answers ?? [],
        status: result.status,
      },
    }),
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

  // outcome.success 时按 reason 解析 result，得到要渲染的组件与其 props
  const resultRender = computed(() => {
    if (props.content?.outcome?.type !== 'success') return undefined;
    const result = props.content?.result;
    if (!result) return undefined;
    return resultRenderers[result.reason]?.(result);
  });
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
