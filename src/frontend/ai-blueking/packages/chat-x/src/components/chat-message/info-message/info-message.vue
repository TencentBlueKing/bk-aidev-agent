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
        :aria-busy="forkLoading || undefined"
        class="ai-info-message-fork"
        :class="{ 'is-clickable': forkClickable, 'is-loading': forkLoading }"
        :role="forkClickable ? 'button' : undefined"
        :tabindex="forkClickable ? 0 : undefined"
        @click="handleForkClick"
        @keydown.enter="handleForkClick"
      >
        <Loading
          v-if="forkLoading"
          class="ai-info-message-fork-loading"
          mode="spin"
          size="mini"
          theme="primary"
        />
        <component
          :is="ForkIcon"
          v-else
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
  import { computed, shallowRef } from 'vue';

  import { Loading } from 'bkui-vue';

  import { ForkIcon } from '../../../icons/tools';
  import { t } from '../../../lang/lang';
  import { isPromiseLike } from '../../../utils/utils';

  import type { InfoMessage, MessageForkInfo } from '../../../ag-ui/types/messages';

  const props = defineProps<
    Partial<InfoMessage> & {
      onForkSourceClick?: (forkInfo: MessageForkInfo) => Promise<void> | void;
    }
  >();

  const forkInfo = computed(() => props.property?.fork_info);
  const forkLoading = shallowRef(false);
  const forkClickable = computed(() => !!forkInfo.value && !!props.onForkSourceClick && !forkLoading.value);

  const handleForkClick = async () => {
    if (!forkClickable.value || !forkInfo.value || forkLoading.value) return;
    const result = props.onForkSourceClick?.(forkInfo.value);
    if (!isPromiseLike(result)) return;

    forkLoading.value = true;
    try {
      await result;
    } finally {
      forkLoading.value = false;
    }
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

    // 左右虚线夹中间文案：自定义虚线（4px 实段 + 4px 空隙）比默认 dashed 更疏
    &::before,
    &::after {
      flex: 1;
      align-self: center;
      min-width: 16px;
      height: 1px;
      content: '';
      background-image: linear-gradient(
        to right,
        variables.$color-border 0,
        variables.$color-border 4px,
        transparent 4px,
        transparent 8px
      );
      background-repeat: repeat-x;
      background-position: center;
      background-size: 8px 1px;
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

      &.is-clickable {
        cursor: pointer;
      }

      &.is-loading {
        cursor: default;
      }

      &-loading {
        flex-shrink: 0;
      }

      &-icon {
        flex-shrink: 0;
        font-size: 14px;
        color: variables.$color-text-secondary;
      }

      &-text {
        color: variables.$color-primary;
      }

      // hover：文案加深为 #1768ef（与输入区快捷入口等交互蓝一致）
      &.is-clickable:hover .ai-info-message-fork-text {
        color: #1768ef;
      }
    }

    // 设计稿：分叉点分隔线与中间内容间距 8px
    &.is-fork &-body {
      padding: 0 8px;
    }
  }
</style>
