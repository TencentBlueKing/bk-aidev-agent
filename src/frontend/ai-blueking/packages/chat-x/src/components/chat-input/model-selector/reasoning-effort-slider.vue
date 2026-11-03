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
      @pointerenter="handlePointerHover"
      @pointerleave="handlePointerLeave"
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
        ref="thumbRef"
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
        @blur="handleThumbBlur"
        @keydown="handleKeydown"
      />
      <span
        v-if="tipOption?.value"
        aria-hidden="true"
        class="ai-reasoning-effort-slider-tip"
        :style="{ '--ai-reasoning-effort-tip-ratio': tipRatio }"
      >
        {{ tipOption.value }}
      </span>
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
    /** 切到新档位时触发（按下、拖动跨档或按键各一次，同一档不重复；拖动中即抛出） */
    (e: 'change', effort: ReasoningEffort): void;
    /** 拖动开始 / 结束，供外层在拖动期间保持浮层不关闭 */
    (e: 'dragging', dragging: boolean): void;
  }>();

  /** 分段间距，与样式中 segments 的 gap: 2px 一致；第 i 档对应第 i 个分段交界，交界中心在 i × (轨道宽 + 间距) / 段数 - 间距 / 2 */
  const SEGMENT_GAP = 2;

  const trackRef = useTemplateRef<HTMLElement>('trackRef');
  const thumbRef = useTemplateRef<HTMLElement>('thumbRef');
  /** 拖动中的下标，松手后清空，展示回落到 effort */
  const dragIndex = shallowRef<number>();
  /** 悬停下标，只驱动档位名称气泡，不改变选中 */
  const hoverIndex = shallowRef<number>();
  /** 键盘调档时气泡跟随的下标；指针再次移动或失焦后取消 */
  const keyboardIndex = shallowRef<number>();
  /** 本次拖动手势已经同步过的下标，避免同一档重复抛出 */
  let gestureIndex: number | undefined;

  // 只有一个档位时没有可切换的区间：整段高亮、滑块停在最右且不可操作
  const isSingle = computed(() => props.options.length <= 1);
  const interactive = computed(() => !props.disabled && !isSingle.value);
  const selectedIndex = computed(() => props.options.findIndex(option => option.key === props.effort));
  const displayIndex = computed(() => dragIndex.value ?? selectedIndex.value);
  const currentOption = computed<IReasoningEffortOption | undefined>(() => props.options[displayIndex.value]);
  // 段数 = 档位数 - 1：选中第 i 档时前 i 段高亮，滑块停在第 i 个段边界（与设计稿三态一致）
  const segmentCount = computed(() => (isSingle.value ? 1 : props.options.length - 1));
  const activeSegmentCount = computed(() => (isSingle.value ? 1 : Math.max(displayIndex.value, 0)));
  const ratioOf = (index: number) => (props.options.length <= 1 ? 1 : Math.max(index, 0) / (props.options.length - 1));
  const thumbRatio = computed(() => (isSingle.value ? 1 : ratioOf(displayIndex.value)));
  // 拖动跟手；键盘调档跟滑块；仅悬停时停在指针所在档，不移动滑块
  const tipIndex = computed(() => dragIndex.value ?? keyboardIndex.value ?? hoverIndex.value);
  const tipOption = computed(() => {
    const index = tipIndex.value;
    return index === undefined ? undefined : props.options[index];
  });
  const tipRatio = computed(() => (tipIndex.value === undefined ? 0 : ratioOf(tipIndex.value)));

  // 取离指针最近的分段交界作为档位，与滑块的渲染位置一一对应
  const indexFromClientX = (clientX: number) => {
    const rect = trackRef.value?.getBoundingClientRect();
    const lastIndex = props.options.length - 1;
    if (!rect || rect.width <= 0 || lastIndex <= 0) {
      return 0;
    }
    const index = Math.round(((clientX - rect.left + SEGMENT_GAP / 2) * lastIndex) / (rect.width + SEGMENT_GAP));
    return Math.min(Math.max(index, 0), lastIndex);
  };

  const commit = (index: number) => {
    const option = props.options[index];
    if (option && index !== selectedIndex.value) {
      emit('change', option.key);
    }
  };

  // 按下或拖动跨档时立刻选中，与点击一致；手势起点落在当前档时不重复抛出
  const applyIndex = (index: number) => {
    dragIndex.value = index;
    if (gestureIndex === index) {
      return;
    }
    const isGestureStart = gestureIndex === undefined;
    gestureIndex = index;
    const option = props.options[index];
    if (!option || (isGestureStart && index === selectedIndex.value)) {
      return;
    }
    emit('change', option.key);
  };

  const isPointerInsideTrack = (event: PointerEvent) => {
    const rect = trackRef.value?.getBoundingClientRect();
    if (!rect) {
      return false;
    }
    return (
      event.clientX >= rect.left &&
      event.clientX <= rect.right &&
      event.clientY >= rect.top &&
      event.clientY <= rect.bottom
    );
  };

  const finishDrag = (event: PointerEvent) => {
    const index = dragIndex.value;
    dragIndex.value = undefined;
    gestureIndex = undefined;
    if (trackRef.value?.hasPointerCapture?.(event.pointerId)) {
      trackRef.value.releasePointerCapture(event.pointerId);
    }
    // 松手后指针还在轨道上时，继续显示该档名称
    hoverIndex.value =
      event.type !== 'pointercancel' && index !== undefined && isPointerInsideTrack(event) ? index : undefined;
    emit('dragging', false);
  };

  const handlePointerHover = (event: PointerEvent) => {
    if (dragIndex.value !== undefined || !props.options.length) {
      return;
    }
    keyboardIndex.value = undefined;
    hoverIndex.value = indexFromClientX(event.clientX);
  };

  const handlePointerLeave = () => {
    hoverIndex.value = undefined;
  };

  const handlePointerDown = (event: PointerEvent) => {
    if (!interactive.value || event.button !== 0) {
      return;
    }
    // 阻止默认行为避免拖动时选中文字；捕获指针后拖出轨道也能持续跟随。
    // preventDefault 会吃掉点击带来的焦点，左右键监听在滑块上，这里要手动聚焦
    event.preventDefault();
    keyboardIndex.value = undefined;
    thumbRef.value?.focus({ preventScroll: true });
    trackRef.value?.setPointerCapture?.(event.pointerId);
    emit('dragging', true);
    applyIndex(indexFromClientX(event.clientX));
  };

  const handlePointerMove = (event: PointerEvent) => {
    if (dragIndex.value !== undefined) {
      applyIndex(indexFromClientX(event.clientX));
      return;
    }
    handlePointerHover(event);
  };

  const handlePointerUp = (event: PointerEvent) => {
    if (dragIndex.value === undefined) {
      return;
    }
    finishDrag(event);
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
    const nextIndex = Math.min(Math.max(nextIndexMap[event.key], 0), lastIndex);
    // 悬停气泡钉在指针所在档，键盘调档时改跟滑块
    hoverIndex.value = undefined;
    keyboardIndex.value = nextIndex;
    commit(nextIndex);
  };

  const handleThumbBlur = () => {
    keyboardIndex.value = undefined;
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
      touch-action: none;
      cursor: pointer;
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

    // 滑块中心对齐第 i 个分段交界（(100% + 2px 段间距) × 比例 - 1px），再减半个直径 6px；
    // 首末档夹在轨道两端不越界，对应设计稿「关闭」x=0、「最高」x=165（轨道 177）
    &-thumb {
      position: absolute;
      top: 0;
      left: clamp(0px, calc((100% + 2px) * var(--ai-reasoning-effort-thumb-ratio, 0) - 7px), calc(100% - 12px));
      box-sizing: border-box;
      width: 12px;
      height: 12px;
      outline: none;
      background: #fff;
      border: 2px solid variables.$color-primary;
      border-radius: 50%;

      &:focus-visible {
        box-shadow: 0 0 0 2px rgb(58 132 255 / 30%);
      }
    }

    // 档位名称气泡：中心对齐滑块中心（与 thumb 同一套 clamp），箭头指向该档交界
    &-tip {
      position: absolute;
      bottom: calc(100% + 4px);
      left: clamp(6px, calc((100% + 2px) * var(--ai-reasoning-effort-tip-ratio, 0) - 1px), calc(100% - 6px));
      z-index: 1;
      padding: 2px 6px;
      font-size: 12px;
      line-height: 16px;
      color: #fff;
      white-space: nowrap;
      pointer-events: none;
      background: #313238;
      border-radius: 2px;
      transform: translateX(-50%);

      &::after {
        position: absolute;
        top: 100%;
        left: 50%;
        content: '';
        border-color: #313238 transparent transparent;
        border-style: solid;
        border-width: 4px 4px 0;
        transform: translateX(-50%);
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
