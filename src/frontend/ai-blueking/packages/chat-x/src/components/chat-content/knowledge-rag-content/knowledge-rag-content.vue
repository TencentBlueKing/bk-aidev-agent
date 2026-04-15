<template>
  <ActivityLayout v-model:collapsed="collapsed">
    <template #title>
      <span class="ai-activity-message-title-icon">
        <AiLoading v-if="isLoading" />
        <DocumentIcon
          v-else
          style="font-size: 12px"
        />
      </span>
      <span class="ai-activity-message-title-text">
        {{ title }}
      </span>
    </template>
    <div class="knowledge-rag-content">
      <MarkdownContent :content="content?.content || ''" />
    </div>
    <ReferenceContent :content="content?.referenceDocument || []" />
  </ActivityLayout>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { MessageStatus } from '../../../ag-ui/types/constants';
  import { DocumentIcon } from '../../../icons/content';
  import { t } from '../../../lang/lang';
  import AiLoading from '../../ai-loading/ai-loading.vue';
  import ActivityLayout from '../activity-layout/activity-layout.vue';
  import MarkdownContent from '../markdown-content/markdown-content.vue';
  import ReferenceContent from '../reference-content/reference-content.vue';

  import type { MessageStatus as MessageStatusType } from '../../../ag-ui/types/constants';
  import type { KnowledgeRagMessageContent } from '../../../ag-ui/types/contents';

  const props = defineProps<{
    content?: KnowledgeRagMessageContent;
    messageUid?: string;
    status?: MessageStatusType;
  }>();
  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });
  const isLoading = computed(() => {
    return props.status === MessageStatus.Pending || props.status === MessageStatus.Streaming;
  });
  const title = computed(() => {
    return isLoading.value ? t('检索中') : t('检索完成');
  });
</script>
<style lang="scss">
  .knowledge-rag-content {
    display: flex;
    flex-direction: column;
    padding: 6px 14px;
    margin-top: -16px;
    color: #979ba5;

    .ai-markdown-body {
      color: #979ba5;
    }
  }
</style>
