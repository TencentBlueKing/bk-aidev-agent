<template>
  <div class="ai-reasoning-message">
    <div
      class="ai-reasoning-message-title"
      :class="{
        'ai-reasoning-message-title-collapsed': collapsed,
        'is-thinking': status === MessageStatus.Pending || status === MessageStatus.Streaming,
        'is-complete': status === MessageStatus.Complete || status === MessageStatus.Success,
        'is-error': status === MessageStatus.Error,
      }"
      @click="collapsed = !collapsed"
    >
      <span
        v-if="status === MessageStatus.Pending || status === MessageStatus.Streaming"
        class="ai-reasoning-message-title-icon"
      >
        <AiLoading />
      </span>
      <span class="ai-reasoning-message-title-text">
        {{ reasoningTitle }}
      </span>
      <!-- <template v-if="status === MessageStatus.Pending || status === MessageStatus.Streaming">
        <ContentLoadingIcon
          v-for="i in 3"
          :key="i"
          :class="`loading-status-${i}`"
        />
      </template> -->
      <span
        class="ai-reasoning-message-title-icon collapsed-icon"
        :class="{ 'is-collapsed': collapsed }"
      >
        <CollapsedIcon />
      </span>
    </div>
    <div
      v-show="!collapsed"
      class="ai-reasoning-message-content"
    >
      <template v-if="status === MessageStatus.Error">
        <CommonErrorContent :content="content?.join('\n') || ''" />
      </template>
      <template v-else>
        <template
          v-for="item in Array.isArray(content) ? content : [content]"
          :key="item"
        >
          <MarkdownContent :content="item" />
        </template>
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, nextTick, watch } from 'vue';

  import { MessageStatus } from '../../../ag-ui/types/constants';
  import { CollapsedIcon } from '../../../icons/messages';
  import { t } from '../../../lang/lang';
  import { formatDuration } from '../../../utils/utils';
  import AiLoading from '../../ai-loading/ai-loading.vue';
  import CommonErrorContent from '../../chat-content/common-error-content/common-error-content.vue';
  import MarkdownContent from '../../chat-content/markdown-content/markdown-content.vue';

  import type { ReasoningMessage } from '../../../ag-ui/types/messages';

  const props = defineProps<Partial<ReasoningMessage>>();

  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });

  // 监听 duration 变化，如果 duration 不为空，则停止监听并折叠
  const { stop } = watch(
    () => props.duration,
    async duration => {
      if (duration) {
        collapsed.value = true;
        await nextTick();
        stop?.();
      }
    },
    {
      immediate: true,
    },
  );

  const reasoningTitle = computed(() => {
    switch (props.status) {
      case MessageStatus.Pending:
        return t('思考中');
      case MessageStatus.Success:
      case MessageStatus.Complete:
        return t('已思考完成') + (props.duration ? ` (${t('耗时')} ：${formatDuration(props.duration)})` : '');
      case MessageStatus.Error:
        return t('思考失败');
      default:
        return t('思考中');
    }
  });
</script>
<style lang="scss">
  @use 'sass:list';
  @use '../../../styles/variables.scss' as variables;

  .ai-reasoning-message {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12px;

    &-title {
      display: flex;
      align-items: center;
      width: fit-content;
      max-width: 100%;
      height: 28px;
      padding: 0 10px;
      color: #4d4f56;
      background: #f0f1f5;
      border-radius: 4px;

      &.is-error {
        background-color: #fff0f0;

        .ai-thinking-icon {
          color: #ea3636;
        }
      }

      &-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        margin-right: 4px;
        font-size: 18px;

        &.ai-thinking-icon {
          transform: rotate(90deg);
        }

        &.collapsed-icon {
          width: 12px;
          height: 12px;
          margin-right: 0;
          margin-left: 4px;
          font-size: 10px;
          color: #4d4f56;
          transform: rotate(90deg);
        }

        &.is-collapsed {
          transform: rotate(-90deg);
        }
      }

      &-text {
        display: inline;
        flex: 1;
        width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &:hover {
        cursor: pointer;
        background: #eaebf0;
      }
    }

    &-content {
      display: flex;
      flex-direction: column;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 2px;

      .ai-markdown-body {
        color: #979ba5;
      }
    }
  }
</style>
