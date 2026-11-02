<template>
  <div
    class="ai-reasoning-effort-slider"
    :class="{ 'is-disabled': disabled, 'is-static': isSingle }"
  >
    <div
      ref="trackRef"
      class="ai-reasoning-effort-slider-track"
      @pointercancel="handlePointerCancel"
      @pointerdown="handlePointerDown"
      @pointermove="handlePointerMove"
      @pointerup="handlePointerUp"
    >
      <span class="ai-reasoning-effort-slider-segments">
        <span
          v-for="segment in segmentCount"
          :key="segment"
          class="ai-reasoning-effort-slider-segment"
          :class="{ 'is-active': segment <= activeSegmentCount }"
        />
      </span>
      <span
        :aria-disabled="!interactive"
        :aria-label="t('思考深度')"
        :aria-valuemax="Math.max(options.length - 1, 0)"
        aria-valuemin="0"
        :aria-valuenow="Math.max(displayIndex, 0)"
        :aria-valuetext="currentOption?.value"
        class="ai-reasoning-effort-slider-thumb"
        role="slider"
        :style="{ '--ai-reasoning-effort-thumb-ratio': thumbRatio }"
        :tabindex="interactive ? 0 : -1"
        @keydown="handleKeydown"
      />
    </div>
    <span
      class="ai-reasoning-effort-slider-value"
      :title="currentOption?.desc"
    >
      {{ currentOption?.value }}
    </span>
  </div>
</template>

<script setup lang="ts">
  import { computed, shallowRef, useTemplateRef } from 'vue';

  import { t } from '../../../lang/lang';

  import type { IReasoningEffortOption, ReasoningEffort } from './types';

  const props = defineProps<{
    /** 是否禁用（只读展示） */
    disabled?: boolean;
    /** 当前档位；不在 options 内时不高亮任何段 */
    effort?: ReasoningEffort;
    /** 可选档位，按接口返回顺序由浅到深 */
    options: IReasoningEffortOption[];
  }>();
  const emit = defineEmits<{
    /** 用户确认了新档位（点击、松手或按键时触发一次，拖动过程中不触发） */
    (e: 'change', effort: ReasoningEffort): void;
    /** 拖动开始 / 结束，供外层在拖动期间保持浮层不关闭 */
    (e: 'dragging', dragging: boolean): void;
  }>();

  /** 滑块直径，与设计稿 slider-thumb 及样式中的 12px 一致；轨道两端各留半个滑块，保证滑块不越出轨道 */
  const THUMB_SIZE = 12;

  const trackRef = useTemplateRef<HTMLElement>('trackRef');
  /** 拖动中的预览下标，松手后清空并以 effort 为准 */
  const dragIndex = shallowRef<number>();

  // 只有一个档位时没有可切换的区间：整段高亮、滑块停在最右且不可操作
  const isSingle = computed(() => props.options.length <= 1);
  const interactive = computed(() => !props.disabled && !isSingle.value);
  const selectedIndex = computed(() => props.options.findIndex(option => option.key === props.effort));
  const displayIndex = computed(() => dragIndex.value ?? selectedIndex.value);
  const currentOption = computed<IReasoningEffortOption | undefined>(() => props.options[displayIndex.value]);
  // 段数 = 档位数 - 1：选中第 i 档时前 i 段高亮，滑块停在第 i 个段边界（与设计稿三态一致）
  const segmentCount = computed(() => (isSingle.value ? 1 : props.options.length - 1));
  const activeSegmentCount = computed(() => (isSingle.value ? 1 : Math.max(displayIndex.value, 0)));
  const thumbRatio = computed(() =>
    isSingle.value ? 1 : Math.max(displayIndex.value, 0) / (props.options.length - 1),
  );

  const indexFromClientX = (clientX: number) => {
    const rect = trackRef.value?.getBoundingClientRect();
    const usable = (rect?.width ?? 0) - THUMB_SIZE;
    if (!rect || usable <= 0) {
      return 0;
    }
    const ratio = Math.min(Math.max((clientX - rect.left - THUMB_SIZE / 2) / usable, 0), 1);
    return Math.round(ratio * (props.options.length - 1));
  };

  const commit = (index: number) => {
    const option = props.options[index];
    if (option && index !== selectedIndex.value) {
      emit('change', option.key);
    }
  };

  const finishDrag = (event: PointerEvent) => {
    dragIndex.value = undefined;
    if (trackRef.value?.hasPointerCapture?.(event.pointerId)) {
      trackRef.value.releasePointerCapture(event.pointerId);
    }
    emit('dragging', false);
  };

  const handlePointerDown = (event: PointerEvent) => {
    if (!interactive.value || event.button !== 0) {
      return;
    }
    // 阻止默认行为避免拖动时选中文字；捕获指针后拖出轨道也能持续跟随
    event.preventDefault();
    trackRef.value?.setPointerCapture?.(event.pointerId);
    dragIndex.value = indexFromClientX(event.clientX);
    emit('dragging', true);
  };

  const handlePointerMove = (event: PointerEvent) => {
    if (dragIndex.value === undefined) {
      return;
    }
    dragIndex.value = indexFromClientX(event.clientX);
  };

  const handlePointerUp = (event: PointerEvent) => {
    if (dragIndex.value === undefined) {
      return;
    }
    const index = dragIndex.value;
    finishDrag(event);
    commit(index);
  };

  const handlePointerCancel = (event: PointerEvent) => {
    if (dragIndex.value === undefined) {
      return;
    }
    finishDrag(event);
  };

  // 上下方向键与 Enter 被模型列表的键盘导航占用，这里只响应左右 / Home / End
  const handleKeydown = (event: KeyboardEvent) => {
    if (!interactive.value) {
      return;
    }
    const lastIndex = props.options.length - 1;
    const current = Math.max(selectedIndex.value, 0);
    const nextIndexMap: Record<string, number> = {
      ArrowLeft: current - 1,
      ArrowRight: current + 1,
      End: lastIndex,
      Home: 0,
    };
    if (!(event.key in nextIndexMap)) {
      return;
    }
    event.preventDefault();
    commit(Math.min(Math.max(nextIndexMap[event.key], 0), lastIndex));
  };
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-reasoning-effort-slider {
    display: flex;
    flex: 1;
    gap: 8px;
    align-items: center;
    justify-content: flex-end;
    min-width: 0;

    // 轨道高度放大到滑块直径以扩大点击区域，分段本身保持设计稿的 4px
    &-track {
      position: relative;
      display: flex;
      flex: 1;
      align-items: center;
      min-width: 80px;
      max-width: 177px;
      height: 12px;
      cursor: pointer;
      touch-action: none;
    }

    &-segments {
      display: flex;
      flex: 1;
      gap: 2px;
    }

    &-segment {
      flex: 1;
      height: 4px;
      background: variables.$color-border;

      &:first-child {
        border-radius: 8px 0 0 8px;
      }

      &:last-child {
        border-radius: 0 8px 8px 0;
      }

      &:only-child {
        border-radius: 8px;
      }

      &.is-active {
        background: variables.$color-primary;
      }
    }

    // 滑块左边缘位于 (轨道宽 - 滑块直径) × 比例，两端不越出轨道；直径与脚本中 THUMB_SIZE 保持一致
    &-thumb {
      position: absolute;
      top: 0;
      left: calc((100% - 12px) * var(--ai-reasoning-effort-thumb-ratio, 0));
      box-sizing: border-box;
      width: 12px;
      height: 12px;
      background: #fff;
      border: 2px solid variables.$color-primary;
      border-radius: 50%;
      outline: none;

      &:focus-visible {
        box-shadow: 0 0 0 2px rgb(58 132 255 / 30%);
      }
    }

    &-value {
      min-width: 24px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height, 20px);
      color: variables.$color-text;
      white-space: nowrap;
    }

    &.is-static &-track {
      cursor: default;
    }

    &.is-disabled &-track {
      cursor: not-allowed;
    }
  }
</style>
