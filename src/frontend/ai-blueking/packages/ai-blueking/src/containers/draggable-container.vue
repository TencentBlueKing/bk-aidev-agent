<template>
  <vue-draggable-resizable
    v-show="props.visible"
    ref="draggableRef"
    :active="props.visible"
    :class="['draggable-container-wrapper', props.className]"
    class-name="draggable-container-inner"
    :drag-handle="props.dragHandle"
    :draggable="props.draggable"
    :h="height"
    :max-width="maxWidth"
    :min-height="minHeight"
    :min-width="minWidth"
    :parent="true"
    :prevent-deactivation="true"
    :resizable="props.resizable"
    :style="rootStyle"
    :w="width"
    :x="left"
    :y="top"
    @drag-stop="handleDragStopWithIframe"
    @dragging="handleDraggingWithIframe"
    @resize-stop="handleResizeStopWithIframe"
    @resizing="handleResizingWithIframe"
  >
    <div class="draggable-container-content">
      <slot />
    </div>
  </vue-draggable-resizable>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';

  import VueDraggableResizable from 'vue-draggable-resizable';

  import { useDraggable } from './use-draggable';

  import type { DraggableContainerEmits, DraggableContainerProps, PositionAndSize } from './types';

  import 'vue-draggable-resizable/style.css';

  // Props 定义
  const props = withDefaults(defineProps<DraggableContainerProps>(), {
    visible: false,
    draggable: true,
    resizable: true,
    defaultWidth: 400,
    defaultHeight: undefined,
    defaultX: undefined,
    defaultY: 0,
    minWidth: 400,
    minHeight: 400,
    maxWidth: undefined,
    maxWidthPercent: 80,
    compressedHeight: 800,
    compressedPadding: 0,
    dragHandle: '.drag-handle',
    className: '',
    teleportTo: 'body',
  });

  // Emits 定义
  const emit = defineEmits<DraggableContainerEmits>();

  // 拖拽/调整大小状态
  const isDraggingOrResizing = ref(false);

  // 使用拖拽逻辑
  const {
    minWidth,
    minHeight,
    maxWidth,
    top,
    left,
    width,
    height,
    isCompressed,
    isSidePanelExpanded,
    handleDragging,
    handleResizing,
    handleDragStop,
    handleResizeStop,
    toggleCompression,
    updatePosition,
    updateSize,
    updatePositionAndSize,
    expandForSidePanel,
    collapseSidePanel,
  } = useDraggable(
    {
      initWidth: props.defaultWidth,
      minWidth: props.minWidth,
      minHeight: props.minHeight,
      maxWidthPercent: props.maxWidthPercent,
      compressedHeight: props.compressedHeight,
      defaultHeight: props.defaultHeight,
      defaultTop: props.defaultY,
      defaultLeft: props.defaultX,
      compressedPadding: props.compressedPadding,
    },
    {
      onDragStop: position => emit('drag-stop', position),
      onResizeStop: position => emit('resize-stop', position),
      onDragging: position => emit('dragging', position),
      onResizing: position => emit('resizing', position),
    },
  );

  // 计算根元素样式
  const rootStyle = computed(() => {
    const maxWidthValue =
      typeof props.maxWidth === 'number' ? `${props.maxWidth}px` : (props.maxWidth ?? `${maxWidth.value}px`);

    return {
      '--draggable-max-width': maxWidthValue,
    };
  });

  // 当前位置和大小
  const positionAndSize = computed<PositionAndSize>(() => ({
    x: left.value,
    y: top.value,
    width: width.value,
    height: height.value,
  }));

  // ==================== iframe 指针事件处理 ====================

  /**
   * 禁用页面中所有 iframe 的指针事件
   * 用于解决拖拽时鼠标经过 iframe 导致事件丢失的问题
   */
  const disableIframePointerEvents = (): void => {
    const iframes = document.querySelectorAll('iframe');
    iframes.forEach(iframe => {
      iframe.style.pointerEvents = 'none';
    });
  };

  /**
   * 恢复页面中所有 iframe 的指针事件
   */
  const enableIframePointerEvents = (): void => {
    const iframes = document.querySelectorAll('iframe');
    iframes.forEach(iframe => {
      iframe.style.pointerEvents = '';
    });
  };

  /**
   * 拖拽时的处理（包含 iframe 禁用）
   */
  const handleDraggingWithIframe = (x: number, y: number): void => {
    if (!isDraggingOrResizing.value) {
      isDraggingOrResizing.value = true;
      disableIframePointerEvents();
    }
    handleDragging(x, y);
  };

  /**
   * 调整大小时的处理（包含 iframe 禁用）
   */
  const handleResizingWithIframe = (x: number, y: number, w: number, h: number): void => {
    if (!isDraggingOrResizing.value) {
      isDraggingOrResizing.value = true;
      disableIframePointerEvents();
    }
    handleResizing(x, y, w, h);
  };

  /**
   * 拖拽停止时的处理（包含 iframe 恢复）
   */
  const handleDragStopWithIframe = (x: number, y: number): void => {
    handleDragStop(x, y);
    isDraggingOrResizing.value = false;
    enableIframePointerEvents();
  };

  /**
   * 调整大小停止时的处理（包含 iframe 恢复）
   */
  const handleResizeStopWithIframe = (x: number, y: number, w: number, h: number): void => {
    handleResizeStop(x, y, w, h);
    isDraggingOrResizing.value = false;
    enableIframePointerEvents();
  };

  // 监听压缩状态变化
  watch(isCompressed, newValue => {
    emit('compression-change', newValue);
  });

  // 暴露给父组件的方法和属性
  defineExpose({
    updatePosition,
    updateSize,
    updatePositionAndSize,
    toggleCompression,
    expandForSidePanel,
    collapseSidePanel,
    positionAndSize,
    isCompressed,
    isSidePanelExpanded,
  });
</script>

<style lang="scss" scoped>
  .draggable-container-wrapper {
    pointer-events: auto;
  }

  .draggable-container-inner {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    pointer-events: auto;
    background: transparent;
    border-radius: 12px;
    box-shadow: 0 2px 12px 0 rgb(0 0 0 / 20%);

    :deep(.handle) {
      background: transparent;
      border: none;

      &.handle-ml,
      &.handle-mr {
        top: 0;
        height: 100%;
        margin-top: 0;
        cursor: ew-resize;
      }

      &.handle-tm,
      &.handle-bm {
        left: 0;
        width: 100%;
        margin-left: 0;
        cursor: ns-resize;
      }

      &.handle-tl,
      &.handle-br {
        cursor: nwse-resize;
      }

      &.handle-tr {
        top: -5px;
        right: -5px;
      }

      &.handle-tl {
        top: -5px;
        left: -5px;
      }

      &.handle-bl {
        bottom: -5px;
        left: -5px;
      }

      &.handle-br {
        right: -5px;
        bottom: -5px;
      }

      &.handle-tr,
      &.handle-bl {
        cursor: nesw-resize;
      }
    }
  }

  .draggable-container-content {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }

  // 覆盖 vue-draggable-resizable 的默认样式
  :deep(.vdr) {
    background: transparent;
    border: none;
  }
</style>
