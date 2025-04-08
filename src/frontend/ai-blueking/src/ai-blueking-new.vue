<template>
  <teleport :to="teleportTo">
    <div class="ai-blueking-wrapper">
      <vue-draggable-resizable
        v-if="isShow"
        ref="resizeWrapper"
        :active="isShow"
        :draggable="true"
        :h="height"
        :max-width="maxWidth"
        :min-height="minHeight"
        :min-width="minWidth"
        :parent="true"
        :prevent-deactivation="true"
        :resizable="true"
        :w="width"
        :x="left"
        :y="top"
        class-name="ai-blueking-container-wrapper"
        drag-handle=".drag-handle"
        @dragging="handleDragging"
        @resizing="handleResizing"
      >
        <div class="ai-blueking-container">
          <!-- 顶部栏 -->
          <AiBluekingHeader
            :is-compression-height="isCompressionHeight"
            @close="handleClose"
            @toggle-compression="toggleCompression"
          />

          <div class="content-wrapper">
            <!-- 主要内容区域 -->
            <div :class="`main-content ${sessionContents.length === 0 ? 'greeting-layout' : 'chat-layout'}`">
              <motion.div
                v-if="sessionContents.length === 0"
                class="greeting-box"
                :transition="{
                  duration: 0.5,
                  ease: [0.33, 1, 0.68, 1],
                  type: 'tween',
                }"
                :animate="{ opacity: 1 }"
                :initial="{ opacity: 1 }"
              >
                <div class="greeting-title">
                  {{ t('你好，我是小鲸') }}
                </div>
                <div class="greeting-anmition-wrapper">
                  <motion.div
                    class="greeting-text"
                    :transition="{
                      duration: 1.2,
                      ease: [0.16, 0.77, 0.47, 0.97],
                      scaleX: {
                        type: 'spring',
                        stiffness: 160,
                        damping: 15,
                        mass: 0.5,
                        delay: 0.1,
                      },
                    }"
                    :animate="{ width: 'auto', scaleX: 1 }"
                    :initial="{ width: 0, scaleX: 0 }"
                  >
                    {{ t('输入你的问题，助你高效的完成工作') }}
                  </motion.div>
                </div>
              </motion.div>
              <div
                ref="messageWrapper"
                :style="{ opacity: sessionContents.length > 0 ? 1 : 0 }"
                class="message-wrapper"
              >
                <render-message
                  v-for="(message, index) in sessionContents"
                  :index="index"
                  :key="message.id"
                  :message="message"
                  @delete="handleDelete"
                  @regenerate="handleRegenerate"
                  @resend="handleResend"
                />
              </div>

              <motion.div
                :transition="{
                  duration: 0.5,
                  ease: [0.33, 1, 0.68, 1],
                  type: 'tween',
                  layoutId: 'chat-input',
                }"
                :class="`chat-input-container ${sessionContents.length === 0 ? 'centered' : 'bottom'}`"
                layout
              >
                <div
                  v-if="currentSessionLoading || showScrollToBottom"
                  class="bottom-tools-bar"
                >
                  <BarButton
                    v-if="currentSessionLoading"
                    color="#EA3636"
                    icon="icon-tingzhishengcheng"
                    text="停止生成"
                    @click="handleStop"
                  />
                  <BarButton
                    v-if="showScrollToBottom"
                    color="#979BA5"
                    icon="icon-jiantou"
                    text="返回底部"
                    @click="scrollMainToBottom"
                  />
                </div>
                <ChatInputBox
                  v-model="inputMessage"
                  :loading="currentSessionLoading"
                  :prompts="props.prompts"
                  :shortcuts="shortcuts"
                  @height-change="handleInputHeightChange"
                  @send="handleSendMessage"
                  @shortcut-click="handleShortcutClick"
                  @stop="handleStop"
                />
              </motion.div>
            </div>
          </div>
        </div>
      </vue-draggable-resizable>
      <Nimbus
        v-model:is-panel-show="isShow"
        :default-minimize="defaultMinimize"
        v-model:is-minimize="isNimbusMinimize"
        @click="handleNimbusClick"
      />
      <RenderPopup
        :shortcuts="shortcuts"
        @click="isShow = true"
        @shortcut-click="handleShortcutClick"
      />
    </div>
  </teleport>
</template>

<script setup lang="ts">
  import { computed, provide, ref, nextTick, watch, defineExpose } from 'vue';
  import VueDraggableResizable from 'vue-draggable-resizable';
  import type { IRequestOptions } from './types';

  import { useChat, useStyle, useClickProxy, type ISession, ShortCut } from '@blueking/ai-ui-sdk';
  import { motion } from 'motion-v';

  import AiBluekingHeader from './components-new/ai-header.vue';
  import BarButton from './components-new/bar-button.vue';
  import ChatInputBox from './components-new/chat-input-box.vue';
  import renderMessage from './components-new/render-message.vue';
  import RenderPopup from './components-new/render-popup.vue';
  import { POPUP_INJECTION_KEY } from './composables/use-popup-props';
  import { useResizableContainer } from './composables/use-resizable-container';
  import { useSelect } from './composables/use-select-pop';
  import { DEFAULT_SHORTCUTS } from './config';
  import { t } from './lang';
  import { scrollToBottom, escapeHtml } from './utils';
  import Nimbus from './views/nimbus.vue';

  import 'vue-draggable-resizable/style.css';

  // 类型定义
  interface Props {
    enablePopup?: boolean;
    shortcuts?: ShortCut[];
    url?: string;
    prompts?: string[];
    requestOptions?: IRequestOptions;
    defaultMinimize?: boolean;
    teleportTo?: string;
  }

  // Props 定义
  const props = withDefaults(defineProps<Props>(), {
    enablePopup: true,
    shortcuts: () => DEFAULT_SHORTCUTS,
    url: '',
    prompts: () => [],
    requestOptions: () => ({}),
    defaultMinimize: false,
    teleportTo: 'body',
  });

  // Emits 定义
  const emit = defineEmits<{
    (e: 'shortcut-click', shortcut: ShortCut): void;
    (e: 'close' | 'show' | 'stop'): void;
  }>();

  // 提供 popup 注入
  provide(POPUP_INJECTION_KEY, props.enablePopup);

  // 状态管理
  const resizeWrapper = ref<InstanceType<typeof VueDraggableResizable>>();
  const isShow = ref(false);
  const inputMessage = ref('');
  const messageWrapper = ref<HTMLElement>();
  const showScrollToBottom = ref(false);
  const isNimbusMinimize = ref(props.defaultMinimize);
  let lastScrollTop = 0; // 上一次的滚动位置, 用于判断是否向下滑动

  // 使用可调整大小的容器
  const {
    minWidth,
    minHeight,
    maxWidth,
    top,
    left,
    width,
    height,
    isCompressionHeight,
    handleDragging,
    handleResizing,
    toggleCompression,
  } = useResizableContainer({ maxWidthPercent: 80 });

  const inputHeight = ref(68);

  const handleInputHeightChange = (height: number) => {
    inputHeight.value = height;
  };

  const contentMarginBottom = computed(() => {
    const toolsBarHeight = 40;
    const offSetHeight = selectedText.value ? 100 : 70;
    return inputHeight.value + toolsBarHeight + offSetHeight;
  });

  const { selectedText, citeText, setCiteText } = useSelect(props.enablePopup);

  const handleClose = () => {
    isShow.value = false;
    emit('close');
  };

  const handleShow = () => {
    isShow.value = true;
    emit('show');
  };

  const handleNimbusClick = () => {
    handleShow();
  };

  // 初始化样式和点击代理
  useStyle();
  useClickProxy();

  // 初始化会话信息
  const session: ISession = {
    sessionCode: '1',
    sessionName: 'test',
    model: '',
  };

  // 添加用户滚动跟踪变量
  const userScrolling = ref(false);

  // 重置用户滚动状态的函数
  const resetUserScrolling = () => {
    userScrolling.value = false;
  };

  // 处理用户滚动事件
  const handleUserScroll = () => {
    if (!messageWrapper.value) return;

    userScrolling.value = true;

    const { scrollTop, scrollHeight, clientHeight } = messageWrapper.value;
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50;

    // 更新返回底部按钮的显示状态
    showScrollToBottom.value = !isNearBottom && scrollHeight > clientHeight;

    // 只有向下滑动且接近底部时才重置滚动状态
    if (isNearBottom && scrollTop > lastScrollTop) {
      resetUserScrolling();
    }
    lastScrollTop = scrollTop;
  };

  // 监听滚动容器
  watch(messageWrapper, el => {
    if (el) {
      el.addEventListener('scroll', handleUserScroll);
    }
  });

  // 使用聊天功能
  const {
    currentSession,
    sessionContents,
    sendChat,
    stopChat,
    setCurrentSession,
    currentSessionLoading,
    reGenerateChat,
    reSendChat,
    deleteChat,
  } = useChat({
    handleStart: () => {
      scrollToBottomIfNeeded();
    },
    handleText: () => {
      scrollToBottomIfNeeded();
    },
    handleEnd: () => {
      scrollToBottomIfNeeded();
    },
    requestOptions: {
      url: props.url,
      ...props.requestOptions,
    },
  });
  setCurrentSession(session);

  const scrollMainToBottom = () => {
    messageWrapper.value?.scrollTo({
      top: messageWrapper.value.scrollHeight,
      behavior: 'smooth',
    });
  };

  // 滚动到底部的辅助函数
  const scrollToBottomIfNeeded = () => {
    // 如果用户正在滚动查看历史消息，则不自动滚动
    if (userScrolling.value) return;

    if (messageWrapper.value) {
      scrollToBottom(messageWrapper.value);
    }
  };

  // 事件处理
  const handleSendMessage = (message: string) => {
    if (!message.trim()) return;

    // 发送新消息时重置用户滚动状态
    resetUserScrolling();

    // HTML转义功能 防止被当做 HTML 标签渲染
    const escapedMessage = escapeHtml(message);

    sendChat(
      {
        message: escapedMessage,
        cite: citeText.value,
      },
      () => {
        nextTick(scrollToBottomIfNeeded);
      },
    );

    // 清空输入
    inputMessage.value = '';
    setCiteText('');
  };

  const handleRegenerate = (index: number) => {
    reGenerateChat(index);
  };

  const handleResend = (index: number, value: { message: string; cite: string }) => {
    reSendChat(index, value);
  };

  const handleStop = () => {
    if (currentSession?.value?.sessionCode) {
      stopChat(currentSession.value.sessionCode);
      emit('stop');
    }
  };

  const handleShortcutClick = (shortcut: ShortCut) => {
    !isShow.value && handleShow();

    sendChat({
      message: shortcut.label,
      cite: selectedText.value || inputMessage.value,
      shortcut,
    });

    emit('shortcut-click', shortcut);
  };

  const handleDelete = (index: number) => {
    deleteChat(index);
  };

  // 监听消息列表变化，自动滚动到底部
  watch(
    sessionContents,
    () => {
      nextTick(scrollToBottomIfNeeded);
    },
    { deep: true },
  );

  defineExpose({
    sessionContents,
    handleShow,
    handleClose,
    handleStop,
    sendChat,
    handleSendMessage,
    handleShortcutClick,
    handleDelete,
    handleRegenerate,
    handleResend,
  });
</script>

<style lang="scss" scoped>
  @import './styles/mixins.scss';

  .ai-blueking-wrapper {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 10000;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
  }

  .ai-blueking-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    pointer-events: auto;
    background: #ffffff;
    border-radius: 2px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.2);

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

  .ai-blueking-container {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }

  .content-wrapper {
    position: relative;
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .main-content {
    position: relative;
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    height: 100%;
    padding: 16px;
    overflow-y: auto;

    .bottom-tools-bar {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }

    .message-wrapper {
      position: relative;
      display: flex;
      flex: 1;
      flex-direction: column;
      gap: 32px;
      min-height: 0;
      padding: 0 16px;
      margin-right: -16px;
      margin-bottom: v-bind('contentMarginBottom + "px"');
      margin-left: -16px;
      overflow-y: auto;
      transition: opacity 0.5s ease;

      @include custom-scrollbar;
    }

    &.chat-layout {
      gap: 0;
    }

    .greeting-box {
      position: absolute;
      top: 92px;
      left: 50%;
      z-index: 2;
      display: flex;
      flex-direction: column;
      gap: 8px;
      align-items: center;
      width: 100%;
      pointer-events: none;
      transform: translateX(-50%);

      .greeting-anmition-wrapper {
        overflow: hidden;
      }

      .greeting-title {
        margin-bottom: 22px;
        font-size: 21px;
        font-weight: 700;
        line-height: 24px;
        color: #313238;
      }

      .greeting-text {
        width: fit-content;
        font-size: 14px;
        line-height: 22px;
        color: #4d4f56;
        white-space: nowrap;
        transform-origin: left;
      }
    }

    .chat-input-container {
      z-index: 3;
      width: 100%;
      outline: none;
      transform-origin: center;
      will-change: transform;

      &.centered {
        position: absolute;
        top: 188px;
        left: 50%;
        width: calc(100% - 32px);

        /* stylelint-disable-next-line declaration-no-important */
        transform: translate(-50%, 0) !important;
      }

      &.bottom {
        position: absolute;
        right: 16px;
        bottom: 16px;
        left: 16px;
        width: calc(100% - 32px);
      }
    }
  }

  .action-icon {
    cursor: pointer;
    opacity: 0.7;

    &:hover {
      opacity: 1;
    }
  }

  // 添加 Nimbus 相关样式
  :deep(.vdr) {
    background: transparent;
    border: none;
  }
</style>
