<template>
  <div
    ref="headerRef"
    class="header drag-handle"
    :class="{ 'draggable': props.draggable }"
  >
    <div class="left-section">
      <div class="logo">
        <img
          :src="logo"
          alt="logo"
        />
      </div>
      <div class="title">{{ displayTitle }}</div>
    </div>
    <div class="right-section">
      <i
        v-if="props.showNewChatIcon"
        class="bkai-icon bkai-xinzengliaotian"
        v-bk-tooltips="{ content: t('新增聊天'), boundary: 'parent' }"
        @click="handleNewChat"
      ></i>
      <i
        v-if="props.showHistoryIcon"
        ref="historyIconRef"
        class="bkai-icon bkai-history"
        v-bk-tooltips="{ content: t('历史会话'), boundary: 'parent' }"
        @click="handleHistoryClick"
      ></i>
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
  import { useHistoryPanel } from '../composables/use-history-panel';
  import { t } from '../lang';
  import { sessionStore } from '../store/sessionStore';

  import { bkTooltips } from 'bkui-vue';
  import HistoryPanel from './history-panel.vue';

  const props = withDefaults(defineProps<{
    title: string;
    isCompressionHeight: boolean;
    draggable: boolean;
    showHistoryIcon: boolean;
    showNewChatIcon?: boolean;
  }>(), {
    title: t('AI 小鲸'),
    isCompressionHeight: false,
    draggable: true,
    showHistoryIcon: true,
    showNewChatIcon: true,
  });

  const emit = defineEmits<(e: 'close' | 'toggleCompression' | 'newChat') => void>();

  const vBkTooltips = bkTooltips;

  // 历史面板相关的 refs
  const historyIconRef = ref<HTMLElement | null>(null);

  // 使用历史面板 composable
  const { handleTriggerClick: handleHistoryClick } = useHistoryPanel({
    triggerRef: historyIconRef,
    panelComponent: HistoryPanel,
    tippyOptions: {
      placement: 'bottom-end',
      offset: [0, 8],
      appendTo: () => document.querySelector('.ai-blueking-container-wrapper') as HTMLElement || document.body,
    }
  });

  const displayTitle = computed(() => {
    return sessionStore.currentSession.value?.sessionName || props.title;
  });

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



  // 处理新增聊天按钮点击
  const handleNewChat = async () => {
    try {
      // 通知父组件
      emit('newChat')
      // 创建新会话
      await sessionStore.initSession(false)
    } catch (error) {
      console.error('Failed to create new chat:', error)
    }
  }
</script>

<style lang="scss" scoped>
  .header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 14px;
    border-bottom: 1px solid #e5e5e5;

    &.draggable {
      cursor: move;
    }

    .left-section {
      display: flex;
      gap: 4px;
      align-items: center;
      flex: 1;
      min-width: 0;

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
        max-width: calc(100% - 60px);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
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

<style lang="scss">
  // 历史面板 tippy 样式
  .tippy-box[data-theme~='history-panel'] {
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    padding: 0;

    .tippy-content {
      padding: 0px;
    }
  }
</style>
