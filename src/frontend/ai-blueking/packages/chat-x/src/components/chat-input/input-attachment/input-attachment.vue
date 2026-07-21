<template>
  <div class="ai-input-attachment">
    <div class="ai-input-attachment-default">
      <slot name="default" />
    </div>
    <div class="ai-input-attachment-before-send">
      <slot name="before-send" />
    </div>
    <slot name="send-icon">
      <div
        class="send-message-icon"
        :class="[
          messageState && `send-message-icon__${messageState}`,
          { 'send-message-icon__disabled': sendDisabledTip },
        ]"
        @click="handleSendMessage"
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
            content: sendDisabledTip || (props.messageState === MessageStatus.Disabled ? undefined : t('发送')),
            theme: 'ai-chat-box',
            offset: [0, 16],
          }"
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
    sendDisabledTip?: string;
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
      props.sendDisabledTip ||
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
    width: 100%;
    height: 40px;
    padding: 0 12px;

    &-default {
      display: flex;
      flex: 1;
      gap: 8px;
      align-items: center;
      width: 1px;
      height: 100%;
    }

    &-before-send {
      display: flex;
      flex: 0 0 140px;
      align-items: center;
      justify-content: center;
      width: fit-content;
      height: 100%;
    }

    .send-message-icon {
      right: 12px;
      display: flex;
      flex: 0 0 32px;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      font-size: 16px;
      color: #fff;
      cursor: pointer;
      background: #3a84ff;
      border-radius: 8px;

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
