<template>
  <div
    ref="headerRef"
    class="header drag-handle"
  >
    <div class="left-section">
      <div class="logo">
        <img
          :src="logo"
          alt="logo"
        />
      </div>
      <div class="title">{{ title }}</div>
    </div>
    <div class="right-section">
      <!-- <i class="bkai-icon bkai-xinzengliaotian"></i> -->
      <!-- <i class="bkai-icon bkai-history"></i> -->
      <i
        ref="compressionRef"
        class="bkai-icon"
        :class="compressionIcon"
        @click="emit('toggleCompression')"
      ></i>
      <i
        ref="closeRef"
        class="bkai-icon bkai-close-line-2"
        @click="emit('close')"
      ></i>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, onMounted, watch, onBeforeUnmount } from 'vue';

  import logo from '../assets/images/avatar.png';
  import { useTooltip } from '../composables/use-tippy';
  import { t } from '../lang';

  const props = withDefaults(defineProps<{
    title: string;
    isCompressionHeight: boolean;
  }>(), {
    title: t('AI 小鲸'),
    isCompressionHeight: false,
  });

  const emit = defineEmits<(e: 'close' | 'toggleCompression') => void>();

  const compressionIcon = computed(() => {
    return props.isCompressionHeight ? 'bkai-morenchicun' : 'bkai-yasuo';
  });

  const compressionTooltip = computed(() => {
    return props.isCompressionHeight ? t('恢复默认尺寸') : t('缩小高度');
  });

  const headerRef = ref<HTMLElement | null>(null);
  const compressionRef = ref<HTMLElement | null>(null);
  const closeRef = ref<HTMLElement | null>(null);

  const { createTooltip, destroyAll } = useTooltip({
    arrow: true,
    delay: [0, 0],
  });

  // 初始化 tooltip
  const initTooltips = () => {
    destroyAll(); // 先清除所有已存在的 tooltip
    if (compressionRef.value) {
      createTooltip(compressionRef.value, compressionTooltip.value, {
        appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
      });
    }
    if (closeRef.value) {
      createTooltip(closeRef.value, t('关闭'), {
        appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
      });
    }
  };

  // 监听压缩状态变化，更新 tooltip
  watch(
    () => props.isCompressionHeight,
    () => {
      initTooltips();
    },
  );

  onMounted(() => {
    initTooltips();
  });

  onBeforeUnmount(() => {
    destroyAll();
  });
</script>

<style lang="scss" scoped>
  .header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 14px;
    cursor: move;
    border-bottom: 1px solid #e5e5e5;

    .left-section {
      display: flex;
      gap: 4px;
      align-items: center;

      .logo {
        width: 32px;
        height: 32px;

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
      }

      .title {
        font-size: 14px;
        font-weight: 600;
        line-height: 20px;
        color: #4d4f56;
      }
    }

    .right-section {
      display: flex;
      gap: 12px;
    }

    .bkai-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      margin-right: 0;
      font-size: 14px;
      color: #63656e;
      cursor: pointer;
      border-radius: 2px;

      &:hover {
        color: #4d4f56;
        background: #eaebf0;
      }
    }
  }
</style>
