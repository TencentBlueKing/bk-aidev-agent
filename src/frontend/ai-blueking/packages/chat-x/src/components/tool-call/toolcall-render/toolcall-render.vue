<template>
  <div class="ai-toolcall-render">
    <div
      class="ai-toolcall-render-header"
      :class="{ 'is-expanded': !effectiveCollapsed }"
      @click="handleToggle"
    >
      <ToolCallIcon />
      <!-- 前缀、工具名与状态同处一个内联文本块，保证「（成功，…）」紧贴工具名，与设计稿一致 -->
      <span
        v-overflow-tips="{ ...commonTippyOptions, text: headerText, appendTo: 'parent' }"
        class="toolcall-header-text"
      >
        <span
          class="toolcall-header-title"
          :class="{ 'is-loading': isPending }"
          >{{ isPending ? pendingLabel : callTypeLabel }} <HighlightKeyword :text="toolTitle" /></span
        ><span
          v-if="statusText"
          class="toolcall-header-status"
          >&nbsp;(&nbsp;<span
            class="toolcall-header-result"
            :class="isError ? 'is-error' : 'is-success'"
            >{{ statusText }}</span
          ><template v-if="durationDisplay">，{{ t('耗时') }}：{{ durationDisplay }}</template
          >&nbsp;)</span
        >
      </span>
      <ChevronRightIcon
        v-if="!isPending"
        :class="{ 'is-expanded': !effectiveCollapsed }"
      />
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

  import { MessageStatus } from '../../../ag-ui/types/constants';
  import { useCommonTippyInject, useKeywordMatch } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives';
  import { ChevronRightIcon, ToolCallIcon } from '../../../icons';
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

  /** 成功态：Success / Complete / Completed 归一 */
  const isSuccess = computed(() =>
    [MessageStatus.Complete, MessageStatus.Completed, MessageStatus.Success].includes(props.status as MessageStatus),
  );
  const isError = computed(() => props.status === MessageStatus.Error || !!props.toolCall?.toolMessage?.error);
  /** 既非成功也非失败时统一视为进行中，与旧 default 分支行为保持一致 */
  const isPending = computed(() => !isSuccess.value && !isError.value);

  /** 优先取 function.type；旧数据无 type 时按 mcpName 兼容判定为 MCP */
  const callType = computed(() => {
    const fn = props.toolCall?.function;
    return fn?.type ?? (fn?.mcpName ? 'mcp' : 'function');
  });

  /** 结束态前缀：Skill 用「读取」，工具 / MCP 仍用「调用」 */
  const callTypeLabel = computed(() => {
    if (callType.value === 'skill') {
      return t('读取 Skill');
    }
    return callType.value === 'mcp' ? t('调用 MCP') : t('调用工具');
  });

  /** 进行中前缀：Skill 显示「正在读取」，其余保持「正在调用」 */
  const pendingLabel = computed(() => (callType.value === 'skill' ? t('正在读取') : t('正在调用')));

  const toolTitle = computed(() => {
    const fn = props.toolCall?.function;
    const mcpName = fn?.mcpName || '';
    const name = fn?.name || props.toolCall?.id || '';
    if (!mcpName) {
      return name;
    }
    return `${mcpName} / ${name}`;
  });

  const statusText = computed(() => {
    if (isError.value) {
      return t('失败');
    }
    return isSuccess.value ? t('成功') : '';
  });

  const durationDisplay = computed(() => {
    const duration = props.duration || props.toolCall?.toolMessage?.duration;
    return duration ? formatDuration(duration) : '';
  });

  /** 溢出提示所需的完整纯文本 */
  const headerText = computed(() => {
    const prefix = `${isPending.value ? pendingLabel.value : callTypeLabel.value} ${toolTitle.value}`;
    if (!statusText.value) {
      return prefix;
    }
    const durationPart = durationDisplay.value ? `，${t('耗时')}：${durationDisplay.value}` : '';
    return `${prefix}（${statusText.value}${durationPart}）`;
  });
</script>
<style lang="scss">
  @keyframes ai-toolcall-shimmer {
    from {
      background-position: 100% 0;
    }

    to {
      background-position: -100% 0;
    }
  }

  .ai-toolcall-render {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
    font-size: var(--ai-font-size, 12px);
    line-height: 20px;

    &-header {
      display: flex;
      gap: 4px;
      align-items: center;
      width: 100%;
      color: #979ba5;
      cursor: pointer;

      .ai-toolcall-icon {
        flex-shrink: 0;
        width: 16px;
        height: 16px;
      }

      .ai-chevron-right-icon {
        flex-shrink: 0;
        width: 10px;
        height: 10px;
        transition: transform 0.2s ease-in-out;

        &.is-expanded {
          color: #313238;
          transform: rotate(90deg);
        }
      }

      .toolcall-header-text {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      // 进行中态的文字 loading：渐变光带循环扫过
      .toolcall-header-title.is-loading {
        background: linear-gradient(90deg, #979ba5 0%, #e0e2e9 50%, #979ba5 100%);
        background-clip: text;
        background-size: 200% 100%;
        animation: ai-toolcall-shimmer 1.8s linear infinite;
        -webkit-text-fill-color: transparent;

        @media (prefers-reduced-motion: reduce) {
          animation: none;
        }
      }

      // 仅状态词着色，括号与耗时保持弱显示
      .toolcall-header-result {
        &.is-success {
          color: #2caf5e;
        }

        &.is-error {
          color: #ea3636;
        }
      }

      // 展开态与 hover 态：图标与工具名变为主文本色，作为可点击/已展开的视觉提示
      &.is-expanded,
      &:hover {
        .ai-toolcall-icon,
        .toolcall-header-title:not(.is-loading) {
          color: #313238;
        }
      }
    }

    &-content {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
  }
</style>
