<template>
  <component
    :is="activityComponent"
    v-if="activityComponent"
    v-model:collapsed="collapsed"
    :content="content"
    :status="status"
  />
</template>
<script setup lang="ts">
  import { type Component, computed } from 'vue';

  import { MessageContentType } from '../../../ag-ui/types/constants';
  import FlowAgentContent from '../../chat-content/flow-agent-content/flow-agent-content.vue';
  import KnowledgeRagContent from '../../chat-content/knowledge-rag-content/knowledge-rag-content.vue';
  import ReferenceDocContent from '../../chat-content/reference-doc-content/reference-doc-content.vue';

  import type { ActivityMessage } from '../../../ag-ui/types/messages';

  const activityComponentMap: Record<string, Component> = {
    [MessageContentType.FlowAgent]: FlowAgentContent,
    [MessageContentType.KnowledgeRag]: KnowledgeRagContent,
    [MessageContentType.ReferenceDocument]: ReferenceDocContent,
  };

  const props = defineProps<Partial<ActivityMessage>>();
  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });
  const activityComponent = computed(() => {
    return activityComponentMap[props.activityType ?? ''];
  });
</script>
