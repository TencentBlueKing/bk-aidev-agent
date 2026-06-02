<template>
  <teleport :to="props.teleportTo">
    <div :class="['ai-blueking-v2', props.extCls]">
      <!-- 可拖拽容器 -->
      <draggable-container
        ref="draggableContainerRef"
        :compressed-padding="props.miniPadding"
        :default-height="props.defaultHeight"
        :default-width="props.defaultWidth"
        :default-x="props.defaultLeft"
        :default-y="props.defaultTop"
        :drag-handle="'.drag-handle'"
        :draggable="props.draggable"
        :max-width="props.maxWidth"
        :max-width-percent="80"
        :visible="panelVisible"
        @compression-change="handleCompressionChange"
        @drag-stop="handleDragStop"
        @dragging="handleDragging"
        @resize-stop="handleResizeStop"
        @resizing="handleResizing"
      >
        <div :class="['ai-blueking-panel', { 'has-messages': !isWelcomeState }]">
          <!-- 独立的 Header 组件 -->
          <AIHeader
            v-if="!props.hideHeader"
            :agent-name="agentName"
            :chat-helper="chatHelper"
            :draggable="props.draggable"
            :dropdown-menu-config="props.dropdownMenuConfig"
            :enable-chat-session="props.enableChatSession"
            :has-permission="hasPermission"
            :has-session-contents="hasSessionContents"
            :auto-generate-loading="autoGenerateLoading"
            :is-compression-height="isCompressed"
            :render-mode="props.renderMode"
            :session-business-manager="sessionBusinessManager"
            :session-name="sessionName"
            :show-compression-icon="props.showCompressionIcon"
            :show-history-icon="props.showHistoryIcon"
            :show-more-icon="props.showMoreIcon"
            :show-new-chat-icon="props.showNewChatIcon"
            :title="props.title"
            @auto-generate-name="handleAutoGenerateName"
            @close="handleClose"
            @help-click="handleHelpClick"
            @history-click="handleHistoryClick"
            @history-session-delete="handleHistorySessionDelete"
            @history-session-rename="handleHistorySessionRename"
            @history-session-switch="handleHistorySessionSwitch"
            @new-chat="handleNewChat"
            @new-chat-created="handleNewChatCreated"
            @rename="handleRename"
            @share="handleShare"
            @toggle-compression="handleToggleCompression"
          >
            <template
              v-if="$slots.headerLeft"
              #headerLeft
            >
              <slot name="headerLeft" />
            </template>
          </AIHeader>

          <!-- ChatBot 核心组件（仅聊天区域） -->
          <ChatBot
            ref="chatBotRef"
            :always-create-new-session="props.alwaysCreateNewSession"
            :auto-load="props.loadRecentSessionOnMount"
            :chat-helper="chatHelper"
            :hello-text="props.helloText"
            :message-tools-tippy-options="messageToolsTippyOptions"
            :placeholder="props.placeholder"
            :prompts="agentPrompts"
            :render-mode="props.renderMode"
            :request-options="props.requestOptions"
            :use-agent-name="props.useAgentName"
            :get-side-render-component="props.getSideRenderComponent"
            :get-side-tab-render-component="props.getSideTabRenderComponent"
            :on-custom-tab-change="props.onCustomTabChange"
            :resize-props="props.resizeProps"
            :resources="agentResources"
            :session-code="props.initialSessionCode"
            :share-loading="isShareLoading"
            :shortcuts="props.shortcuts"
            :skills="agentSkills"
            :style="{ height: props.hideHeader ? '100%' : 'calc(100% - 48px)' }"
            :url="normalizedUrl"
            @cancel-share="handleCancelShare"
            @confirm-share="(messages: Message[]) => handleConfirmShare(messages)"
            @error="(err: Error) => handleError(err)"
            @execution-panel-change="handleExecutionPanelChange"
            @receive-end="handleReceiveEnd"
            @receive-start="handleReceiveStart"
            @receive-text="handleReceiveText"
            @request-share="handleShare"
            @send-message="(msg: string) => handleSendMessage(msg)"
            @session-switched="(session: ISession | null) => handleSessionSwitched(session)"
            @shortcut-click="handleShortcutClick"
            @stop="handleStop"
          >
            <template
              v-if="$slots.codeHeader"
              #codeHeader="slotProps"
            >
              <slot
                name="codeHeader"
                v-bind="slotProps"
              />
            </template>
            <template
              v-if="$slots.message"
              #message="slotProps"
            >
              <slot
                name="message"
                v-bind="slotProps"
              />
            </template>
          </ChatBot>
        </div>
      </draggable-container>

      <!-- Nimbus 悬浮球 -->
      <nimbus-button
        v-if="!props.hideNimbus"
        v-model:is-minimize="nimbusMinimized"
        v-model:is-panel-show="panelVisible"
        :default-minimize="props.defaultMinimize"
        :size="props.nimbusSize"
        @click="handleNimbusClick"
      />

      <!-- 划词选择弹窗（使用 chat-x 的 AiSelection 组件） -->
      <AiSelection
        v-if="props.enablePopup"
        v-model:visible="aiSelectionVisible"
        :exclude-selectors="['.draggable-container-wrapper']"
        :max-shortcut-count="props.shortcutLimit"
        :shortcuts="filteredPopupShortcuts"
        @select-shortcut="handleAiSelectionShortcut"
        @selection-change="handleSelectionChange"
      />
    </div>
  </teleport>
</template>

<script setup lang="ts">
  import { AiSelection } from '@blueking/chat-x';

  import AIHeader from './components/ai-header/index.vue';
  import ChatBot from './components/chat-bot.vue';
  import {
    useAiBluekingInit,
    useAiSelection,
    usePanelContainer,
    useSessionHandlers,
    useShareHandlers,
  } from './composables';
  import { defaultProps } from './config';
  import { DraggableContainer } from './containers';
  import NimbusButton from './views/nimbus.vue';

  import type { AIBluekingEmits, AIBluekingExpose, AIBluekingProps, ISession } from './types';
  import type { Message, MessageToolsStatus } from '@blueking/chat-x';

  const props = withDefaults(defineProps<AIBluekingProps>(), defaultProps);
  const emit = defineEmits<AIBluekingEmits>();
  defineSlots<{
    codeHeader?: (props: { language: string; token: unknown[] }) => unknown;
    headerLeft?: () => unknown;
    message?: (props: { message: Message; messageToolsStatus?: MessageToolsStatus }) => unknown;
  }>();

  // ==================== 1. 核心初始化 ====================
  const {
    chatHelper,
    componentManager,
    sessionBusinessManager,
    shareBusinessManager,
    shortcutManager,
    forwarders,
    forwardToManager,
    chatBotRef,
    draggableContainerRef,
    panelVisible,
    nimbusMinimized,
    normalizedUrl,
    agentName,
    currentSession,
    isCompressed,
    isWelcomeState,
    messageToolsTippyOptions,
    agentResources,
    agentPrompts,
    agentSkills,
    handleError,
    ensureSessionReady,
    updateAgentInfo,
  } = useAiBluekingInit({
    props,
    emit: emit as (event: string, ...args: unknown[]) => void,
  });

  // ==================== 2. 面板/容器控制 ====================
  const {
    show,
    hide,
    handleShow,
    handleClose,
    handleNimbusClick,
    handleDragging,
    handleResizing,
    handleDragStop,
    handleResizeStop,
    handleToggleCompression,
    handleCompressionChange,
    handleExecutionPanelChange,
    sendMessage,
    handleReceiveStart,
    handleReceiveText,
    handleReceiveEnd,
    handleStop,
    stopGeneration,
    setCiteText,
    focusInput,
    selectShortcut,
    sendShortcut,
    getChatHelper,
    updatePosition,
    updateSize,
    updatePositionAndSize,
    handleShortcutClick,
  } = usePanelContainer({
    componentManager,
    chatBotRef,
    forwarders,
    forwardToManager,
    beforeNimbusClick: props.beforeNimbusClick,
    ensureSessionReady,
  });

  // ==================== 3. 会话管理 ====================
  const {
    sessionName,
    hasPermission,
    hasSessionContents,
    autoGenerateLoading,
    handleNewChat,
    handleNewChatCreated,
    handleHistoryClick,
    handleHistorySessionSwitch,
    handleHistorySessionDelete,
    handleHistorySessionRename,
    handleAutoGenerateName,
    handleHelpClick,
    handleRename,
    handleSessionSwitched,
    addNewSession,
    switchToSession,
    updateSessionName,
  } = useSessionHandlers({
    chatHelper,
    sessionBusinessManager,
    chatBotRef,
    forwarders,
    handleError,
    currentSession,
  });

  // ==================== 4. 分享模式 ====================
  const { isShareLoading, handleShare, handleCancelShare, handleConfirmShare } = useShareHandlers({
    shareBusinessManager,
    chatBotRef,
    forwarders,
    handleError,
  });

  // ==================== 5. 划词选择 ====================
  const { aiSelectionVisible, filteredPopupShortcuts, handleSelectionChange, handleAiSelectionShortcut } =
    useAiSelection({
      shortcutManager,
      chatBotRef,
      forwardToManager,
      show,
      props,
    });

  // ==================== 消息发送桥接 ====================
  const handleSendMessage = (message: string) => {
    hasSessionContents.value = true;
    forwarders.sendMessage(message);
  };

  // ==================== Expose ====================
  defineExpose<AIBluekingExpose>({
    show,
    handleShow,
    handleClose,
    hide,
    sendMessage,
    selectShortcut,
    sendShortcut,
    getChatHelper,
    stopGeneration,
    addNewSession,
    switchToSession,
    updateSessionName,
    updatePosition,
    updateSize,
    updatePositionAndSize,
    setCiteText,
    focusInput,
    updateAgentInfo,
  });
</script>

<style lang="scss" scoped>
  .ai-blueking-v2 {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 10000;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
  }

  .ai-blueking-panel {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;

    // overflow: hidden;
    background:
      linear-gradient(
        154deg,
        rgb(163 150 234 / 16%) 0%,
        rgb(187 176 234 / 12%) 8%,
        rgb(95 107 246 / 8%) 13%,
        rgb(35 93 250 / 4%) 35%,
        transparent 50%
      ),
      #fff;
    border-radius: 12px;

    &.has-messages {
      background: #fff;
    }
  }
</style>
