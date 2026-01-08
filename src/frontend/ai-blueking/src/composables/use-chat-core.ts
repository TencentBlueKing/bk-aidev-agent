/**
 * useChatCore - 聊天核心逻辑 Composable
 *
 * 整合了会话管理、消息操作、生命周期事件等核心逻辑
 * 解决了各模块之间的循环依赖问题
 */
import { ref, Ref, computed, ComputedRef, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { SessionContentRole } from '@blueking/ai-ui-sdk/enums';
import type { ISessionContent } from '@blueking/ai-ui-sdk/types';
import { useCopyCode } from 'markdown-it-copy-code';
import { HIDE_ROLE_LIST } from '../config';
import { escapeHtml } from '../utils';
import type { IRequestOptions, IShortcut } from '../types';
import type { SessionStore } from '../store/sessionStore';
import type { AddNewSessionOptions } from '../store/types';
import { t } from '../lang';

export interface UseChatCoreOptions {
  /** 标准化的 URL */
  normalizedUrl: ComputedRef<string>;
  /** Session Store 实例 */
  sessionStore: any;
  /** Props */
  props: {
    loadRecentSessionOnMount: boolean;
    initialSessionCode: string;
    autoSwitchToInitialSession: boolean;
    prompts: string[];
    requestOptions?: IRequestOptions;
  };
  /** useChat 返回的方法 - 使用宽松类型以兼容 SDK */
  chatMethods: {
    currentSession: Ref<{ sessionCode?: string } | undefined>;
    sessionContents: Ref<ISessionContent[]>;
    currentSessionLoading: Ref<boolean>;
    plusSessionContent: (...args: any[]) => Promise<any>;
    chat: (...args: any[]) => void;
    stopChat: (...args: any[]) => void;
    reGenerateChat: (...args: any[]) => void;
    reSendChat: (...args: any[]) => void;
    deleteChat: (...args: any[]) => void;
    renameSessionApi: (sessionCode: string) => Promise<{ sessionName?: string } | undefined>;
    stopSessionContentApi: () => void;
    setSessionContents: (contents: ISessionContent[]) => void;
    updateRequestOptions: (options: IRequestOptions) => void;
  };
  /** 消息列表方法 */
  messageListMethods: {
    scrollMainToBottom: () => void;
    scrollToBottomIfNeeded: () => void;
    resetUserScrolling: () => void;
    messageListRef: Ref<any>;
  };
  /** 选择文本方法 */
  selectMethods: {
    citeText: Ref<string>;
    setCiteText: (text: string) => void;
  };
  /** 快捷方式方法 */
  shortcutMethods: {
    handleCancelShortcut: () => void;
  };
  /** 选择模式方法 */
  selectionModeMethods: {
    enterSelectMode: (type: 'transfer' | 'share') => void;
  };
  /** 问候语高度方法 */
  greetingMethods: {
    updateGreetingTextHeight: () => void;
  };
  /** 输入消息 */
  inputMessage: Ref<string>;
  /** 是否显示面板 */
  isShow: Ref<boolean>;
  /** 事件发射器 */
  emit: {
    (
      e: 'session-initialized',
      data: { openingRemark: string; predefinedQuestions: string[] }
    ): void;
    (e: 'init-session-finished'): void;
    (e: 'send-message', message: string): void;
    (e: 'stop'): void;
    (e: 'show'): void;
    (e: 'close'): void;
  };
}

export interface UseChatCoreReturn {
  // 会话状态
  showScrollToBottom: Ref<boolean>;

  // 计算属性
  promptList: ComputedRef<string[]>;
  hasSessionContents: ComputedRef<boolean>;
  greetingText: ComputedRef<string>;
  enableChatSession: ComputedRef<boolean>;

  // 会话管理方法
  initSession: (loadRecentSession?: boolean) => Promise<void>;
  switchToSession: (sessionCode: string) => Promise<boolean>;
  handleNewChat: () => Promise<void>;
  handleAutoGenerateName: (sessionCode?: string) => Promise<void>;

  // 消息操作方法
  handleSendMessage: (message: string) => Promise<void>;
  handleRegenerate: (index: number) => void;
  handleResend: (index: number, data: { message: string }) => void;
  handleStop: () => void;
  handleSubmitShortcut: (data: {
    shortcut: IShortcut;
    formData: Record<string, any>[];
    citeFormData?: Record<string, any>[];
  }) => Promise<void>;
  handleDelete: (index: number) => void;
  handleUpdateSessionContent: (data: {
    messageId: number | undefined;
    updates: Partial<ISessionContent>;
  }) => void;

  // UI 事件处理
  handleShow: (sessionCode?: string, options?: AddNewSessionOptions) => Promise<void>;
  handleClose: () => void;
  handleScrollMainToBottom: () => void;
  handleScrollPositionChange: (isNearBottom: boolean) => void;
}

export function useChatCore(options: UseChatCoreOptions): UseChatCoreReturn {
  const {
    normalizedUrl,
    sessionStore,
    props,
    chatMethods,
    messageListMethods,
    selectMethods,
    shortcutMethods,
    selectionModeMethods,
    greetingMethods,
    inputMessage,
    isShow,
    emit,
  } = options;

  const {
    currentSession,
    sessionContents,
    currentSessionLoading,
    plusSessionContent,
    chat,
    stopChat,
    reGenerateChat,
    reSendChat,
    deleteChat,
    renameSessionApi,
    stopSessionContentApi,
    setSessionContents,
    updateRequestOptions,
  } = chatMethods;

  const { scrollMainToBottom, scrollToBottomIfNeeded, resetUserScrolling, messageListRef } =
    messageListMethods;

  const { citeText, setCiteText } = selectMethods;
  const { handleCancelShortcut } = shortcutMethods;
  const { enterSelectMode } = selectionModeMethods;
  const { updateGreetingTextHeight } = greetingMethods;

  // ===================================================================
  // 状态定义
  // ===================================================================
  const isSessionInitialized = ref(false);
  let initSessionPromise: Promise<void> | null = null;
  const openingRemark = ref('');
  const predefinedQuestions: Ref<string[]> = ref([]);
  const showScrollToBottom = ref(false);

  // ===================================================================
  // 计算属性
  // ===================================================================
  const promptList = computed(() => {
    return [...props.prompts, ...predefinedQuestions.value];
  });

  const hasSessionContents = computed(() => {
    return sessionContents.value.filter(item => !HIDE_ROLE_LIST.includes(item.role)).length > 0;
  });

  const greetingText = computed(() => openingRemark.value || t('输入你的问题，助你高效的完成工作'));

  // 是否启用会话管理
  const enableChatSession = computed(() => {
    return sessionStore.agentInfo.value?.conversationSettings?.enableChatSession ?? true;
  });

  // ===================================================================
  // 会话管理方法
  // ===================================================================
  const initSession = async (loadRecentSession = false): Promise<void> => {
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

  const switchToSession = async (sessionCode: string): Promise<boolean> => {
    if (!sessionCode) return false;

    if (!isSessionInitialized.value) {
      await initSession();
    }

    const targetSession = sessionStore.sessionList.value.find(
      (s: { sessionCode: string }) => s.sessionCode === sessionCode
    );
    if (targetSession) {
      await sessionStore.switchSessionWithContents(targetSession);
      return true;
    }
    return false;
  };

  const sendStopSessionRequest = (): boolean => {
    if (navigator.sendBeacon && normalizedUrl.value) {
      const stopUrl = `${normalizedUrl.value}/session_content/stop/`;
      const success = navigator.sendBeacon(stopUrl, new Blob(['{}'], { type: 'application/json' }));
      return success;
    } else {
      stopSessionContentApi();
      return false;
    }
  };

  const isFirstUserMessageInSession = (): boolean => {
    const visibleMessages = sessionContents.value.filter(
      item => !HIDE_ROLE_LIST.includes(item.role)
    );
    return visibleMessages.length === 1 && visibleMessages[0].role === SessionContentRole.User;
  };

  const autoRenameCurrentSession = async (): Promise<void> => {
    try {
      if (currentSession.value?.sessionCode) {
        const updatedSession = await renameSessionApi(currentSession.value.sessionCode);
        if (updatedSession?.sessionName) {
          await sessionStore.getSessionList();
        }
      }
    } catch (error) {
      console.error('自动命名会话失败:', error);
    }
  };

  const handleAutoGenerateName = async (sessionCode?: string): Promise<void> => {
    try {
      const targetSessionCode = sessionCode || currentSession.value?.sessionCode;

      if (!targetSessionCode) {
        console.error('无法获取会话代码');
        return;
      }

      console.log('开始自动生成命名，会话代码:', targetSessionCode);
      const updatedSession = await renameSessionApi(targetSessionCode);

      if (updatedSession?.sessionName) {
        await sessionStore.getSessionList();
      }
    } catch (error) {
      console.error('自动命名失败:', error);
    }
  };

  const handleNewChat = async (): Promise<void> => {
    stopChat(currentSession.value?.sessionCode);
    inputMessage.value = '';
    setCiteText('');
    setSessionContents([]);
  };

  // ===================================================================
  // 消息操作方法
  // ===================================================================
  const handleSendMessage = async (message: string): Promise<void> => {
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

    const shouldAutoRename = isFirstUserMessageInSession();

    chat({
      sessionCode: currentSession.value?.sessionCode,
      ...props.requestOptions,
    });

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

  const handleRegenerate = (index: number): void => {
    const sessionContent = sessionContents.value[index];
    if (sessionContent) {
      reGenerateChat(sessionContent.sessionCode, sessionContent, index);
    }
  };

  const handleResend = (
    index: number,
    data: {
      message: string;
      shortcut?: any;
      formData?: Record<string, any>[];
    }
  ): void => {
    const { message, shortcut, formData } = data;

    // 如果是 shortcut 类型的消息，先删除原消息，然后重新提交 shortcut
    if (shortcut && formData) {
      // 删除当前消息和后续的 AI 回复
      deleteChat(index, currentSession.value?.sessionCode);

      // 重新提交 shortcut
      handleSubmitShortcut({
        shortcut,
        formData,
        citeFormData: formData, // 这里简化处理，实际应该根据可见字段过滤
      });
      return;
    }

    // 普通消息的处理逻辑
    const sessionContent = sessionContents.value[index];
    if (sessionContent) {
      sessionContent.content = escapeHtml(message);
      reSendChat(sessionContent.sessionCode, sessionContent, index);
    }
  };

  const handleStop = (): void => {
    if (currentSession?.value?.sessionCode) {
      stopChat(currentSession.value.sessionCode);
      emit('stop');
    }
  };

  const handleSubmitShortcut = async (data: {
    shortcut: IShortcut;
    formData: Record<string, any>[];
    citeFormData?: Record<string, any>[];
  }): Promise<void> => {
    const { shortcut, formData, citeFormData } = data;
    handleCancelShortcut();

    if (!isShow.value) {
      isShow.value = true;
      emit('show');
    }

    if (currentSessionLoading.value) {
      handleStop();
    }

    if (!isSessionInitialized.value && normalizedUrl.value) {
      await initSession();
    }

    const citeData = citeFormData || formData;

    // 处理 requestOptions.context 的不同类型情况
    // context 可能是：数组、函数、对象或 undefined
    const requestContext = props.requestOptions?.context;

    // 如果 context 是数组，则合并到 context 数组中；否则使用空数组
    const contextArray = Array.isArray(requestContext) ? requestContext : [];

    // 如果 context 是函数，则执行函数获取返回值；否则直接使用原值（可能是对象或 undefined）
    // 用于展开到 extra 对象中
    const contextExtra = typeof requestContext === 'function' ? requestContext() : requestContext;

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
          // 合并表单数据和请求选项中的数组类型 context
          context: [...formData, ...contextArray],
          // 展开函数返回的对象或直接展开对象类型的 context
          ...contextExtra,
        },
      },
    });

    const shouldAutoRename = isFirstUserMessageInSession();

    chat({
      sessionCode: currentSession.value?.sessionCode,
      ...props.requestOptions,
    });

    if (shouldAutoRename) {
      try {
        await autoRenameCurrentSession();
      } catch (error) {
        console.error('自动命名会话失败:', error);
      }
    }

    emit('send-message', shortcut.name);
  };

  const handleDelete = (index: number): void => {
    deleteChat(index, currentSession.value?.sessionCode);
  };

  const handleUpdateSessionContent = (data: {
    messageId: number | undefined;
    updates: Partial<ISessionContent>;
  }): void => {
    if (data.messageId) {
      const index = sessionContents.value.findIndex(content => content.id === data.messageId);
      if (index !== -1) {
        const updatedContent = { ...sessionContents.value[index], ...data.updates };
        sessionContents.value[index] = updatedContent;
        sessionContents.value = [...sessionContents.value];
      }
    }
  };

  // ===================================================================
  // UI 事件处理
  // ===================================================================
  const handleShow = async (
    sessionCode?: string,
    sessionOptions?: AddNewSessionOptions
  ): Promise<void> => {
    if (sessionOptions?.isTemporary) {
      if (!isSessionInitialized.value) {
        await initSession();
      }

      stopChat(currentSession.value?.sessionCode);
      inputMessage.value = '';
      setCiteText('');
      await sessionStore.addNewSession(sessionCode, sessionOptions);

      isShow.value = true;
      emit('show');
    } else {
      isShow.value = true;
      emit('show');

      if (!isSessionInitialized.value) {
        await initSession();
      }

      if (sessionCode) {
        await switchToSession(sessionCode);
      }
    }

    updateGreetingTextHeight();
  };

  const handleClose = (): void => {
    isShow.value = false;
    emit('close');
  };

  const handleScrollMainToBottom = (): void => {
    scrollMainToBottom();
    showScrollToBottom.value = false;
  };

  const handleScrollPositionChange = (isNearBottom: boolean): void => {
    const messageWrapper = messageListRef.value?.messageWrapper;
    if (!messageWrapper) return;

    const { scrollHeight, clientHeight } = messageWrapper;
    showScrollToBottom.value = !isNearBottom && scrollHeight > clientHeight;
  };

  // ===================================================================
  // Watchers
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

  // ===================================================================
  // 生命周期
  // ===================================================================
  const handleEnterSelectMode = (event: CustomEvent<{ type: 'transfer' | 'share' }>): void => {
    const { type } = event.detail;
    enterSelectMode(type);
  };

  const handleUnload = (): void => {
    sendStopSessionRequest();
  };

  onMounted(async () => {
    window.addEventListener('unload', handleUnload);
    window.addEventListener('enter-select-mode', handleEnterSelectMode as EventListener);

    if (normalizedUrl.value) {
      await initSession(props.loadRecentSessionOnMount);

      if (props.initialSessionCode && props.autoSwitchToInitialSession) {
        await switchToSession(props.initialSessionCode);
      }

      // 触发初始化完成事件，通知外部会话已准备就绪
      emit('init-session-finished');
    }

    useCopyCode();
  });

  onBeforeUnmount(() => {
    window.removeEventListener('enter-select-mode', handleEnterSelectMode as EventListener);
    window.removeEventListener('unload', handleUnload);
  });

  return {
    // 状态
    showScrollToBottom,

    // 计算属性
    promptList,
    hasSessionContents,
    greetingText,
    enableChatSession,

    // 会话管理方法
    initSession,
    switchToSession,
    handleNewChat,
    handleAutoGenerateName,

    // 消息操作方法
    handleSendMessage,
    handleRegenerate,
    handleResend,
    handleStop,
    handleSubmitShortcut,
    handleDelete,
    handleUpdateSessionContent,

    // UI 事件处理
    handleShow,
    handleClose,
    handleScrollMainToBottom,
    handleScrollPositionChange,
  };
}
