<template>
  <vue-draggable-resizable
    :active="!isPanelShow"
    :axis="'y'"
    :draggable="true"
    :h="nimbusDimensions.container"
    :parent="true"
    :prevent-deactivation="true"
    :resizable="false"
    :w="nimbusDimensions.container"
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
          :width="nimbusDimensions.img"
          :height="nimbusDimensions.img"
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

  const props = withDefaults(
    defineProps<{
      isPanelShow: boolean;
      isMinimize: boolean;
      size?: 'small' | 'normal' | 'large';
    }>(),
    {
      size: 'normal',
    }
  );

  const emit = defineEmits<{
    (e: 'click'): void;
    (e: 'minimize', value: boolean): void;
    (e: 'update:isMinimize', value: boolean): void;
  }>();

  const sizeMap = {
    small: {
      container: 40,
      wrapper: 32,
      img: 24,
      mini: {
        size: 14,
        fontSize: 10,
        right: -4,
      },
    },
    normal: {
      container: 48,
      wrapper: 40,
      img: 32,
      mini: {
        size: 16,
        fontSize: 12,
        right: -6,
      },
    },
    large: {
      container: 56,
      wrapper: 48,
      img: 40,
      mini: {
        size: 18,
        fontSize: 14,
        right: -6,
      },
    },
  };

  const nimbusDimensions = computed(() => sizeMap[props.size]);

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
  watch(isMinimize, newValue => {
    emit('update:isMinimize', newValue);
  });

  const minimizeTooltip = computed(() => {
    return isMinimize.value ? t('恢复默认大小') : t('最小化，将缩成锚点');
  });

  // 使用 tippy 工具提示
  const { createTooltip, destroyAll } = useTooltip({
    theme: 'ai-blueking',
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
    }
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
    width: v-bind('`${nimbusDimensions.container}px`');
    height: v-bind('`${nimbusDimensions.container}px`');
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
      width: v-bind('`${nimbusDimensions.wrapper}px`');
      height: v-bind('`${nimbusDimensions.wrapper}px`');
      background: #f0f5ff;
      border-radius: 50%;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .nimbus-mini {
      position: absolute;
      top: 0;
      right: v-bind('`${nimbusDimensions.mini.right}px`');
      display: flex;
      align-items: center;
      justify-content: center;
      width: v-bind('`${nimbusDimensions.mini.size}px`');
      height: v-bind('`${nimbusDimensions.mini.size}px`');
      font-size: v-bind('`${nimbusDimensions.mini.fontSize}px`');
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
