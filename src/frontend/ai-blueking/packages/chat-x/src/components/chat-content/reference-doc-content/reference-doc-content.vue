<template>
  <ActivityLayout v-model:collapsed="collapsed">
    <template #title>
      <span class="ai-activity-message-title-icon">
        <DocumentIcon style="font-size: 12px" />
      </span>
      <span class="ai-activity-message-title-text">
        {{ title }}
      </span>
    </template>
    <ReferenceContent :content="content || []" />
  </ActivityLayout>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { isEn } from '../../../common/lang';
  import { DocumentIcon } from '../../../icons/content';
  import ActivityLayout from '../activity-layout/activity-layout.vue';
  import ReferenceContent from '../reference-content/reference-content.vue';

  import type { ReferenceDocumentContent } from '../../../ag-ui/types/contents';

  const props = defineProps<{
    content?: ReferenceDocumentContent[];
  }>();
  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });
  const title = computed(() => {
    const length = props.content?.length ?? 0;
    return isEn ? `Reference ${length} documents as reference` : `引用 ${length} 篇资料作为参考`;
  });
</script>
