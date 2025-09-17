<template>
  <teleport :to="teleportTo">
    <div :class="['ai-blueking-wrapper', props.extCls ?? '']">
      <vue-draggable-resizable
        v-if="isShow"
        ref="resizeWrapper"
        :active="isShow"
        :draggable="props.draggable"
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
        <div
          ref="rootNode"
          class="ai-blueking-container"
        >
          <loading-overlay :show="isLoadingSessionContents" />
          <!-- 顶部栏 -->
          <ai-blueking-header
            v-if="!props.hideHeader"
            :title="props.title"
            :is-compression-height="isCompressionHeight"
            :draggable="props.draggable"
            :show-history-icon="props.showHistoryIcon"
            :show-new-chat-icon="props.showNewChatIcon"
            :enable-chat-session="enableChatSession"
            :chat-group="sessionStore.agentInfo.value?.chatGroup"
            :has-session-contents="hasSessionContents"
            @close="handleClose"
            @toggle-compression="toggleCompression"
            @new-chat="handleNewChat"
            @auto-generate-name="handleAutoGenerateName"
            @help-click="() => enterSelectMode('transfer')"
          />
          <div class="content-wrapper">
            <!-- 主要内容区域 -->
            <div :class="`main-content ${!hasSessionContents ? 'greeting-layout' : 'chat-layout'}`">
              <greeting-section
                ref="greetingSectionRef"
                :title="props.helloText"
                :greeting-text="greetingText"
                :has-session-contents="hasSessionContents"
                :render-markdown="renderMarkdown"
                :greeting-max-height="greetingMaxHeight"
              />
              <message-list
                ref="messageListRef"
                :session-contents="sessionContents"
                :has-session-contents="hasSessionContents"
                :content-margin-bottom="contentMarginBottom"
                :is-select-mode="sessionStore.isSelectMode.value"
                :is-message-selected="sessionStore.isMessageSelected"
                @delete="handleDelete"
                @regenerate="handleRegenerate"
                @resend="handleResend"
                @message-select="sessionStore.toggleMessageSelection"
                @scroll-position-change="handleScrollPositionChange"
              />
              <!-- 选择模式下的底部确认区域 -->
              <div
                v-if="sessionStore.isSelectMode.value"
                class="selection-footer"
              >
                <div class="selection-info">
                  <bk-checkbox
                    :model-value="isSelectAll"
                    :indeterminate="isIndeterminate"
                    label="全选"
                    @change="handleSelectAllChange"
                  />
                </div>
                <div class="selection-actions">
                  <bk-button
                    class="cancel-btn"
                    @click="handleCancelSelection"
                  >
                    {{ t('取消') }}
                  </bk-button>
                  <bk-button
                    class="confirm-btn"
                    :loading="loading"
                    theme="primary"
                    @click="handleConfirmSelection"
                  >
                    {{ t('确定') }}
                  </bk-button>
                </div>
              </div>

              <motion.div
                v-else
                :transition="{
                  duration: 0.5,
                  ease: [0.33, 1, 0.68, 1],
                  type: 'tween',
                  layoutId: 'chat-input',
                }"
                :class="`chat-input-container ${!hasSessionContents ? 'centered' : 'bottom'}`"
                :style="hasSessionContents ? undefined : inputContainerStyle"
                layout
              >
                <div class="chat-input-wrapper">
                  <div
                    v-if="currentSessionLoading || showScrollToBottom"
                    class="bottom-tools-bar"
                  >
                    <bar-button
                      v-if="currentSessionLoading"
                      color="#EA3636"
                      icon="bkai-icon bkai-tingzhishengcheng"
                      :text="t('停止生成')"
                      @click="handleStop"
                    />
                    <bar-button
                      v-if="showScrollToBottom"
                      color="#979BA5"
                      icon="bkai-icon bkai-jiantou"
                      :text="t('返回底部')"
                      @click="handleScrollMainToBottom"
                    />
                  </div>
                  <custom-input
                    v-if="currentShortcut"
                    :key="currentShortcut.id"
                    :shortcut="currentShortcut"
                    :root-node="rootNode"
                    @cancel="handleCancelShortcut"
                    @submit="handleSubmitShortcut"
                  />

                  <chat-input-box
                    v-else
                    v-model="inputMessage"
                    :class="!hasSessionContents ? 'greeting-layout' : 'chat-layout'"
                    :loading="currentSessionLoading || false"
                    :prompts="promptList"
                    :shortcuts="props.shortcuts"
                    :shortcut-filter="props.shortcutFilter"
                    :conversation-settings="sessionStore.agentInfo.value?.conversationSettings"
                    :disabled="props.disabledInput"
                    @height-change="handleInputHeightChange"
                    @send="handleSendMessage"
                    @shortcut-click="handleInputShortcutClick"
                    @stop="handleStop"
                  />
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </vue-draggable-resizable>
      <nimbus
        v-if="!props.hideNimbus"
        v-model:is-panel-show="isShow"
        v-model:is-minimize="isNimbusMinimize"
        :default-minimize="defaultMinimize"
        :size="props.nimbusSize"
        @click="handleNimbusClick"
      />
      <render-popup
        :shortcuts="props.shortcuts"
        :conversation-settings="sessionStore.agentInfo.value?.conversationSettings"
        :shortcut-limit="props.shortcutLimit"
        :shortcut-filter="props.shortcutFilter"
        @click="isShow = true"
        @shortcut-click="handlePopupShortcutClick"
      />
    </div>
  </teleport>
</template>

<script setup lang="ts">
  // ===================================================================
  // 1. 导入和类型定义
  // ===================================================================
  import { SessionContentRole } from '@blueking/ai-ui-sdk/enums';
  import { useChat, useStyle, useClickProxy } from '@blueking/ai-ui-sdk/hooks';
  import { Button as BkButton, Checkbox as BkCheckbox } from 'bkui-vue';
  import { useCopyCode } from 'markdown-it-copy-code';
  import { motion } from 'motion-v';
  import {
    computed,
    defineEmits,
    defineExpose,
    defineProps,
    nextTick,
    onBeforeUnmount,
    onMounted,
    provide,
    ref,
    Ref,
    watch,
    withDefaults,
  } from 'vue';
  import VueDraggableResizable from 'vue-draggable-resizable';

  // 组件导入
  import AiBluekingHeader from './components/ai-header.vue';
  import BarButton from './components/bar-button.vue';
  import ChatInputBox from './components/chat-input-box.vue';
  import CustomInput from './components/custom-inputs/index.vue';
  import GreetingSection from './components/greeting-section.vue';
  import LoadingOverlay from './components/loading-overlay.vue';
  import MessageList from './components/message-list.vue';
  import RenderPopup from './components/render-popup.vue';
  // Composable导入
  import { useGreetingHeight } from './composables/use-greeting-height';
  import { useMarkdown } from './composables/use-markdown';
  import { useMessageList } from './composables/use-message-list';
  import { POPUP_INJECTION_KEY } from './composables/use-popup-props';
  import { useResizableContainer } from './composables/use-resizable-container';
  import { useSelect } from './composables/use-select-pop';
  import { useSelectionMode } from './composables/use-selection-mode';
  import { provideSessionStore } from './composables/use-session-store';
  import { useShortcut } from './composables/use-shortcut';
  // 配置和工具导入
  import { HIDE_ROLE_LIST } from './config';
  import { t } from './lang';
  import type { IRequestOptions, IShortcut } from './types';
  import { escapeHtml, normalizeUrl } from './utils';
  import Nimbus from './views/nimbus.vue';

  // 样式导入
  import 'vue-draggable-resizable/style.css';

  // 类型定义
  interface Props {
    extCls?: string;
    title?: string;
    helloText?: string;
    enablePopup?: boolean;
    shortcuts?: IShortcut[];
    shortcutLimit?: number;
    shortcutFilter?: (shortcut: IShortcut, selectedText: string) => boolean;
    url?: string;
    prompts?: string[];
    hideNimbus?: boolean;
    requestOptions?: IRequestOptions;
    defaultMinimize?: boolean;
    teleportTo?: string;
    draggable?: boolean;
    defaultWidth?: number;
    defaultHeight?: number;
    defaultTop?: number;
    defaultLeft?: number;
    hideHeader?: boolean;
    disabledInput?: boolean;
    nimbusSize?: 'small' | 'normal' | 'large';
    showHistoryIcon?: boolean;
    showNewChatIcon?: boolean;
    placeholder?: string;
    miniPadding?: number;
    initialSessionCode?: string;
    autoSwitchToInitialSession?: boolean;
    loadRecentSessionOnMount?: boolean;
  }

  // ===================================================================
  // 2. Props 和 Emits 定义
  // ===================================================================
  const props = withDefaults(defineProps<Props>(), {
    title: '',
    extCls: '',
    helloText: t('你好，我是小鲸'),
    enablePopup: true,
    shortcuts: () => [],
    shortcutLimit: 3,
    shortcutFilter: undefined,
    url: '',
    prompts: () => [],
    hideNimbus: false,
    requestOptions: () => ({}),
    defaultMinimize: false,
    teleportTo: 'body',
    draggable: true,
    defaultWidth: undefined,
    defaultHeight: undefined,
    defaultTop: undefined,
    defaultLeft: undefined,
    hideHeader: false,
    disabledInput: false,
    nimbusSize: 'normal',
    showHistoryIcon: true,
    showNewChatIcon: true,
    placeholder: t('输入 "/" 唤出 Prompt\n通过 Shift + Enter 进行换行输入'),
    miniPadding: 0,
    initialSessionCode: '',
    autoSwitchToInitialSession: false,
    loadRecentSessionOnMount: false,
  });

  const emit = defineEmits<{
    (e: 'shortcut-click', data: { shortcut: IShortcut; source: 'popup' | 'main' }): void;
    (e: 'close' | 'show' | 'stop' | 'receive-start' | 'receive-text' | 'receive-end'): void;
    (e: 'send-message', message: string): void;
    (
      e: 'session-initialized',
      data: { openingRemark: string; predefinedQuestions: string[] }
    ): void;
    (e: 'sdk-error', data: { apiName: string; code: number; message: string; data: unknown }): void;
    (e: 'transfer-messages', messageIds: string[]): void;
    (e: 'share-messages', messageIds: string[]): void;
  }>();

  // ===================================================================
  // 3. 依赖注入
  // ===================================================================
  provide(POPUP_INJECTION_KEY, props.enablePopup);

  // ===================================================================
  // 4. 核心状态管理
  // ===================================================================
  // DOM引用
  const resizeWrapper = ref<InstanceType<typeof VueDraggableResizable>>();
  const chatInputBoxRef = ref<InstanceType<typeof ChatInputBox>>();
  const rootNode: Ref<HTMLElement | undefined> = ref();

  // UI状态
  const isShow = ref(false);
  const isNimbusMinimize = ref(props.defaultMinimize);
  const inputMessage = ref('');
  const showScrollToBottom = ref(false);

  // 会话状态
  const isSessionInitialized = ref(false);
  let initSessionPromise: Promise<void> | null = null;
  const openingRemark = ref('');
  const predefinedQuestions: Ref<string[]> = ref([]);

  // 窗口状态
  const windowHeight = ref(window.innerHeight);

  // 输入状态
  const inputHeight = ref(68);

  // ===================================================================
  // 5. 会话存储
  // ===================================================================
  const sessionStore = provideSessionStore();

  // ===================================================================
  // 6. 组合式 API 钩子 (Composables)
  // ===================================================================
  // 使用 markdown 渲染功能
  const { renderMarkdown } = useMarkdown();

  // 使用选择文本功能
  const { selectedText, citeText, setCiteText } = useSelect(props.enablePopup);

  // 使用消息列表功能
  const { messageListRef, scrollMainToBottom, scrollToBottomIfNeeded, resetUserScrolling } =
    useMessageList();

  // 使用快捷方式功能
  const { currentShortcut, handleShortcutClick, handleCancelShortcut } = useShortcut({
    selectedText: selectedText,
    isShow: isShow,
    handleShow: () => {
      handleShow();
    },
    handleStop: () => {
      handleStop();
    },
  });

  // 初始化样式和点击代理
  useStyle();
  useClickProxy();

  // ===================================================================
  // 7. UI 和布局管理 (UI & Layout)
  // ===================================================================
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
  } = useResizableContainer({
    maxWidthPercent: 80,
    initWidth: props.defaultWidth,
    defaultHeight: props.defaultHeight,
    defaultTop: props.defaultTop,
    defaultLeft: props.defaultLeft,
    miniPadding: props.miniPadding,
  });

  // 动态计算 greeting 最大高度
  const greetingMaxHeight = computed(() => windowHeight.value - 367);

  // 使用问候语高度计算功能
  const { greetingSectionRef, updateGreetingTextHeight, getInputContainerStyle } =
    useGreetingHeight({
      greetingMaxHeight: greetingMaxHeight.value,
    });

  // 计算输入框的动态位置
  const inputContainerStyle = computed(() => {
    return getInputContainerStyle(hasSessionContents.value);
  });

  // 内容边距计算
  const contentMarginBottom = computed(() => {
    const toolsBarHeight = 40;
    const offSetHeight = selectedText.value ? 100 : 70;
    return inputHeight.value + toolsBarHeight + offSetHeight;
  });

  // ===================================================================
  // 8. 聊天和会话管理 (Chat & Session)
  // ===================================================================

  // 标准化的URL，自动匹配当前页面协议 - **必须在使用它的 useChat 之前定义**
  const normalizedUrl = computed(() => {
    return normalizeUrl(props.url);
  });

  // 使用聊天功能
  const {
    currentSession,
    sessionContents,
    isLoadingSessionContents,
    plusSessionContent,
    plusSessionApi,
    chat,
    stopChat,
    setCurrentSession,
    setCurrentSessionChain,
    currentSessionLoading,
    reGenerateChat,
    reSendChat,
    deleteChat,
    updateRequestOptions,
    getAgentInfoApi,
    getChatGroupApi,
    getSessionsApi,
    getSessionContentsApi,
    modifySessionApi,
    deleteSessionApi,
    renameSessionApi,
    setSessionContents,
    handleCompleteRole,
    stopSessionContentApi,
  } = useChat({
    handleStart: () => {
      scrollToBottomIfNeeded();
      emit('receive-start');
    },
    handleText: () => {
      scrollToBottomIfNeeded();
      emit('receive-text');
    },
    handleEnd: () => {
      scrollToBottomIfNeeded();
      emit('receive-end');
    },
    requestOptions: {
      url: normalizedUrl.value,
      ...props.requestOptions,
    },
    otherOptions: {
      hideReferenceDocIcon: true,
    },
  });

  // 使用选择模式功能
  const {
    handleConfirmSelection,
    handleCancelSelection,
    handleSelectAllChange,
    enterSelectMode,
    isSelectAll,
    isIndeterminate,
    loading,
  } = useSelectionMode({
    sessionStore,
    sessionContents,
    getChatGroupApi,
    onTransferMessages: messageIds => {
      emit('transfer-messages', messageIds);
    },
    onShareMessages: messageIds => {
      emit('share-messages', messageIds);
    },
  });

  // 注册 SDK 的方法
  sessionStore.registerSdkMethods({
    setCurrentSession,
    setCurrentSessionChain,
    setSessionContents,
    modifySessionApi,
    deleteSessionApi,
    renameSessionApi,
    getSessionContentsApi,
    getSessionsApi,
    getAgentInfoApi,
    plusSessionApi,
    handleCompleteRole,
    getChatGroupApi,
  });

  // 注册错误回调函数
  sessionStore.registerErrorCallback(error => {
    emit('sdk-error', error);
  });

  // 提示列表
  const promptList = computed(() => {
    return [...props.prompts, ...predefinedQuestions.value];
  });

  // 是否有会话内容
  const hasSessionContents = computed(() => {
    return sessionContents.value.filter(item => !HIDE_ROLE_LIST.includes(item.role)).length > 0;
  });

  // 是否启用会话管理
  const enableChatSession = computed(() => {
    return sessionStore.agentInfo.value?.conversationSettings?.enableChatSession ?? true;
  });

  // 问候文本
  const greetingText = computed(() => openingRemark.value || t('输入你的问题，助你高效的完成工作'));

  // ===================================================================
  // 9. 会话初始化逻辑
  // ===================================================================
  const initSession = async (loadRecentSession = false) => {
    if (initSessionPromise) {
      await initSessionPromise;
      return;
    }
    if (isSessionInitialized.value && !initSessionPromise) {
      return;
    }

    initSessionPromise = (async () => {
      try {
        const { conversationSettings } = await sessionStore.initSession(true, loadRecentSession);
        openingRemark.value = conversationSettings?.openingRemark || '';
        predefinedQuestions.value = conversationSettings?.predefinedQuestions || [];
        isSessionInitialized.value = true;

        emit('session-initialized', {
          openingRemark: openingRemark.value,
          predefinedQuestions: predefinedQuestions.value,
        });
      } finally {
        initSessionPromise = null;
        updateGreetingTextHeight();
      }
    })();

    await initSessionPromise;
  };

  // ===================================================================
  // 10. Watcher 监听器
  // ===================================================================
  watch(
    () => normalizedUrl.value,
    (newUrl, oldUrl) => {
      if (newUrl !== oldUrl && newUrl) {
        updateRequestOptions({
          url: newUrl,
          ...props.requestOptions,
        });
        isSessionInitialized.value = false;
        initSessionPromise = null;
        initSession();
      }
    }
  );

  watch(
    () => props.requestOptions,
    newOptions => {
      updateRequestOptions({
        url: normalizedUrl.value,
        ...newOptions,
      });
    },
    { deep: true }
  );

  watch(
    sessionContents,
    () => {
      nextTick(scrollToBottomIfNeeded);
    },
    { deep: true }
  );

  watch(
    () => isShow.value,
    newValue => {
      if (newValue) {
        nextTick(() => {
          chatInputBoxRef.value?.focus();
        });
      }
    }
  );

  // ===================================================================
  // 11. 生命周期钩子
  // ===================================================================
  const _switchToSession = async (sessionCode: string) => {
    if (!sessionCode) return;
    //确保在切换会话之前，会话列表已初始化
    if (!isSessionInitialized.value) {
      await initSession();
    }
    const targetSession = sessionStore.sessionList.value.find(s => s.sessionCode === sessionCode);
    if (targetSession) {
      await sessionStore.switchSessionWithContents(targetSession);
      return true;
    }
    return false;
  };
  const handleWindowResize = () => {
    windowHeight.value = window.innerHeight;
  };

  // 处理进入选择模式的自定义事件
  const handleEnterSelectMode = (event: CustomEvent<{ type: 'transfer' | 'share' }>) => {
    const { type } = event.detail;
    enterSelectMode(type);
  };

  // 使用 sendBeacon 发送停止会话请求
  const sendStopSessionRequest = () => {
    if (navigator.sendBeacon && normalizedUrl.value) {
      const stopUrl = `${normalizedUrl.value}/session_content/stop/`;

      // 使用 sendBeacon 发送 POST 请求
      const success = navigator.sendBeacon(stopUrl, new Blob(['{}'], { type: 'application/json' }));

      return success;
    } else {
      // 降级到普通的停止API调用
      stopSessionContentApi();
      return false;
    }
  };

  // 处理页面卸载事件
  const handleUnload = () => {
    sendStopSessionRequest();
  };

  onMounted(async () => {
    // 使用 unload 事件配合 sendBeacon，确保请求能够成功发送
    window.addEventListener('unload', handleUnload);
    window.addEventListener('resize', handleWindowResize);
    window.addEventListener('enter-select-mode', handleEnterSelectMode as EventListener);
    if (normalizedUrl.value && !props.defaultMinimize) {
      await initSession(props.loadRecentSessionOnMount);

      // 如果设置了初始会话代码且需要自动切换，则切换到初始会话
      if (props.initialSessionCode && props.autoSwitchToInitialSession) {
        await _switchToSession(props.initialSessionCode);
      }
    }

    useCopyCode();
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleWindowResize);
    window.removeEventListener('enter-select-mode', handleEnterSelectMode as EventListener);

    // 清理页面卸载相关的事件监听器
    window.removeEventListener('unload', handleUnload);
  });

  // ===================================================================
  // 12. 事件处理函数
  // ===================================================================
  const handlePopupShortcutClick = (data: { shortcut: IShortcut; source: 'popup' | 'main' }) => {
    // 来自 render-popup 的快捷方式点击事件
    emit('shortcut-click', { shortcut: data.shortcut, source: data.source });
    handleShortcutClick(data);
  };

  const handleInputShortcutClick = (data: { shortcut: IShortcut; source: 'popup' | 'main' }) => {
    // 传递_source属性以便custom-input组件可以正确处理自动提交
    const modifiedShortcut = {
      ...data.shortcut,
      _source: data.source,
    };
    emit('shortcut-click', { shortcut: modifiedShortcut, source: data.source });
    handleShortcutClick({ shortcut: modifiedShortcut, source: data.source });
  };

  const handleInputHeightChange = (height: number) => {
    inputHeight.value = height;
  };

  const handleClose = () => {
    isShow.value = false;
    emit('close');
  };

  const handleShow = async (sessionCode?: string) => {
    isShow.value = true;
    emit('show');

    if (!isSessionInitialized.value) {
      await initSession();
    }

    if (sessionCode) {
      await _switchToSession(sessionCode);
    }
    updateGreetingTextHeight();
  };

  const handleNimbusClick = () => {
    handleShow();
  };

  const handleScrollMainToBottom = () => {
    scrollMainToBottom();
    // 滚动到底部后隐藏按钮
    showScrollToBottom.value = false;
  };

  const handleScrollPositionChange = (isNearBottom: boolean) => {
    // 只有当消息容器有内容且不在底部时，才显示返回底部按钮
    const messageWrapper = messageListRef.value?.messageWrapper;
    if (!messageWrapper) return;

    const { scrollHeight, clientHeight } = messageWrapper;
    showScrollToBottom.value = !isNearBottom && scrollHeight > clientHeight;
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return;

    if (!isSessionInitialized.value && normalizedUrl.value) {
      await initSession();
    }

    resetUserScrolling();
    const escapedMessage = escapeHtml(message);

    await plusSessionContent(currentSession.value?.sessionCode, {
      role: SessionContentRole.User,
      content: escapedMessage,
      sessionCode: currentSession.value?.sessionCode,
      property: {
        extra: {
          cite: citeText.value,
          ...(typeof props.requestOptions?.context === 'function'
            ? props.requestOptions?.context()
            : props.requestOptions?.context),
        },
      },
    });

    // 检查是否为当前会话中的第一条用户消息
    const shouldAutoRename = isFirstUserMessageInSession();

    chat({
      sessionCode: currentSession.value?.sessionCode,
      ...props.requestOptions,
    });

    // 在发送第一条用户消息后调用renameSessionApi
    if (shouldAutoRename) {
      try {
        await autoRenameCurrentSession();
      } catch (error) {
        console.error('自动命名会话失败:', error);
      }
    }

    emit('send-message', escapedMessage);
    inputMessage.value = '';
    setCiteText('');
  };

  const handleRegenerate = (index: number) => {
    const sessionContent = sessionContents.value[index];
    if (sessionContent) {
      reGenerateChat(sessionContent.sessionCode, sessionContent, index);
    }
  };

  const handleResend = (index: number, { message }: { message: string }) => {
    const sessionContent = sessionContents.value[index];
    if (sessionContent) {
      sessionContent.content = escapeHtml(message);
      reSendChat(sessionContent.sessionCode, sessionContent, index);
    }
  };

  const handleStop = () => {
    if (currentSession?.value?.sessionCode) {
      stopChat(currentSession.value.sessionCode);
      emit('stop');
    }
  };

  const handleSubmitShortcut = async (data: {
    shortcut: IShortcut;
    formData: Record<string, any>[];
    citeFormData?: Record<string, any>[];
  }) => {
    const { shortcut, formData, citeFormData } = data;
    handleCancelShortcut();
    !isShow.value && handleShow();
    currentSessionLoading.value && handleStop();

    if (!isSessionInitialized.value && normalizedUrl.value) {
      await initSession();
    }

    // 使用 citeFormData（如果提供）否则回退到 formData
    const citeData = citeFormData || formData;

    await plusSessionContent(currentSession.value?.sessionCode, {
      role: SessionContentRole.User,
      content: shortcut.name,
      sessionCode: currentSession.value?.sessionCode,
      property: {
        extra: {
          cite: {
            type: 'structured',
            title: shortcut.name,
            data: citeData.map(item => ({
              key: item.__label,
              value: item.__value,
            })),
          },
          command: shortcut.id,
          context: [
            ...formData,
            ...(Array.isArray(props.requestOptions?.context) ? props.requestOptions.context : []),
          ],
        },
      },
    });

    // 检查是否为当前会话中的第一条用户消息
    const shouldAutoRename = isFirstUserMessageInSession();

    chat({
      sessionCode: currentSession.value?.sessionCode,
      ...props.requestOptions,
    });

    // 在发送第一条用户消息后调用renameSessionApi
    if (shouldAutoRename) {
      try {
        await autoRenameCurrentSession();
      } catch (error) {
        console.error('自动命名会话失败:', error);
      }
    }

    emit('send-message', shortcut.name);
  };

  const handleDelete = (index: number) => {
    deleteChat(index, currentSession.value?.sessionCode);
  };

  // 检查是否为第一条用户消息（排除隐藏角色）
  const isFirstUserMessageInSession = () => {
    const visibleMessages = sessionContents.value.filter(
      item => !HIDE_ROLE_LIST.includes(item.role)
    );
    return visibleMessages.length === 1 && visibleMessages[0].role === SessionContentRole.User;
  };

  // 自动重命名当前会话
  const autoRenameCurrentSession = async () => {
    try {
      if (currentSession.value?.sessionCode) {
        const updatedSession = await renameSessionApi(currentSession.value.sessionCode);
        if (updatedSession?.sessionName) {
          // 更新会话存储中的会话名称
          await sessionStore.getSessionList();
        }
      }
    } catch (error) {
      console.error('自动命名会话失败:', error);
    }
  };

  // 处理自动生成命名
  const handleAutoGenerateName = async (sessionCode?: string) => {
    try {
      // 如果没有传入 sessionCode，使用当前会话的 sessionCode
      const targetSessionCode = sessionCode || currentSession.value?.sessionCode;

      if (!targetSessionCode) {
        console.error('无法获取会话代码');
        return;
      }

      console.log('开始自动生成命名，会话代码:', targetSessionCode);
      const updatedSession = await renameSessionApi(targetSessionCode);

      if (updatedSession?.sessionName) {
        // 刷新会话列表以获取最新的会话信息
        await sessionStore.getSessionList();
      }
    } catch (error) {
      console.error('自动命名失败:', error);
    }
  };

  const handleNewChat = async () => {
    stopChat(currentSession.value?.sessionCode);
    inputMessage.value = '';
    setCiteText('');
    setSessionContents([]);
  };

  // ===================================================================
  // 13. 暴露给父组件的方法
  // ===================================================================
  defineExpose({
    stopSessionContentApi,
    sessionContents,
    handleShow,
    handleClose,
    handleStop,
    handleSendMessage,
    handleShortcutClick,
    handleDelete,
    handleRegenerate,
    handleResend,
    updateRequestOptions,
    currentSessionLoading,
    isLoadingSessionContents,
    updateGreetingTextHeight,
    setCurrentSession,
    setCiteText,
    focusInput: () => {
      chatInputBoxRef.value?.focus();
    },
    // 新增会话接口
    addNewSession: (sessionCode?: string) => sessionStore.addNewSession(sessionCode),
    // 更新会话名称接口
    updateSessionName: async (sessionCode: string, newName: string) => {
      return sessionStore.updateSession(sessionCode, { sessionName: newName });
    },
    // 切换到指定会话
    switchToSession: _switchToSession,
    // 获取会话列表
    getSessionList: sessionStore.getSessionList,
    sessionList: sessionStore.sessionList,
    // 是否启用会话管理
    enableChatSession,
  });
</script>

<style lang="scss" scoped>
  @use './styles/mixins.scss';
  @use './styles/markdown.scss';

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
    :deep(.icon-search::before) {
      content: none !important;
    }
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

    .message-line-wrapper {
      width: 100%;
      max-width: 1000px;
      margin: 0 auto;
    }

    &.chat-layout {
      gap: 0;
    }

    .chat-input-wrapper {
      max-width: 1000px;
      margin: 0 auto;
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

    .selection-footer {
      position: absolute;
      bottom: 0;
      left: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      height: 46px;
      padding: 0 16px;
      background: #fafbfd;
      box-shadow: inset 0 1px 0 0 #dcdee5;

      .selection-info {
        font-size: 14px;
        color: #63656e;
      }

      .selection-actions {
        display: flex;
        gap: 8px;

        .cancel-btn {
          color: #63656e;
          background: #ffffff;
          border: 1px solid #c4c6cc;

          &:hover {
            border-color: #979ba5;
          }
        }
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
