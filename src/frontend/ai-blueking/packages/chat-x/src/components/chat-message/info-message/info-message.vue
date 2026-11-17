<template>
  <div
    class="ai-info-message"
    :class="{ 'is-fork': forkInfo }"
  >
    <!-- 分支会话的分叉点：设计稿为图标 + 蓝色文案，点击切回来源会话 -->
    <div
      v-if="forkInfo"
      class="ai-info-message-body"
    >
      <div
        class="ai-info-message-fork"
        role="button"
        tabindex="0"
        @click="handleForkClick"
        @keydown.enter="handleForkClick"
      >
        <component
          :is="ForkIcon"
          class="ai-info-message-fork-icon"
        />
        <span class="ai-info-message-fork-text">{{ t('从其他会话中继续') }}</span>
      </div>
    </div>
    <div
      v-else
      class="ai-info-message-body"
    >
      <div
        v-for="(text, index) in Array.isArray(content) ? content : [content]"
        :key="index"
        class="ai-info-message-content"
      >
        {{ text }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { ForkIcon } from '../../../icons/tools';
  import { t } from '../../../lang/lang';

  import type { InfoMessage, MessageForkInfo } from '../../../ag-ui/types/messages';

  const props = defineProps<
    Partial<InfoMessage> & {
      onForkSourceClick?: (forkInfo: MessageForkInfo) => void;
    }
  >();

  const forkInfo = computed(() => props.property?.fork_info);

  const handleForkClick = () => {
    if (!forkInfo.value) return;
    props.onForkSourceClick?.(forkInfo.value);
  };
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-info-message {
    display: flex;
    align-items: center;
    width: 100%;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    color: variables.$color-text-secondary;

    // 左右虚线夹中间文案，整块居中占位，避免 height:0 溢出被遮挡
    &::before,
    &::after {
      flex: 1;
      min-width: 16px;
      content: '';
      border-bottom: 1px dashed variables.$color-border;
    }

    &-body {
      display: flex;
      flex-shrink: 0;
      flex-direction: column;
      gap: 4px;
      align-items: center;
      max-width: calc(100% - 32px);
      padding: 0 12px;
      text-align: center;
    }

    &-content {
      max-width: 100%;
      word-break: break-all;
    }

    &-fork {
      display: flex;
      gap: 4px;
      align-items: center;
      cursor: pointer;

      &-icon {
        flex-shrink: 0;
        font-size: 14px;
        color: variables.$color-text-secondary;
      }

      &-text {
        color: variables.$color-primary;
      }
    }

    // 设计稿：分叉点分隔线与中间内容间距 8px
    &.is-fork &-body {
      padding: 0 8px;
    }
  }
</style>
