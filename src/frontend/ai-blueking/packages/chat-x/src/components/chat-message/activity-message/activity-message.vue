<template>
  <component
    :is="activityComponent"
    v-if="activityComponent"
    v-model:collapsed="collapsed"
    :content="content"
    :message-uid="uid"
    :on-interrupt-resume="onInterruptResume"
    :status="status"
  />
</template>
<script setup lang="ts">
  import { type Component, computed } from 'vue';

  import { MessageContentType } from '../../../ag-ui/types/constants';
  import FlowAgentContent from '../../chat-content/flow-agent-content/flow-agent-content.vue';
  import KnowledgeRagContent from '../../chat-content/knowledge-rag-content/knowledge-rag-content.vue';
  import ReferenceDocContent from '../../chat-content/reference-doc-content/reference-doc-content.vue';

  import type { OnInterruptResume } from '../../../ag-ui/types/interrupt';
  import type { ActivityMessage } from '../../../ag-ui/types/messages';

  const activityComponentMap: Record<string, Component> = {
    [MessageContentType.FlowAgent]: FlowAgentContent,
    [MessageContentType.KnowledgeRag]: KnowledgeRagContent,
    [MessageContentType.ReferenceDocument]: ReferenceDocContent,
  };

  // onInterruptResume 仅 FlowAgent 子组件消费（节点重试 / 跳过）；其余活动组件忽略该 prop
  const props = defineProps<Partial<ActivityMessage> & { onInterruptResume?: OnInterruptResume }>();
  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });
  const activityComponent = computed(() => {
    return activityComponentMap[props.activityType ?? ''];
  });
</script>
