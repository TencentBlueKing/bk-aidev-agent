<template>
  <vue-draggable-resizable
    :active="!isPanelShow"
    :axis="'y'"
    :draggable="true"
    :h="48"
    :parent="true"
    :prevent-deactivation="true"
    :resizable="false"
    :w="48"
    :x="nimbusLeft"
    :y="nimbusTop"
    @dragging="handleDragging"
  >
    <div
      ref="nimbusContainerRef"
      class="nimbus-container"
      :class="{ 'is-minimize': isMinimize }"
      @click="handleClick"
      @mousedown="handleMouseDown"
      @mouseenter="handleMouseEnter"
      @mouseleave="handleMouseLeave"
      @mouseup="handleMouseUp"
    >
      <div class="nimbus-bkai-wrapper">
        <img
          width="32"
          height="32"
          :src="avatar"
          alt="nimbus"
        />
      </div>
      <i
        ref="minimizeButtonRef"
        class="nimbus-mini bkai-icon"
        :class="isMinimize ? 'bkai-yinyong' : 'bkai-minus-line'"
        @click.stop="handleMinimize"
      ></i>
    </div>
  </vue-draggable-resizable>
</template>

<script setup lang="ts">
  import { ref, onMounted, watch, computed, nextTick, onBeforeUnmount } from 'vue';
  import VueDraggableResizable from 'vue-draggable-resizable';

  import avatar from '../assets/images/avatar.png';
  import { useNimbus } from '../composables/use-nimbus';
  import { useTooltip } from '../composables/use-tippy';
  import { t } from '../lang';

  defineOptions({
    name: 'NimbusButton',
  });

  const props = defineProps<{
    isPanelShow: boolean;
    isMinimize: boolean;
  }>();

  const emit = defineEmits<{
    (e: 'click'): void;
    (e: 'minimize', value: boolean): void;
    (e: 'update:isMinimize', value: boolean): void;
  }>();

  const nimbusContainerRef = ref<HTMLElement | null>(null);
  const minimizeButtonRef = ref<HTMLElement | null>(null);

  const {
    nimbusLeft,
    nimbusTop,
    isMinimize,
    handleClick,
    handleMinimize,
    handleDragging,
    handleMouseEnter,
    handleMouseLeave,
    handleMouseDown,
    handleMouseUp,
  } = useNimbus(emit, props.isMinimize);

  // 向父组件通知状态变化
  watch(isMinimize, (newValue) => {
    emit('update:isMinimize', newValue);
  });

  const minimizeTooltip = computed(() => {
    return isMinimize.value ? t('恢复默认大小') : t('最小化，将缩成锚点');
  });

  // 使用 tippy 工具提示
  const { createTooltip, destroyAll } = useTooltip({
    theme: 'ai-blueking',
    followCursor: 'horizontal',
    delay: [0, 0],
  });

  // 监听窗口大小变化
  const handleResize = () => {
    nextTick(() => {
      initTooltips();
    });
  };

  // 初始化工具提示
  const initTooltips = () => {
    destroyAll();
    if (nimbusContainerRef.value && !isMinimize.value) {
      createTooltip(nimbusContainerRef.value, 'Cmd + I', {
        placement: 'left',
      });
    }

    if (minimizeButtonRef.value) {
      createTooltip(minimizeButtonRef.value, minimizeTooltip.value, {
        placement: 'top',
      });
    }
  };

  // 监听最小化状态变化，更新 tooltip
  watch(
    () => isMinimize.value,
    () => {
      nextTick(() => {
        initTooltips();
      });
    },
  );

  onMounted(() => {
    nextTick(() => {
      initTooltips();
    });
    window.addEventListener('resize', handleResize);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize);
  });
</script>

<style scoped lang="scss">
  .nimbus-container {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    pointer-events: auto;
    cursor: pointer;
    background: #fff;
    border-radius: 50%;
    box-shadow: 0 0 4px 0 #1919291f;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    transform: translateX(0);

    .nimbus-bkai-wrapper {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      background: #f0f5ff;
      border-radius: 50%;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .nimbus-mini {
      position: absolute;
      top: 0;
      right: -6px;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      font-size: 12px;
      color: #979ba5;
      pointer-events: none;
      background: #fff;
      border-radius: 50%;
      box-shadow: 0 2px 6px 0 #0000001a;
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    &:hover {
      .nimbus-mini {
        pointer-events: auto;
        opacity: 1;
      }
    }

    &.is-minimize {
      transform: translateX(26px);

      &:hover {
        transform: translateX(-5px);
      }

      .nimbus-mini {
        transform: rotate(180deg);
      }
    }
  }
</style>
