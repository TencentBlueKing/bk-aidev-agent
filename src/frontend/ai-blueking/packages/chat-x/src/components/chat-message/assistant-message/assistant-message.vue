<template>
  <div class="ai-assistant-message">
    <div class="ai-assistant-message-content">
      <slot
        v-bind="{
          content,
        }"
      >
        <ContentRender
          :content="content || ''"
          :status="status"
          :type="MessageContentType.Text"
        />
      </slot>
    </div>
    <template v-if="toolCalls && toolCalls.length > 0">
      <template
        v-for="toolCall in toolCalls"
        :key="toolCall.id"
      >
        <ToolCallRender
          :status="status"
          :tool-call="toolCall"
        />
      </template>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { MessageContentType } from '../../../ag-ui/types/constants';
  import ContentRender from '../../chat-content/content-render/content-render.vue';
  import ToolCallRender from '../../tool-call/toolcall-render/toolcall-render.vue';

  import type { AssistantMessage } from '../../../ag-ui/types/messages';
  defineProps<Partial<AssistantMessage>>();
</script>

<style lang="scss">
  .ai-assistant-message {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    width: 100%;
    font-size: 12px;
    line-height: 1.5;
    color: #313238;

    &-content {
      display: flex;
      flex-direction: column;
      gap: 16px;
      width: 100%;
    }

    &-tools {
      display: flex;
      visibility: hidden;
      align-items: center;
      width: 100%;
      margin-bottom: 12px;
    }

    &:hover {
      .assistant-message-tools {
        visibility: visible;
      }
    }
  }
</style>
