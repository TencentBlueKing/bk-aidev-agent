<template>
  <slot
    v-bind="{
      content: props.content,
    }"
  >
    <component :is="contentComponent" />
  </slot>
</template>
<script setup lang="ts" generic="T extends ContentType">
  import { type VNode, computed, h, useSlots } from 'vue';

  import { MessageContentType, MessageStatus } from '../../../ag-ui/types';
  import MarkdownContent from '../markdown-content/markdown-content.vue';
  import ReferenceContent from '../reference-content/reference-content.vue';

  import type { ContentMap, ContentType, ReferenceDocumentContent } from '../../../ag-ui/types/contents';
  import type { Token } from '../../../markdown-it';
  defineSlots<{
    codeHeader: (props: { language: string; token: Token[] }) => null | undefined | VNode;
    default: (props: { content: ContentMap[T] }) => null | undefined | VNode;
  }>();
  const slots = useSlots();
  const props = defineProps<{
    content: ContentMap[T];
    status?: MessageStatus;
    type?: T;
  }>();

  const contentComponent = computed(() => {
    if (typeof props.content === 'string' || props.type === MessageContentType.Text) {
      return h(
        MarkdownContent,
        { content: props.content as string, status: props.status },
        {
          codeHeader: (slotProps: { language: string; token: Token[] }) => {
            return slots.codeHeader?.(slotProps) ?? undefined;
          },
        },
      );
    }
    if (typeof props.content === 'object' && Array.isArray(props.content)) {
      return h(ReferenceContent, { content: props.content as ReferenceDocumentContent[] });
    }
    // if (props.type === MessageContentType.Function) {
    //   return h(MarkdownContent, {
    //     content: props.content as string,
    //   });
    // }
    // if (props.type === MessageContentType.Thinking) {
    //   return h(ThinkingContent, props.content as ThinkingMessageContent);
    // }
    // if (props.type === MessageContentType.ReferenceDocument) {
    //   return h(ReferenceContent, props.content as ReferenceDocumentMessageContent);
    // }
    return undefined;
  });
</script>
