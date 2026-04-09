<template>
  <template
    v-for="item in links"
    :key="item.title"
  >
    <div class="ai-reference-item">
      <!-- <img
        v-if="item.icon"
        class="ai-reference-img"
        :src="item.icon"
      /> -->
      <DocLinkIcon color="#D66F6B" />
      <span
        class="ai-reference-item-title"
        @click="event => item.url && gotoLink(item.url, event)"
      >
        {{ item.title }}
      </span>
      <PreviewIcon
        v-if="item.url && item.originFileUrl"
        v-tippy="{ content: t('预览内容'), theme: 'ai-chat-box' }"
        @click="(event: MouseEvent) => item.url && gotoLink(item.url, event)"
      />
      <TargetIcon
        v-if="item.url && item.originFileUrl"
        v-tippy="{ content: t('跳转详情'), theme: 'ai-chat-box' }"
        @click="(event: MouseEvent) => item.originFileUrl && gotoLink(item.originFileUrl, event)"
      />
    </div>
  </template>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { directive as vTippy } from 'vue-tippy';

  import { DocLinkIcon, PreviewIcon, TargetIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  import type { ReferenceDocumentContent } from '../../../ag-ui/types/contents';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    content: ReferenceDocumentContent[];
  }>();
  const gotoLink = (url: string, event: MouseEvent) => {
    if (!url) return;
    event.stopPropagation();
    event.preventDefault();
    window.open(url, '_blank', 'noopener,noreferrer');
  };
  const links = computed(() => {
    return props.content
      .filter(item => item.name)
      .map(item => {
        return {
          title: item.name,
          url: item.url,
          originFileUrl: item.originFile,
        };
      });
  });
</script>
<style lang="scss">
  .ai-reference-item {
    display: flex;
    flex: 0 0 28px;
    align-items: center;
    height: 28px;
    padding: 0 12px;
    color: #3a84ff;

    &-title {
      flex: 1;
      width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 12px;
      white-space: nowrap;
    }

    &:hover {
      cursor: pointer;
      background: #eaebf0;

      .ai-common-icon {
        display: flex !important;
      }
    }

    .ai-common-icon:not(.ai-doc-link-icon) {
      display: none;
      flex: 0 0 14px;
      width: 13px;
      height: 14px;
      font-size: 14px;
      font-weight: 600;

      &:first-child {
        margin-left: auto;
      }

      &:last-child {
        margin-left: 12px;
      }
    }

    .ai-reference-img {
      flex: 0 0 14px;
      width: 14px;
      height: 14px;
      margin-right: 4px;
      margin-left: 12px;
      border-radius: 2px;
    }
  }
</style>
