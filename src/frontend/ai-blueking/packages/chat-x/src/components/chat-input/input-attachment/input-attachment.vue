<template>
  <div class="ai-input-attachment">
    <slot name="default" />
    <slot name="send-icon">
      <div
        class="send-message-icon"
        :class="{ ['send-message-icon__' + messageState]: true }"
      >
        <LoadingMessageIcon
          v-if="
            messageState === MessageStatus.Streaming ||
            messageState === MessageStatus.Pending ||
            messageState === MessageStatus.Fetching
          "
          v-tippy="{ ...tippyOptions, content: t('停止'), theme: 'ai-chat-box', offset: [0, 16] }"
          @click="handleStopSending"
        />
        <SendMessageIcon
          v-else
          v-tippy="{
            ...tippyOptions,
            content: props.messageState === MessageStatus.Disabled ? undefined : t('发送'),
            theme: 'ai-chat-box',
            offset: [0, 16],
          }"
          @click="handleSendMessage"
        />
      </div>
    </slot>
  </div>
</template>

<script setup lang="ts">
  import { directive as vTippy } from 'vue-tippy';

  import { MessageStatus } from '../../../ag-ui/types';
  import { LoadingMessageIcon, SendMessageIcon } from '../../../icons/messages';
  import { t } from '../../../lang/lang';

  import type { AITippyProps } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    messageState?: MessageStatus;
    tippyOptions?: AITippyProps;
  }>();
  const emit = defineEmits<{
    (e: 'sendMessage'): void;
    (e: 'stopSending'): void;
  }>();
  const handleStopSending = () => {
    emit('stopSending');
  };
  const handleSendMessage = () => {
    if (
      props.messageState === MessageStatus.Disabled ||
      props.messageState === MessageStatus.Pending ||
      props.messageState === MessageStatus.Streaming
    ) {
      return;
    }
    emit('sendMessage');
  };
</script>

<style lang="scss">
  .ai-input-attachment {
    display: flex;
    flex: 0 0 40px;
    gap: 6px;
    align-items: center;
    height: 40px;
    padding: 0 12px;

    .send-message-icon {
      display: flex;
      flex: 0 0 24px;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      margin-left: auto;
      font-size: 14px;
      color: #fff;
      cursor: pointer;
      background: #3a84ff;
      border-radius: 4px;

      // &__active {
      //   color: #fff;
      //   cursor: pointer;
      //   background: #3a84ff;
      // }

      &__disabled {
        color: #c4c6cc;
        cursor: not-allowed;
        background: #f0f1f5;
      }

      &__streaming,
      &__pending {
        color: #fff;
        cursor: pointer;
        background: #3a84ff;
      }
    }
  }
</style>
