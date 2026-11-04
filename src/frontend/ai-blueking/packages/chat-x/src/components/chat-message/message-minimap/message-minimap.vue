<template>
  <div
    v-if="visible"
    class="ai-message-minimap"
    :class="{ 'is-hover': hoverIndex !== -1, 'is-overlap': overlapsMessage }"
    :style="{
      '--ai-message-minimap-viewport-height': `${viewportHeight}px`,
      '--ai-message-minimap-top': `${minimapTop}px`,
      '--ai-message-minimap-mask-left': `${maskLeft}px`,
    }"
    @wheel.prevent.stop="handleWheel"
  >
    <!-- hover 时盖住消息左侧的白色渐变，只做视觉遮挡，不拦截事件 -->
    <div class="ai-message-minimap-mask" />
    <nav
      ref="listRef"
      :aria-label="t('消息定位')"
      class="ai-message-minimap-list"
      :class="{ 'is-fade-top': isFadeTop, 'is-fade-bottom': isFadeBottom }"
      @mouseleave="handleListLeave"
      @scroll="handleListScroll"
    >
      <button
        v-for="(round, index) in rounds"
        :key="index"
        :aria-label="questionTexts[index] || undefined"
        class="ai-message-minimap-item"
        :class="{ 'is-active': hoverIndex < 0 && activeIndexSet.has(index), 'is-hover': hoverIndex === index }"
        type="button"
        @click="emit('locate', round.userGroup.uid)"
        @mouseenter="handleItemEnter($event, index)"
      >
        <span
          class="ai-message-minimap-item-line"
          :style="{ width: `${resolveLineWidth(index)}px` }"
        />
      </button>
    </nav>
    <!-- 预览 DOM 由 tippy 移入浮层展示，这里只是 Vue 渲染的落脚点，本身不可见 -->
    <div class="ai-message-minimap-tip-host">
      <div
        ref="tipContentRef"
        class="ai-message-minimap-preview"
      >
        <div class="ai-message-minimap-preview-question">{{ previewQuestion }}</div>
        <div
          v-if="previewAnswer"
          class="ai-message-minimap-preview-answer"
        >
          {{ previewAnswer }}
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';

  import tippy from 'tippy.js';

  import { useCommonTippyInject } from '../../../composables/use-common';
  import { getAnswerText, getQuestionText, useMessageMinimap } from '../../../composables/use-message-minimap';
  import { t } from '../../../lang/lang';

  import type { MessageGroup } from '../../../composables/use-message-group';
  import type { Instance } from 'tippy.js';

  import 'tippy.js/dist/tippy.css';

  export type MessageMinimapEmits = {
    (e: 'locate', uid: string): void;
  };

  export type MessageMinimapProps = {
    /** 消息滚动容器，用作可视区判断的 root */
    container?: HTMLElement | null;
    messageGroups: MessageGroup[];
  };

  // 设计稿刻度宽度：常态 6px，hover 的刻度 30px，向两侧每隔一根递减 6px
  const LINE_MIN_WIDTH = 6;
  const LINE_MAX_WIDTH = 30;
  const LINE_WIDTH_STEP = 6;
  // 贴主栏左边缘，留出 4px，避免刻度被面板边框切掉
  const EDGE_LEFT = 4;

  const props = defineProps<MessageMinimapProps>();
  const emit = defineEmits<MessageMinimapEmits>();

  const commonTippyOptions = useCommonTippyInject();
  const { activeIndexes, rounds, visible } = useMessageMinimap({
    container: () => props.container,
    messageGroups: () => props.messageGroups,
  });

  const listRef = useTemplateRef<HTMLElement>('listRef');
  const tipContentRef = useTemplateRef<HTMLElement>('tipContentRef');

  const viewportHeight = shallowRef(0);
  const minimapTop = shallowRef(0);
  const maskLeft = shallowRef(0);
  // 最长刻度的右端越过消息列左缘时，hover 需要遮住被压住的消息
  const overlapsMessage = shallowRef(true);
  const hoverIndex = shallowRef(-1);
  const isFadeTop = shallowRef(false);
  const isFadeBottom = shallowRef(false);

  const activeIndexSet = computed(() => new Set(activeIndexes.value));
  const questionTexts = computed(() => rounds.value.map(round => getQuestionText(round.userGroup.messages[0])));
  const previewQuestion = computed(() => questionTexts.value[hoverIndex.value] ?? '');
  // 只解析当前 hover 那一轮的回答
  const previewAnswer = computed(() =>
    hoverIndex.value < 0 ? '' : getAnswerText(rounds.value[hoverIndex.value]?.answerGroup?.messages),
  );

  const resolveLineWidth = (index: number) => {
    if (hoverIndex.value < 0) return LINE_MIN_WIDTH;
    return Math.max(LINE_MIN_WIDTH, LINE_MAX_WIDTH - LINE_WIDTH_STEP * Math.abs(index - hoverIndex.value));
  };

  /**
   * 定位器贴在主栏左边缘，垂直范围跟消息可视区走，不把输入框算进去。
   * 主栏变窄、消息列铺满时，最长刻度会压到消息，这时才需要遮罩。
   */
  const updatePlacement = (container: HTMLElement) => {
    viewportHeight.value = container.clientHeight;
    const anchor = container.parentElement;
    if (!anchor) {
      minimapTop.value = 0;
      maskLeft.value = 0;
      overlapsMessage.value = true;
      return;
    }
    const gutter = container.getBoundingClientRect().left - anchor.getBoundingClientRect().left;
    minimapTop.value = container.offsetTop;
    maskLeft.value = Math.round(gutter);
    overlapsMessage.value = gutter < EDGE_LEFT + LINE_MAX_WIDTH;
  };

  // 定位器以消息可视区为基准垂直居中、限制最大高度，需跟随容器尺寸变化
  watch(
    () => props.container,
    (container, _, onCleanup) => {
      if (!container) return;
      const update = () => updatePlacement(container);
      update();
      const resizeObserver = new ResizeObserver(update);
      resizeObserver.observe(container);
      if (container.parentElement) resizeObserver.observe(container.parentElement);
      onCleanup(() => resizeObserver.disconnect());
    },
    { immediate: true },
  );

  /** 列表超出最大高度时，在还有内容的一端渐隐 */
  const updateFade = () => {
    const list = listRef.value;
    if (!list) {
      isFadeTop.value = false;
      isFadeBottom.value = false;
      return;
    }
    isFadeTop.value = list.scrollTop > 0;
    isFadeBottom.value = list.scrollTop + list.clientHeight < list.scrollHeight - 1;
  };

  watch([viewportHeight, rounds, visible], updateFade, { flush: 'post' });

  // 高亮刻度跑出定位器可见范围时（如首屏贴底），把列表滚到能看到高亮刻度；hover 中不打断用户
  watch(
    activeIndexes,
    indexes => {
      const list = listRef.value;
      const firstIndex = indexes[0];
      if (!list || firstIndex === undefined || hoverIndex.value !== -1) return;
      const item = list.children[firstIndex];
      if (!(item instanceof HTMLElement)) return;
      if (item.offsetTop < list.scrollTop) {
        list.scrollTop = item.offsetTop;
      } else if (item.offsetTop + item.offsetHeight > list.scrollTop + list.clientHeight) {
        list.scrollTop = item.offsetTop + item.offsetHeight - list.clientHeight;
      }
      updateFade();
    },
    { flush: 'post' },
  );

  let previewTip: Instance | undefined;
  let tipAnchor: HTMLElement | undefined;

  const getReferenceClientRect = () => (tipAnchor?.isConnected ? tipAnchor.getBoundingClientRect() : new DOMRect());

  /** 与 common tippy 挂到同一层（全屏时为全屏容器），每次展示时重新取 */
  const resolveAppendTo = (reference: Element) => {
    const appendTo = commonTippyOptions?.value?.appendTo;
    if (appendTo instanceof Element) return appendTo;
    if (typeof appendTo === 'function') return appendTo(reference);
    return document.body;
  };

  const destroyPreview = () => {
    tipAnchor = undefined;
    previewTip?.destroy();
    previewTip = undefined;
  };

  const showPreview = (anchor: HTMLElement) => {
    tipAnchor = anchor;
    // 等预览文字渲染进落脚点后再定位，浮层尺寸才准确
    nextTick(() => {
      const content = tipContentRef.value;
      if (tipAnchor !== anchor || !content) return;
      if (!previewTip) {
        const zIndex = commonTippyOptions?.value?.zIndex;
        previewTip = tippy(document.createElement('div'), {
          allowHTML: false,
          appendTo: resolveAppendTo,
          arrow: true,
          content,
          getReferenceClientRect,
          hideOnClick: false,
          interactive: false,
          maxWidth: 'none',
          // 箭头露出 5px，再留 1px 与 hover 刻度末端的间隙
          offset: [0, 6],
          placement: 'right',
          // 定位用视口坐标，不受消息容器滚动与裁切影响
          popperOptions: { strategy: 'fixed' },
          theme: 'ai-chat-box-light light ai-message-minimap',
          trigger: 'manual',
          ...(zIndex ? { zIndex } : {}),
        });
      }
      previewTip.show();
      previewTip.popperInstance?.update();
    });
  };

  /**
   * 滚轮留在定位器内：消息容器不跟随滚动。
   * 刻度超出定位器高度时，只滚动定位器自己的列表。
   */
  const handleWheel = (event: WheelEvent) => {
    const list = listRef.value;
    if (!list) return;
    const maxScrollTop = list.scrollHeight - list.clientHeight;
    if (maxScrollTop <= 0) return;
    // 鼠标滚轮常以「行」为单位，按一行约 16px 换算，触控板仍用像素
    const delta = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? event.deltaY * 16 : event.deltaY;
    list.scrollTop = Math.min(maxScrollTop, Math.max(0, list.scrollTop + delta));
  };

  const handleItemEnter = (event: MouseEvent, index: number) => {
    hoverIndex.value = index;
    if (event.currentTarget instanceof HTMLElement) {
      showPreview(event.currentTarget);
    }
  };

  const handleListLeave = () => {
    hoverIndex.value = -1;
    tipAnchor = undefined;
    previewTip?.hide();
  };

  const handleListScroll = () => {
    updateFade();
    previewTip?.popperInstance?.update();
  };

  watch(visible, isVisible => {
    if (isVisible) return;
    hoverIndex.value = -1;
    destroyPreview();
  });

  onBeforeUnmount(destroyPreview);
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  // 刻度颜色按设计稿取 bkui 标准灰：常态 #c4c6cc，可视区高亮 #63656e，hover 为标题色
  $line-color: #c4c6cc;
  $line-active-color: #63656e;

  // 首尾渐隐区覆盖约三根刻度
  $fade-size: 24px;
  $fade-color: rgb(0 0 0 / 20%);

  // 挂在主栏上，贴左边缘且不占位；垂直位置跟消息滚动容器对齐
  .ai-message-minimap {
    position: absolute;
    top: var(--ai-message-minimap-top, 0);
    left: 0;
    z-index: 10;
    width: 0;
    height: 0;
    pointer-events: none;

    &-mask {
      position: absolute;
      top: 0;
      left: 0;
      width: 100px;
      height: var(--ai-message-minimap-viewport-height, 0);
      pointer-events: none;
      background: linear-gradient(90deg, #fff 0%, rgb(255 255 255 / 0%) 100%);
      opacity: 0;
      transition: opacity 0.15s;
    }

    &-list {
      position: absolute;
      top: calc(var(--ai-message-minimap-viewport-height, 0px) / 2);
      left: 4px;
      display: flex;
      flex-direction: column;

      // 贴主栏左边缘；hover 时放宽到最长刻度
      width: 12px;
      max-height: calc(var(--ai-message-minimap-viewport-height, 0px) * 2 / 3);
      overflow-y: auto;
      pointer-events: auto;
      scrollbar-width: none;
      transform: translateY(-50%);

      &::-webkit-scrollbar {
        display: none;
      }

      &.is-fade-top {
        mask-image: linear-gradient(to bottom, $fade-color 0, #000 $fade-size);
      }

      &.is-fade-bottom {
        mask-image: linear-gradient(to top, $fade-color 0, #000 $fade-size);
      }

      &.is-fade-top.is-fade-bottom {
        mask-image: linear-gradient(
          to bottom,
          $fade-color 0,
          #000 $fade-size,
          #000 calc(100% - #{$fade-size}),
          $fade-color 100%
        );
      }
    }

    &.is-hover {
      .ai-message-minimap-list {
        width: 30px;
      }
    }

    // 刻度压到消息列时才遮住左侧消息；左侧是空白时不盖
    &.is-hover.is-overlap .ai-message-minimap-mask {
      left: var(--ai-message-minimap-mask-left, 0);
      opacity: 1;
    }

    // 每根刻度占 8px 高（2px 横线 + 6px 间距），整行可点击
    &-item {
      display: flex;
      flex: 0 0 8px;
      align-items: center;
      width: 100%;
      height: 8px;
      padding: 0;
      cursor: pointer;
      background: transparent;
      border: 0;

      &-line {
        display: block;
        height: 2px;
        background-color: $line-color;
        border-radius: 2px;
        transition:
          width 0.15s,
          background-color 0.15s;
      }

      &.is-active .ai-message-minimap-item-line {
        background-color: $line-active-color;
      }

      &.is-hover .ai-message-minimap-item-line {
        background-color: variables.$color-title;
      }
    }

    &-tip-host {
      display: none;
    }
  }

  // 预览内容被 tippy 移到浮层里，不在 .ai-message-minimap 下
  .ai-message-minimap-preview {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 356px;
    padding: 12px 16px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);

    &-question {
      overflow: hidden;
      text-overflow: ellipsis;
      color: variables.$color-text;
      white-space: nowrap;
    }

    &-answer {
      display: -webkit-box;
      overflow: hidden;
      -webkit-line-clamp: 2;
      color: variables.$color-text-secondary;
      word-break: break-all;
      -webkit-box-orient: vertical;
    }
  }

  // 预览箭头按设计稿 6×12（tippy 默认 16×8），露出 5px、与卡片重叠 1px 避免缝隙
  .tippy-box[data-theme~='ai-message-minimap'] > .tippy-arrow {
    width: 12px;
    height: 12px;
  }

  .tippy-box[data-theme~='ai-message-minimap'][data-placement^='right'] > .tippy-arrow::before {
    left: -5px;
    border-width: 6px 6px 6px 0;
  }

  .tippy-box[data-theme~='ai-message-minimap'][data-placement^='left'] > .tippy-arrow::before {
    right: -5px;
    border-width: 6px 0 6px 6px;
  }
</style>
