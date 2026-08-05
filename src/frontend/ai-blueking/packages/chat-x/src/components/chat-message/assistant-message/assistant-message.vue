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
    <template v-if="toolCalls && toolCalls.length > 0">
      <template
        v-for="toolCall in toolCalls"
        :key="toolCall.id"
      >
        <ToolCallRender
          :status="toolCall.toolMessage?.status ?? status"
          :tool-call="toolCall"
        />
      </template>
    </template>
    <!-- 生成文件产物 -->
    <MessageArtifacts
      v-if="artifacts && artifacts.length > 0"
      :artifacts="artifacts"
      :message-uid="messageUid"
    />
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { MessageContentType } from '../../../ag-ui/types/constants';
  import ContentRender from '../../chat-content/content-render/content-render.vue';
  import ToolCallRender from '../../tool-call/toolcall-render/toolcall-render.vue';
  import MessageArtifacts from './message-artifacts/message-artifacts.vue';

  import type { AssistantMessage } from '../../../ag-ui/types/messages';

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
  // 唯一消息标识：优先 uid，回退 id，供文件产物命中唯一文件与「在对话中定位」
  const messageUid = computed(() => props.uid ?? (props.id != null ? String(props.id) : ''));
</script>

<style lang="scss">
  .ai-assistant-message {
    display: flex;
    flex-direction: column;
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
      margin-bottom: 12px;
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
