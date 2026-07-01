<template>
  <component :is="messageComponent" />
</template>
<script setup lang="ts">
  import { type Component, type VNode, computed, h, renderSlot, useSlots } from 'vue';

  import { MessageRole } from '../../../ag-ui/types/constants';
  import { type AssistantMessage as AssistantMessageProps } from '../../../ag-ui/types/messages';
  import ContentRender from '../../chat-content/content-render/content-render.vue';
  import ActivityMessage from '../activity-message/activity-message.vue';
  import AssistantMessage from '../assistant-message/assistant-message.vue';
  import InfoMessage from '../info-message/info-message.vue';
  import { InterruptMessageRender } from '../interrupt-message';
  import LoadingMessage from '../loading-message/loading-message.vue';
  import ReasoningMessage from '../reasoning-message/reasoning-message.vue';
  import ToolMessage from '../tool-message/tool-message.vue';
  import UserMessage from '../user-message/user-message.vue';

  import type { Message, MessageStatus } from '../../../ag-ui/types';
  import type { OnInterruptResume } from '../../../ag-ui/types/interrupt';
  import type { Token } from '../../../markdown-it';
  import type { MessageToolsProps } from '../../message-tools/message-tools.vue';
  import type { UserQuestionAnsweredCardSlots } from '../interrupt-message/user-question/user-question-answered-card.vue';
  import type { UserMessageActionsProps } from '../user-message/user-message.vue';

  defineSlots<{
    // 中断消息「已回答内容」回显的自定义 slot，透传给 InterruptMessageRender
    answeredQuestion: UserQuestionAnsweredCardSlots['answer'];
    codeHeader: (props: { language: string; token: Token[] }) => null | undefined | VNode;
    default: (props: { content: string; status: MessageStatus }) => VNode;
  }>();

  const props = defineProps<
    Partial<UserMessageActionsProps> &
      Pick<MessageToolsProps, 'onAction' | 'tippyOptions'> & {
        message: Partial<Message>;
        onInterruptResume?: OnInterruptResume;
      }
  >();

  const slots = useSlots();

  type AnsweredQuestionSlotProps = Parameters<UserQuestionAnsweredCardSlots['answer']>[0];

  const messageComponent = computed(() => {
    switch (props.message.role) {
      case MessageRole.User:
        return h(UserMessage, {
          ...props.message,
          onAction: props.onAction,
          onInputConfirm: props.onInputConfirm,
          onShortcutConfirm: props.onShortcutConfirm,
          messageToolsStatus: props.messageToolsStatus,
          tippyOptions: props.tippyOptions,
        });
      case MessageRole.Assistant:
        return h(AssistantMessage, props.message, {
          default: (slotProps: Partial<AssistantMessageProps>) =>
            renderSlot(slots, 'default', slotProps, () => [
              h(
                ContentRender as unknown as Component,
                { content: props.message.content || '', status: props.message.status },
                slots.codeHeader
                  ? {
                      codeHeader: (slotProps: { language: string; token: Token[] }) => slots.codeHeader?.(slotProps),
                    }
                  : undefined,
              ),
            ]),
        });
      case MessageRole.Info:
        return h(InfoMessage, props.message);
      case MessageRole.Reasoning:
        return h(ReasoningMessage, props.message);
      case MessageRole.Tool:
        return h(ToolMessage, props.message);
      case MessageRole.Activity:
        return h(ActivityMessage, { ...props.message, onInterruptResume: props.onInterruptResume });
      case MessageRole.Interrupt:
        return h(
          InterruptMessageRender,
          { ...props.message, onInterruptResume: props.onInterruptResume },
          slots.answeredQuestion
            ? {
                answeredQuestion: (slotProps: AnsweredQuestionSlotProps) => slots.answeredQuestion?.(slotProps),
              }
            : undefined,
        );
      case MessageRole.Loading:
        return h(LoadingMessage, props.message);
      default:
        return null;
    }
  });
</script>
