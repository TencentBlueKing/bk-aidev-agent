<template>
  <div class="ai-assistant-message">
    <!-- 内容 -->
    <div
      v-if="content"
      class="ai-assistant-message-content"
    >
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
    <!-- 工具调用 -->
    <div
      v-if="toolCalls && toolCalls.length > 0"
      class="ai-assistant-message-toolcalls"
    >
      <ToolCallRender
        v-for="toolCall in toolCalls"
        :key="toolCall.id"
        :status="resolveToolCallStatus(toolCall)"
        :tool-call="toolCall"
      />
    </div>
    <!-- 生成文件产物 -->
    <MessageArtifacts
      v-if="artifacts && artifacts.length > 0"
      :artifacts="artifacts"
    />
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { MessageContentType, MessageStatus } from '../../../ag-ui/types/constants';
  import ContentRender from '../../chat-content/content-render/content-render.vue';
  import ToolCallRender from '../../tool-call/toolcall-render/toolcall-render.vue';
  import MessageArtifacts from './message-artifacts/message-artifacts.vue';

  import type { AssistantMessage, ToolCall } from '../../../ag-ui/types/messages';

  // 本地 interface：content 用字面量 string，避免 Vue 将泛型 BaseMessage.content 推断为 Object
  interface AssistantMessageProps {
    content?: string;
    id?: AssistantMessage['id'];
    messageId?: AssistantMessage['messageId'];
    name?: AssistantMessage['name'];
    property?: AssistantMessage['property'];
    role?: AssistantMessage['role'];
    status?: AssistantMessage['status'];
    toolCalls?: AssistantMessage['toolCalls'];
    uid?: AssistantMessage['uid'];
  }
  const props = defineProps<AssistantMessageProps>();
  const artifacts = computed(() => props.property?.artifacts);

  /**
   * 工具调用状态：
   * 无结果时进行中（用户已停止则为停止）；结果带 error 为失败；否则取结果状态，缺省沿用本消息状态
   */
  const resolveToolCallStatus = (toolCall: ToolCall): MessageStatus | undefined => {
    const { toolMessage } = toolCall;
    if (!toolMessage) {
      return props.status === MessageStatus.Stop ? MessageStatus.Stop : MessageStatus.Pending;
    }
    if (toolMessage.error) {
      return MessageStatus.Error;
    }
    return toolMessage.status ?? props.status;
  };
</script>

<style lang="scss">
  .ai-assistant-message {
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
    width: 100%;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    color: #313238;

    &-content {
      display: flex;
      flex-direction: column;
      gap: 16px;
      width: 100%;
    }

    // 多条工具调用之间保持 8px 间距（设计稿），不受外层 12px 间距影响
    &-toolcalls {
      display: flex;
      flex-direction: column;
      gap: 8px;
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
