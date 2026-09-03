<template>
  <div class="ai-collapsible-content">
    <div
      class="ai-collapsible-content-body"
      :class="{ 'is-collapsed': isCollapsed }"
      :style="isCollapsed ? { maxHeight: `${maxHeight}px` } : undefined"
    >
      <!-- 折叠由外层 max-height 实现，真实高度始终从这一层测量 -->
      <div ref="measureRef">
        <slot />
      </div>
    </div>
    <div
      v-if="isOverflowing"
      class="ai-collapsible-content-toggle"
      @click="isExpanded = !isExpanded"
    >
      <span>{{ isExpanded ? t('收起') : t('显示更多') }}</span>
      <ArrowLeftIcon
        class="ai-collapsible-content-toggle-icon"
        :class="{ 'is-expanded': isExpanded }"
      />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

  import { ArrowLeftIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  const props = withDefaults(
    defineProps<{
      /** 折叠态下内容区的最大高度，超出才出现展开按钮 */
      maxHeight?: number;
    }>(),
    {
      maxHeight: 200,
    },
  );

  /** 展开态可由外部控制，便于「全部展开」这类批量操作 */
  const isExpanded = defineModel<boolean>('expanded', { default: false });

  const measureRef = useTemplateRef<HTMLElement>('measureRef');
  const contentHeight = shallowRef(0);
  const isOverflowing = computed(() => contentHeight.value > props.maxHeight);
  const isCollapsed = computed(() => isOverflowing.value && !isExpanded.value);

  // 内容可能因为图片加载、流式追加或窗口缩放而变高，用 ResizeObserver 持续跟踪而不是只测一次
  let observer: null | ResizeObserver = null;
  const disconnect = () => {
    observer?.disconnect();
    observer = null;
  };
  watch(
    measureRef,
    element => {
      disconnect();
      if (!element || typeof ResizeObserver === 'undefined') {
        return;
      }
      observer = new ResizeObserver(([entry]) => {
        contentHeight.value = entry.contentRect.height;
      });
      observer.observe(element);
    },
    // 模板 ref 在渲染后才赋值，pre flush 会错过首次挂载
    { flush: 'post' },
  );
  onUnmounted(disconnect);
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-collapsible-content {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;

    &-body {
      &.is-collapsed {
        overflow: hidden;
      }
    }

    // 设计稿标注：默认 #979ba5，hover 变为 #4d4f56
    &-toggle {
      display: flex;
      gap: 4px;
      align-items: center;
      align-self: flex-start;
      margin-top: 8px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: variables.$color-text-secondary;
      cursor: pointer;

      &:hover {
        color: variables.$color-text;
      }

      &-icon {
        flex: 0 0 12px;
        width: 12px;
        height: 12px;
        font-size: 12px;
        transform: rotate(-90deg);
        transition: transform 0.2s ease-in-out;

        path {
          stroke-width: 100;
        }

        &.is-expanded {
          transform: rotate(90deg);
        }
      }
    }
  }
</style>
