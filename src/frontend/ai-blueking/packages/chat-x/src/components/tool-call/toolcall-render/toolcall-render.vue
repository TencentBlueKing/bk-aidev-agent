<template>
  <div class="ai-toolcall-render">
    <div
      class="ai-toolcall-render-header"
      :class="`toolcall-status-${status}`"
      @click="handleToggle"
    >
      <ArrowRightIcon :class="{ 'is-collapsed': effectiveCollapsed }" />
      {{ toolCall?.function.mcpName ? t('调用 MCP：') : t('调用工具：') }}
      <span
        v-overflow-tips="{ ...commonTippyOptions, text: toolTitle, appendTo: 'parent' }"
        class="toolcall-header-title"
      >
        <HighlightKeyword :text="toolTitle" />
      </span>
      <span class="toolcall-status-title">
        <Loading
          v-if="status === MessageStatus.Pending || status === MessageStatus.Streaming"
          mode="spin"
          size="mini"
          theme="primary"
        />
        <BkFlowSuccessIcon
          v-else-if="
            [MessageStatus.Success, MessageStatus.Complete, MessageStatus.Completed].includes(status as MessageStatus)
          "
        />
        <BkFlowFailedIcon v-else-if="status === MessageStatus.Error" />

        <HighlightKeyword :text="statusTitle" />
        <span
          v-if="durationDisplay"
          class="toolcall-duration"
        >
          ({{ durationDisplay }})
        </span>
      </span>
    </div>
    <div
      v-show="!effectiveCollapsed"
      class="ai-toolcall-render-content"
    >
      <DescPanel
        :desc="toolCall?.function.description"
        :title="t('描述')"
      />
      <DescPanel
        :desc="toolCall?.function.arguments"
        :title="t('参数')"
      />
      <ToolMessage
        v-if="toolCall?.toolMessage"
        v-bind="toolCall.toolMessage"
      />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, shallowRef } from 'vue';

  import { Loading } from 'bkui-vue';

  import { MessageStatus } from '../../../ag-ui/types/constants';
  import { useCommonTippyInject, useKeywordMatch } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives';
  import { BkFlowFailedIcon, BkFlowSuccessIcon } from '../../../icons';
  import { ArrowRightIcon } from '../../../icons/content';
  import { t } from '../../../lang/lang';
  import { formatDuration } from '../../../utils/utils';
  import ToolMessage from '../../chat-message/tool-message/tool-message.vue';
  import HighlightKeyword from '../../highlight-keyword/highlight-keyword';
  import DescPanel from '../desc-panel/desc-panel.vue';

  import type { ToolCall } from '../../../ag-ui/types/messages';
  const props = defineProps<{
    duration?: number;
    status?: MessageStatus;
    toolCall?: ToolCall;
  }>();
  const collapsed = shallowRef<boolean | null>(true);
  const superCollapsed = shallowRef<boolean | null>(null);
  const commonTippyOptions = useCommonTippyInject();
  const { keywordMatched, keyword } = useKeywordMatch(() => [
    props.toolCall?.function.name,
    props.toolCall?.function.mcpName,
    props.toolCall?.function.description,
    props.toolCall?.function.arguments,
    props.toolCall?.id,
  ]);

  const effectiveCollapsed = computed(() => {
    if (superCollapsed.value !== null) {
      return superCollapsed.value;
    }
    if (keyword?.value?.trim()) {
      return !keywordMatched.value;
    }
    return collapsed.value;
  });

  function handleToggle() {
    collapsed.value = !effectiveCollapsed.value;
    superCollapsed.value = collapsed.value;
  }

  const toolTitle = computed(() => {
    const mcpName = props.toolCall?.function.mcpName || '';
    const name = props.toolCall?.function.name || props.toolCall?.id || '';
    if (!mcpName) {
      return name;
    }
    return `${mcpName} / ${name}`;
  });
  const statusTitle = computed(() => {
    switch (props.status) {
      default:
      case MessageStatus.Pending:
        return t('调用中');
      case MessageStatus.Completed:
      case MessageStatus.Complete:
      case MessageStatus.Success:
        return t('调用成功');
      case MessageStatus.Error || props.toolCall?.toolMessage?.error:
        return t('调用失败');
    }
  });

  const durationDisplay = computed(() => {
    const duration = props.duration || props.toolCall?.toolMessage?.duration;
    return duration ? formatDuration(duration) : '';
  });
</script>
<style lang="scss">
  @use 'sass:list';
  @use '../../../styles/variables.scss' as variables;

  .ai-toolcall-render {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
    margin-bottom: 8px;
    color: #4d4f56;

    &-header {
      display: flex;
      flex: 0 0 40px;
      align-items: center;
      height: 40px;
      padding: 0 12px;
      font-weight: bold;
      cursor: pointer;
      border: 1px solid transparent;
      border-radius: 4px;

      @each $status, $color in variables.$toolcallStatusMap {
        &.toolcall-status-#{$status} {
          background-color: list.nth($color, 1);
          border-color: list.nth($color, 2);
        }
      }

      .ai-common-icon {
        width: 14px;
        height: 14px;
      }

      .ai-arrow-right-icon {
        margin-right: 6px;
        cursor: pointer;
        transform: rotate(90deg);
        transition: transform 0.2s ease-in-out;

        &:hover {
          color: #3a84ff;
        }

        &.is-collapsed {
          transform: rotate(0deg);
        }
      }

      .toolcall-header-title {
        flex: 1;
        margin-left: 4px;
        overflow: hidden;
        text-overflow: ellipsis;
        font-weight: normal;
        color: #313238;
        white-space: nowrap;
      }

      .toolcall-status-title {
        display: flex;
        gap: 6px;
        align-items: center;
        margin-left: 4px;
        font-weight: normal;
        color: #313238;
      }

      .toolcall-duration {
        font-weight: normal;
        color: #979ba5;
      }
    }

    &-content {
      display: flex;
      flex-direction: column;
      background-color: #f5f7fa;
      border-radius: 2px;
    }
  }
</style>
