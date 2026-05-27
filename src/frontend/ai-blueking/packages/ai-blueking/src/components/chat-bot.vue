<template>
  <div
    :class="['ai-chatbot', props.extCls, { 'welcome-state': isWelcomeState }]"
    :style="chatbotStyle"
  >
    <ChatContainer
      ref="chatContainerRef"
      v-model:cite="cite"
      v-model:selected-shortcut="selectedShortcut"
      v-model:render-mode="internalRenderMode"
      :chat-loading="effectiveChatLoading"
      :common-tippy-options="messageToolsTippyOptions"
      :message-status="messageStatus"
      :message-tools-status="messageToolsStatus"
      :messages="messages"
      :model-value="userInput"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :get-side-render-component="props.getSideRenderComponent"
      :get-side-tab-render-component="props.getSideTabRenderComponent"
      :on-custom-tab-change="effectiveOnCustomTabChange"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-upload="handleUpload"
      :on-user-action="handleUserAction"
      :on-user-input-confirm="handleUserInputConfirm"
      :on-user-shortcut-confirm="handleUserShortcutConfirm"
      :opening-remark="openingRemark"
      :placeholder="props.placeholder"
      :placement="props.placement"
      :prompts="effectivePrompts"
      :resize-props="props.resizeProps"
      :resources="effectiveResources"
      :shortcut-id="selectedShortcut?.id"
      :shortcuts="filteredShortcuts"
      :support-upload="effectiveSupportUpload"
      @collapse-change="handleExecutionPanelChange"
      @confirm-share="handleConfirmShare"
      @delete-shortcut="handleCloseShortcut"
      @select-shortcut="handleSelectShortcut"
      @shortcut-close="handleCloseShortcut"
      @shortcut-submit="handleShortcutSubmit"
      @stop-streaming="handleStopStreaming"
      @update:model-value="handleUpdateModelValue"
    >
      <template #message="{ message, messageToolsStatus }">
        <!-- 消费方提供了 #message slot 时，优先使用消费方的渲染 -->
        <slot
          v-if="slots.message"
          name="message"
          :message="message"
          :message-tools-status="messageToolsStatus"
        />
        <!-- 否则使用默认的 MessageRender -->
        <MessageRender
          v-else
          :message="message"
          :message-tools-status="messageToolsStatus"
          :on-action="tool => handleUserAction(tool, message)"
          :on-input-confirm="(content, docSchema) => handleUserInputConfirm(message, content, docSchema)"
          :on-shortcut-confirm="formModel => handleUserShortcutConfirm(message, formModel)"
          :tippy-options="messageToolsTippyOptions"
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
        </MessageRender>
      </template>
    </ChatContainer>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref, shallowRef, useSlots } from 'vue';

  import { ChatContainer, ChatInput, MessageRender } from '@blueking/chat-x';
  import { RenderMode } from '@blueking/chat-x';
  // import { Loading } from 'bkui-vue';

  import { useChatbotInit } from './composables/use-chatbot-init';
  import { useChatbotState } from './composables/use-chatbot-state';
  import { useMessageSender } from './composables/use-message-sender';
  import { useShareSelection } from './composables/use-share-selection';
  import { useShortcuts } from './composables/use-shortcuts';
  import { useToolActions } from './composables/use-tool-actions';
  // import SelectionFooter from './selection-footer/selection-footer.vue';

  import type { IShortcut } from '../manager/business/types';
  import type { IChatHelper } from '../types';
  import type { ChatBotEmits, ChatBotExpose, ChatBotProps } from './types';
  import type { ISupportUpload } from '@blueking/chat-helper';
  import type { CustomBkFlowTab, IAiSlashMenuItem, Message, MessageToolsStatus, Shortcut } from '@blueking/chat-x';

  const props = withDefaults(defineProps<ChatBotProps>(), {
    chatHelper: undefined,
    url: '',
    enableSelection: false,
    shareLoading: false,
    autoLoad: true,
    shortcuts: () => [],
    resources: () => [],
    renderMode: RenderMode.Chat,
    placement: 'left',
  });

  const emit = defineEmits<ChatBotEmits>();
  const slots = useSlots();
  defineSlots<{
    codeHeader?: (props: { language: string; token: unknown[] }) => unknown;
    message?: (props: { message: Message; messageToolsStatus?: MessageToolsStatus }) => unknown;
  }>();

  // ==================== Template Refs ====================
  const messagesContainerRef = ref<HTMLElement>();
  const chatContainerRef = ref<InstanceType<typeof ChatContainer>>();
  const chatInputRef = ref<InstanceType<typeof ChatInput>>();

  // 共享 ref（由组装层创建，注入到多个 composable）
  const selectedResources = shallowRef<IAiSlashMenuItem[]>([]);
  const selectedShortcut = ref<null | (Shortcut & { supportUpload?: ISupportUpload })>(null);

  // 渲染模式：由 props 驱动，传给 ChatContainer 的 v-model:renderMode
  const internalRenderMode = computed({
    get: () => props.renderMode ?? RenderMode.Chat,
    set: () => {}, // ChatContainer 可能 set，但由父组件 props 控制，忽略
  });

  // ==================== 滚动辅助 ====================
  const scrollToBottom = async () => {
    await nextTick();
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight;
    }
  };

  // 聚焦输入框
  const focusInput = () => {
    chatInputRef.value?.focus?.();
  };

  // ==================== Composable 组装 ====================

  // 1. 初始化 + 生命周期
  const {
    chatHelper,
    isStandaloneMode,
    isInitialized,
    isReady,
    initError,
    whenReady,
    chatBusinessManager,
    sessionBusinessManager,
    shortcutManager,
  } = useChatbotInit({ props, emit, scrollToBottom });

  // 2. 消息发送（先于 shortcuts，解决循环依赖）
  const {
    userInput,
    cite,
    handleUpdateModelValue,
    doSendMessage,
    handleSendMessage,
    handleUpload,
    handleStopSending,
    stopGeneration,
  } = useMessageSender({ emit, chatHelper, chatBusinessManager, selectedShortcut, selectedResources });

  // 3. 快捷指令
  const {
    handleSelectShortcut,
    handleCloseShortcut,
    handleShortcutSubmit,
    selectShortcutWithText,
    getShortcutFromMessage,
    buildShortcutProperty,
    sendShortcutDirectly,
  } = useShortcuts({ props, emit, chatHelper, shortcutManager, doSendMessage, selectedShortcut });

  // 4. 派生状态
  const {
    messageStatus,
    messageToolsStatus,
    messages,
    isMessagesLoading,
    isGenerating,
    currentSession,
    isWelcomeState,
    openingRemark,
    effectiveResources,
    effectivePrompts,
    effectiveSupportUpload,
    chatbotStyle,
    filteredShortcuts,
  } = useChatbotState({
    props,
    chatHelper,
    chatBusinessManager,
    sessionBusinessManager,
    shortcutManager,
    isStandaloneMode,
    isInitialized,
    selectedShortcut,
  });

  // 5. 工具栏动作
  const {
    handleAgentAction,
    handleAgentFeedback,
    handleUserAction,
    handleUserInputConfirm,
    handleUserShortcutConfirm,
    handleStopStreaming,
  } = useToolActions({
    emit,
    chatHelper,
    chatBusinessManager,
    cite,
    focusInput,
    scrollToBottom,
    getShortcutFromMessage,
    buildShortcutProperty,
  });

  // 初始化期间（含 URL 变化重新初始化），委托 ChatContainer 内置 loading
  // 独立模式和非独立模式（AIBlueking）统一处理
  const effectiveChatLoading = computed(() => !isInitialized.value || isMessagesLoading.value);

  // 6. 分享确认（选择模式 UI 由 ChatContainer 内部管理）
  const { handleConfirmShare } = useShareSelection({
    emit,
    chatHelper,
    isStandaloneMode,
  });

  // ==================== 执行情况面板联动 ====================
  const handleExecutionPanelChange = (isCollapse: boolean) => {
    emit('execution-panel-change', isCollapse);
  };

  // ==================== 自定义 Tab 数据加载 ====================
  const effectiveOnCustomTabChange = async (tab: CustomBkFlowTab) => {
    if (props.onCustomTabChange) {
      return props.onCustomTabChange(tab);
    }
    const tabProps = tab.data?.props;
    if (tabProps?.task_id != null && tabProps?.node_id) {
      return chatHelper.value?.message.getFlowAgentTaskNodeInfo(tabProps.task_id, tabProps.node_id);
    }
  };

  // ==================== 辅助方法 ====================

  // 切换会话
  const switchSession = async (sessionCode: string) => {
    if (!sessionBusinessManager.value) {
      console.error('[ChatBot] Cannot switch session: sessionBusinessManager not initialized');
      return;
    }
    try {
      await sessionBusinessManager.value.switchSession(sessionCode);
      emit('session-switched', sessionBusinessManager.value.currentSession.value);
    } catch (error) {
      console.error('Failed to switch session:', error);
      emit('error', error as Error);
    }
  };

  // 设置引用文本
  const setCiteText = (text: string) => {
    cite.value = text;
  };

  // 获取 chatHelper 实例
  const getChatHelper = (): IChatHelper | null => chatHelper.value;

  // ==================== Expose ====================
  defineExpose<ChatBotExpose>({
    sendMessage: (message: string) => handleSendMessage(message, [[]]),
    stopGeneration,
    switchSession,
    messages,
    currentSession,
    isGenerating,
    isReady,
    whenReady,
    getChatHelper,
    setCiteText,
    focusInput,
    enterShareMode: () => chatContainerRef.value?.enterShareMode(),
    exitShareMode: () => chatContainerRef.value?.exitShareMode(),
    selectShortcut: (shortcut: IShortcut, selectedText?: string) => {
      selectShortcutWithText(shortcut as unknown as Shortcut, selectedText);
    },
    sendShortcut: (shortcut: IShortcut, selectedText?: string) => {
      return sendShortcutDirectly(shortcut as unknown as Shortcut, selectedText);
    },
  });
</script>

<style lang="scss">
  .ai-chatbot {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;

    // overflow: hidden;
    background: transparent;
    border-radius: 12px;

    // 欢迎状态：视觉上靠上的布局
    &.welcome-state {
      justify-content: flex-start;
      padding-top: 15vh;
    }

    .chatbot-welcome {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      max-height: 100%;
      padding: 16px;
      overflow: hidden;

      .welcome-content {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
        padding-top: 80px;
        margin-bottom: 24px;
        text-align: center;
      }

      .welcome-banner {
        position: absolute;
        top: 0;
        left: 50%;
        width: 309px;
        height: auto;
        transform: translateX(-50%);
      }

      .welcome-title {
        position: relative;
        margin: 0 0 16px;
        font-size: 20px;
        font-weight: 600;
        line-height: 28px;
        color: #313238;
      }

      .welcome-remark {
        width: 100%;
        max-height: 200px;
        overflow-y: auto;
        font-size: 12px;
        line-height: 20px;
        color: #63656e;

        &::-webkit-scrollbar {
          width: 4px;
        }

        &::-webkit-scrollbar-thumb {
          background: #dcdee5;
          border-radius: 2px;
        }

        // 覆盖 markdown-content 的样式，内容居中但容器宽度占满
        .markdown-content {
          .markdown-body {
            text-align: center;
          }
        }
      }
    }

    .chatbot-messages {
      flex: 1;
      padding: 16px 0 16px 16px;
      overflow-y: auto;
      scrollbar-color: #dcdee5 transparent;

      // Firefox 滚动条样式
      scrollbar-width: thin;

      // 滚动条样式优化
      &::-webkit-scrollbar {
        width: 6px;
      }

      &::-webkit-scrollbar-track {
        background: transparent;
      }

      &::-webkit-scrollbar-thumb {
        background: #dcdee5;
        border-radius: 3px;
        transition: background 0.2s;

        &:hover {
          background: #c4c6cc;
        }
      }

      .message-group {
        max-width: 1000px;
        padding-right: 16px;
        margin-right: auto;
        margin-left: auto;
      }
    }

    .message-wrapper {
      .message-tools-hover {
        opacity: 0;
        transition: opacity 0.2s ease-in-out;
      }

      &:hover .message-tools-hover {
        opacity: 1;
      }
    }

    .chatbot-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      font-size: 12px;
      color: #979ba5;
    }

    .chatbot-error {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      padding: 16px;
      font-size: 12px;
      color: #ea3636;
      text-align: center;
    }

    .ai-chat-container-loading,
    .ai-chat-container-resize-layout {
      animation: chatbot-content-fade-in 0.3s ease-out;
    }

    .chatbot-input {
      width: 100%;
      max-width: 1032px;
      padding: 16px;
      margin: 0 auto;
    }
  }

  @keyframes chatbot-content-fade-in {
    from {
      opacity: 0;
    }

    to {
      opacity: 1;
    }
  }
</style>
