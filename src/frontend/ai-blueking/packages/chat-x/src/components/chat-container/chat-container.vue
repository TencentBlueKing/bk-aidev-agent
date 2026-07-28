<template>
  <div
    class="ai-chat-container"
    :data-ai-size="size"
    :style="{ '--resize-main-width': resizeMainWidth, borderTopColor: isCollapse ? 'transparent' : '#eaebf0' }"
  >
    <div
      v-if="chatLoading"
      class="ai-chat-container-loading"
    >
      <MessageLoading />
    </div>
    <ResizeLayout
      v-else
      class="ai-chat-container-resize-layout"
      :class="{
        'ai-is-collapse':
          isCollapse ||
          (displayTabs.length > 0 && !keyword?.length && executionGroups?.length < 1 && !hasFileArtifactTab),
      }"
      v-bind="resizeProps"
      @resizing="handleResizing"
    >
      <template #aside>
        <div
          v-if="
            !isCollapse && displayTabs.length > 0 && (executionGroups?.length || keyword?.length || hasFileArtifactTab)
          "
          ref="fullScreenRef"
          class="ai-full-screen-wrapper"
        >
          <Tab
            :active="selectedTab.name"
            class="ai-chat-container-tab"
            :label-height="40"
            type="unborder-card"
            @change="handleUpdateTabActive"
          >
            <TabPanel
              v-for="tab in displayTabs"
              :key="tab.name"
              class="ai-chat-container-tab-panel"
              :label="
                () =>
                  h(
                    'div',
                    {
                      class: 'ai-execution-summary-label',
                      onVnodeMounted: (node: VNode) => {
                        if (selectedTab.name === tab.name) {
                          node.el?.scrollIntoView({ behavior: 'smooth' });
                        }
                      },
                    },
                    getSideTabRenderComponent?.(h, tab, { removeCustomTab }) ?? [
                      h(getSideTabIcon(tab.name), {
                        class: 'ai-execution-summary-icon',
                      }),
                      withDirectives(
                        h(
                          'span',
                          {
                            class: 'ai-execution-summary-label-text',
                          },
                          tab.label ?? '',
                        ),
                        [[vOverflowTips, { ...commonTippyOptions, text: tab.label ?? '' }]],
                      ),
                      tab.closable !== false && tab.name !== EXECUTION_TAB_NAME
                        ? h(CloseIcon, {
                            class: 'ai-execution-close-icon',
                            onClick: () => {
                              removeCustomTab(tab.name);
                            },
                          })
                        : null,
                    ],
                  )
              "
              :name="tab.name"
            />
            <template #setting>
              <div class="screen-wrapper">
                <ToolBtn
                  class="screen-btn"
                  :tippy-options="{
                    ...commonTippyOptions,
                    appendTo: isFullScreen ? fullScreenRef! : commonTippyOptions?.appendTo,
                    content: isFullScreen ? t('退出全屏') : t('全屏'),
                  }"
                >
                  <FullScreenIcon
                    v-if="!isFullScreen"
                    @click="enter"
                  />
                  <UnFullScreenIcon
                    v-else
                    @click="exit"
                  />
                </ToolBtn>
              </div>
            </template>
          </Tab>
          <template v-if="selectedTab?.name === EXECUTION_TAB_NAME && executionTabVisible !== false">
            <ExecutionSummary
              v-if="!isCollapse"
              :message-groups="executionGroups"
              style="height: calc(100% - 40px)"
              @locate-message-group="handleLocateMessageGroup"
              @update-keyword="handleUpdateKeyword"
            />
          </template>
          <template v-else-if="selectedTab?.name === FILE_ARTIFACT_TAB_NAME">
            <FileArtifactPanel
              :active-id="activeArtifactId"
              :artifacts="sessionArtifacts"
              style="height: calc(100% - 40px)"
              @select="setActiveArtifactId"
            />
          </template>
          <template v-if="selectedTab && selectedTab.name !== FILE_ARTIFACT_TAB_NAME">
            <div
              :key="selectedTab.name"
              class="ai-chat-container-message-slot"
            >
              <component
                :is="sideRenderComponent"
                :key="selectedTab.name"
                v-bind="selectedTab?.data?.props"
              >
                <template #locateButton>
                  <Button
                    class="ai-locate-button"
                    size="small"
                    text
                    theme="primary"
                    @click="handleLocateMessageGroup(selectedTab?.data?.messageUid)"
                  >
                    {{ t('在对话中定位') }}
                  </Button>
                </template>
              </component>
            </div>
          </template>
        </div>
        <div
          v-if="displayTabs.length > 0 && (executionGroups?.length || hasFileArtifactTab)"
          class="collapse-button"
          :class="{ 'is-right': placement === 'right', 'is-collapsed': isCollapse }"
          @click="handleCollapse"
        >
          <CollapsedIcon />
        </div>
      </template>
      <template #main>
        <slot
          v-if="messages?.length"
          name="default"
          v-bind="{
            messages,
            messageStatus,
            messageGroups,
            selectedUserMessages,
            messageToolsStatus,
            isShareMode,
            commonTippyOptions,
            handleAgentAction,
            onAgentFeedback,
            onInterruptResume,
            onUserAction,
            onUserInputConfirm,
            onUserShortcutConfirm,
          }"
        >
          <MessageContainer
            v-if="messages?.length"
            v-model:selected-user-messages="selectedUserMessages"
            :enable-selection="isShareMode"
            :message-groups="messageGroups"
            :message-status="inputStatus"
            :message-tools-status="messageToolsStatus"
            :message-tools-tippy-options="commonTippyOptions"
            :messages="messages"
            :on-agent-action="handleAgentAction"
            :on-agent-feedback="onAgentFeedback"
            :on-interrupt-resume="onInterruptResume"
            :on-user-action="onUserAction"
            :on-user-input-confirm="onUserInputConfirm"
            :on-user-shortcut-confirm="onUserShortcutConfirm"
            :render-mode="renderMode"
            @stop-streaming="emits('stopStreaming')"
          >
            <template #group="{ group }">
              <slot
                name="group"
                v-bind="{ group }"
              />
            </template>
            <template #default="{ message, messageToolsStatus, onInterruptResume: slotOnInterruptResume }">
              <slot
                name="message"
                v-bind="{ message, messageToolsStatus, onInterruptResume: slotOnInterruptResume }"
              />
            </template>
          </MessageContainer>
        </slot>
        <div
          v-else
          class="ai-welcome-content"
        >
          <slot
            name="welcome"
            v-bind="{ openingRemark, welcomeTitle }"
          >
            <AIBluekingBannerIcon />
            <h2 class="ai-welcome-title">{{ welcomeTitle ?? t('你好，我是小鲸') }}</h2>
            <div
              v-if="openingRemark"
              class="ai-welcome-remark"
            >
              <ContentRender :content="openingRemark" />
            </div>
          </slot>
        </div>
        <template v-if="renderMode !== RenderMode.Share">
          <template v-if="isShareMode">
            <SelectionFooter
              :is-all-selected="isAllSelected"
              :loading="false"
              :selected-count="selectedUserMessages.length"
              @cancel="onCancelShare"
              @confirm="handleConfirmShare"
              @toggle-all="onToggleShareAll"
            />
          </template>
          <ShortcutRender
            v-else-if="selectedShortcut?.components?.length"
            v-bind="selectedShortcut"
            :class="{ 'is-welcome-overlay': !messages?.length }"
            @close="handleShortcutRenderClose"
            @submit="handleShortcutRenderSubmit"
          />
          <template v-else>
            <ChatInput
              v-model:cite="cite"
              :message-status="inputStatus"
              :model-value="modelValue"
              :on-send-message="handleSendMessage"
              :on-stop-sending="onStopSending"
              :on-upload="onUpload"
              :placeholder="placeholder"
              :prompts="prompts"
              :resources="resources"
              :send-disabled-tip="pendingApprovalTipText"
              :shortcut-id="selectedShortcut?.id"
              :shortcuts="shortcuts"
              :skills="skills"
              :support-upload="supportUpload"
              :tippy-options="commonTippyOptions"
              @delete-shortcut="handleCloseShortcut"
              @select-shortcut="handleSelectShortcut"
              @update:model-value="handleUpdateModelValue"
            >
              <template #interrupt>
                <UserQuestionCard
                  v-if="activeUserQuestionInterrupt"
                  :interrupt="activeUserQuestionInterrupt"
                  :on-resume="onInterruptResume"
                >
                  <template #question="{ question, qIndex, answer, setAnswer, confirm }">
                    <slot
                      name="interruptQuestion"
                      v-bind="{ question, qIndex, answer, setAnswer, confirm }"
                    />
                  </template>
                </UserQuestionCard>
                <InputInfoAlert
                  v-if="pendingApprovalTipText"
                  :content="pendingApprovalTipText"
                />
              </template>
            </ChatInput>
          </template>
        </template>
      </template>
    </ResizeLayout>
  </div>
</template>
<script setup lang="ts">
  import {
    type VNode,
    computed,
    ref as deepRef,
    h,
    nextTick,
    onUnmounted,
    shallowRef,
    useTemplateRef,
    watch,
    withDirectives,
  } from 'vue';

  import { Button, ResizeLayout, Tab } from 'bkui-vue';

  import { type Message, type UserMessage, MessageStatus } from '../../ag-ui/types';
  import { LOADING_MESSAGE_ID, RenderMode } from '../../common';
  import { type MessageGroup, useMessageGroup } from '../../composables';
  import { FILE_ARTIFACT_TAB_NAME, useArtifactPreviewProvider } from '../../composables/use-artifact-preview';
  import { useCommonTippyProvider, useRenderModeProvider } from '../../composables/use-common';
  import { EXECUTION_TAB_NAME, useCustomTabProvider } from '../../composables/use-custom-tab';
  import { useFullScreen } from '../../composables/use-full-screen';
  import { type AiSizeMode, useGlobalConfig } from '../../composables/use-global-config';
  import { OverflowTips as vOverflowTips } from '../../directives';
  import { FullScreenIcon, UnFullScreenIcon } from '../../icons';
  import { CloseIcon, CollapsedIcon, ExecutionIcon, NodeTabIcon } from '../../icons';
  import { AIBluekingBannerIcon, ArtifactTabIcon } from '../../icons';
  import { t } from '../../lang/lang';
  import ToolBtn from '../ai-buttons/tool-btn/tool-btn.vue';
  import ShortcutRender from '../ai-shortcut/shortcut-render/shortcut-render.vue';
  import ContentRender from '../chat-content/content-render/content-render.vue';
  import ChatInput, { type ChatInputEmits, type ChatInputProps } from '../chat-input/chat-input.vue';
  import InputInfoAlert from '../chat-input/input-info-alert.vue';
  import FileArtifactPanel from '../chat-message/assistant-message/message-artifacts/file-artifact-panel.vue';
  import { buildSkipResumePayload, UserQuestionCard } from '../chat-message/interrupt-message/user-question';
  import MessageContainer, {
    type MessageContainerEmits,
    type MessageContainerProps,
  } from '../chat-message/message-container/message-container.vue';
  import ExecutionSummary from '../execution-summary/execution-summary.vue';
  import MessageLoading from '../message-loading/message-loading.vue';
  import SelectionFooter from '../selection-footer/selection-footer.vue';

  import type { OnArtifactClick } from '../../ag-ui/types/file';
  import type {
    AITippyProps,
    CustomBkFlowTabData,
    CustomTab,
    IAiSlashMenuItem,
    IToolBtn,
    Shortcut,
    TagSchema,
  } from '../../types';
  import type { UserQuestionCardSlots } from '../chat-message/interrupt-message/user-question/user-question-card.vue';
  import type { Token } from 'markdown-it/index.js';
  export type ChatContainerProps = {
    chatLoading?: boolean;
    commonTippyOptions?: AITippyProps;
    // 执行情况 Tab 是否展示，缺省 true；为 false 时从 Tab 栏隐藏，选中态自动切到首个可见 Tab
    executionTabVisible?: boolean;
    // 用于获取侧边栏组件的渲染
    getSideRenderComponent?: (createElement: typeof h, props?: Record<string, unknown>) => undefined | VNode;
    // 用于获取侧边栏 tab 的渲染
    getSideTabRenderComponent?: (
      createElement: typeof h,
      tab: CustomTab<Record<string, unknown>>,
      events: { removeCustomTab: typeof removeCustomTab },
    ) => undefined | VNode;
    /** 点击文件产物时异步获取 download_url / preview_url；未传则隐藏下载、预览无数据 */
    onArtifactClick?: OnArtifactClick;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onCustomTabChange?: (tab: CustomTab<CustomBkFlowTabData>) => Promise<any>;
    openingRemark?: string;
    placement?: 'left' | 'right';
    resizeProps?: {
      disabled?: boolean;
      initialDivide?: number | string;
      max?: number;
      min?: number;
    };
    /** 字号主题档位：small(默认 12px) / normal(14px) */
    size?: AiSizeMode;
    welcomeTitle?: string;
  };
  const TabPanel = Tab.TabPanel;
  defineSlots<{
    codeHeader: (props: { language: string; token: Token[] }) => null | undefined | VNode;
    default: (props: {
      commonTippyOptions?: AITippyProps;
      handleAgentAction: typeof handleAgentAction;
      isShareMode: boolean;
      messageGroups: MessageContainerProps['messageGroups'];
      messages: Message[];
      messageStatus: MessageContainerProps['messageStatus'];
      messageToolsStatus: MessageContainerProps['messageToolsStatus'];
      onAgentFeedback?: MessageContainerProps['onAgentFeedback'];
      onInterruptResume?: MessageContainerProps['onInterruptResume'];
      onUserAction?: MessageContainerProps['onUserAction'];
      onUserInputConfirm?: (message: Message, content: UserMessage['content'], docSchema: TagSchema) => Promise<void>;
      onUserShortcutConfirm?: (message: Message, formModel: Record<string, unknown>) => Promise<void>;
      selectedUserMessages: Message[];
    }) => null | undefined | VNode;
    group: (props: { group: MessageGroup }) => unknown;
    interruptQuestion: UserQuestionCardSlots['question'];
    message: (props: {
      message: Message;
      messageToolsStatus: MessageContainerProps['messageToolsStatus'];
      onInterruptResume?: MessageContainerProps['onInterruptResume'];
    }) => null | undefined | VNode;
    welcome: (props: {
      openingRemark: ChatContainerProps['openingRemark'];
      welcomeTitle: ChatContainerProps['welcomeTitle'];
    }) => null | undefined | VNode;
  }>();
  const props = withDefaults(
    defineProps<
      ChatContainerProps &
        ChatInputProps &
        Omit<MessageContainerProps, 'enableSelection' | 'messageGroups' | 'messageToolsTippyOptions'>
    >(),
    {
      placement: 'left',
      executionTabVisible: true,
      size: 'small',
    },
  );
  const renderMode = defineModel<RenderMode>('renderMode', {
    required: false,
    default: RenderMode.Chat,
  });

  const fullScreenRef = useTemplateRef<HTMLElement>('fullScreenRef');
  const { isFullScreen, enter, exit } = useFullScreen(fullScreenRef);

  useRenderModeProvider({ renderMode });

  const resizeProps = computed(() => ({
    collapsible: false,
    immediate: true,
    min: 400,
    ...props.resizeProps,
    placement: props.placement,
  }));

  const sideRenderComponent = computed(() => {
    return props.getSideRenderComponent?.(h, selectedTab.value.data?.props ?? {}) ?? selectedTab.value.data?.component;
  });
  useGlobalConfig({
    size: computed(() => props.size ?? 'small'),
    supportUpload: computed(() => props.supportUpload ?? false),
  });
  // 浮层（tippy / Teleport 内容）会挂载到 body，脱离 .ai-chat-container 的 data-ai-size 作用域。
  // 将当前 size 同步到 body，使这些浮层也能继承字号主题变量；容器内内容仍由更近的容器属性控制。
  watch(
    () => props.size ?? 'small',
    size => {
      if (typeof document !== 'undefined') {
        document.body.dataset.aiSize = size;
      }
    },
    { immediate: true },
  );
  const selectedShortcut = defineModel<null | Shortcut>('selectedShortcut', {
    required: false,
  });
  const cite = defineModel<string>('cite', {
    required: false,
    default: '',
  });

  const emits = defineEmits<
    ChatInputEmits &
      MessageContainerEmits & {
        (e: 'shortcutClose'): void;
        (e: 'shortcutSubmit', formModel: Record<string, unknown>): void;
        (e: 'confirmShare', messages: Message[]): void;
        (e: 'collapseChange', isCollapse: boolean, resizeAsideWidth: number): void;
      }
  >();

  useCommonTippyProvider({ tippyOptions: computed(() => props.commonTippyOptions ?? {}) });

  const { displayTabs, tabs, selectedTab, isCollapse, addCustomTab, removeCustomTab, selectCustomTab, resetCustomTab } =
    useCustomTabProvider<CustomBkFlowTabData>({
      executionTabVisible: () => props.executionTabVisible,
      onTabChange: async tab => {
        // 文件产物 Tab 由 FileArtifactPanel 自行通过 onArtifactClick 异步取链，无需走自定义 Tab 拉取
        if (tab.name === FILE_ARTIFACT_TAB_NAME) {
          return;
        }
        const tabProps = selectedTab.value.data?.props || {
          loading: true,
          data: {},
        };
        selectedTab.value.data = {
          ...selectedTab.value.data,
          props: tabProps,
        };
        const data = await props.onCustomTabChange?.(tab);
        selectedTab.value.data = {
          ...selectedTab.value.data,
          props: {
            ...tabProps,
            loading: false,
            data,
          },
        };
      },
    });

  const keyword = shallowRef('');
  const selectedUserMessages = deepRef<Message[]>([]);
  const resolveInitialAsideWidth = () => {
    const divide = props.resizeProps?.initialDivide;
    return typeof divide === 'number' ? divide : 400;
  };
  const resizeAsideWidth = shallowRef<number>(resolveInitialAsideWidth());
  const resizeMainWidth = computed(() => {
    return `calc(100% - ${resizeAsideWidth.value}px)`;
  });

  const {
    messageGroups,
    executionGroups,
    sessionArtifacts,
    isShareMode,
    isAllSelected,
    onToggleShareAll,
    onCancelShare,
    onConfirmShare,
    pendingApprovalTipText,
    activeUserQuestionInterrupt,
  } = useMessageGroup({
    keyword,
    messages: computed(() => props.messages),
    renderMode: computed(() => renderMode.value),
    selectedUserMessages,
  });

  /** 侧栏是否存在「文件产物」Tab，用于放开侧栏对 executionGroups 的显隐强耦合 */
  const hasFileArtifactTab = computed(() => tabs.value.some(tab => tab.name === FILE_ARTIFACT_TAB_NAME));

  // 文件卡片点击 → 命中文件并弹出/切换到固定的「文件产物」侧栏 Tab（排在执行情况之前，不可关闭）
  const { activeArtifactId, setActiveArtifactId } = useArtifactPreviewProvider({
    getOnArtifactClick: () => props.onArtifactClick,
    onOpen: () => {
      addCustomTab({
        closable: false,
        label: t('文件产物'),
        name: FILE_ARTIFACT_TAB_NAME,
        order: -1,
      });
    },
  });

  // 会话切换 / 无文件产物时清理：移除 Tab 并重置命中态，避免残留
  watch(sessionArtifacts, list => {
    if (!list.length) {
      removeCustomTab(FILE_ARTIFACT_TAB_NAME);
      setActiveArtifactId('');
    }
  });

  watch(isCollapse, newVal => {
    if (newVal) {
      keyword.value = '';
      resizeAsideWidth.value = 0;
    }
    emits('collapseChange', newVal, resizeAsideWidth.value);
  });
  watch(
    () => executionGroups.value,
    newVal => {
      // 文件产物 Tab 存在时不因执行组为空而重置，避免误清文件预览侧栏
      if (!newVal.length && !keyword.value && !hasFileArtifactTab.value) {
        resetCustomTab();
      }
    },
    {
      immediate: true,
      deep: false,
    },
  );
  const inputStatus = computed(() => {
    // StopLoading 优先级最高，确保停止接口调用期间 UI 立即响应
    if (props.messageStatus === MessageStatus.StopLoading) {
      return MessageStatus.StopLoading;
    }
    if (messageGroups.value?.some(group => group.messages.some(message => message.id === LOADING_MESSAGE_ID))) {
      return MessageStatus.Fetching;
    }
    return props.messageStatus;
  });
  const handleShortcutRenderClose = () => {
    selectedShortcut.value = null;
    emits('shortcutClose');
  };
  const handleShortcutRenderSubmit = (formModel: Record<string, unknown>) => {
    emits('shortcutSubmit', formModel);
  };
  const handleCloseShortcut = () => {
    emits('deleteShortcut');
  };
  const handleSelectShortcut = (shortcut: Shortcut) => {
    emits('selectShortcut', shortcut);
  };
  const handleUpdateModelValue = (value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]) => {
    emits('update:modelValue', value, selectedResourceList);
  };

  /**
   * 发送拦截：存在激活的 UserQuestion 中断且为自由文本时，按 resume 回传而非发送新消息。
   * @param content - 输入内容（字符串文本或文件数组）
   * @param docSchema - 富文本结构
   */
  const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
    const activeQuestion = activeUserQuestionInterrupt.value;
    return props.onSendMessage?.(
      content,
      docSchema,
      activeQuestion
        ? {
            payload: buildSkipResumePayload(activeQuestion), // 跳过中断时回传空答案
            interrupt: activeQuestion, // 跳过中断时回传中断对象
          }
        : undefined,
    );
  };

  const handleCollapse = () => {
    isCollapse.value = !isCollapse.value;
  };
  /**
   * 定位消息组
   */
  const handleLocateMessageGroup = (uid?: string) => {
    if (!uid) {
      return;
    }
    const dom = document.getElementById(uid);
    if (!dom) {
      const group = messageGroups.value.find(group => group.messages.some(message => message.uid === uid));
      if (group) {
        document.getElementById(group.uid)?.scrollIntoView({ behavior: 'smooth' });
      }
      return;
    }
    dom.scrollIntoView({ behavior: 'smooth' });
  };
  // 侧栏 Tab 默认图标：执行情况用 ExecutionIcon，文件产物用 ArtifactTabIcon，其余用 NodeTabIcon
  const getSideTabIcon = (name: string) => {
    if (name === EXECUTION_TAB_NAME) {
      return ExecutionIcon;
    }
    if (name === FILE_ARTIFACT_TAB_NAME) {
      return ArtifactTabIcon;
    }
    return NodeTabIcon;
  };
  const handleUpdateTabActive = (name: string) => {
    selectCustomTab(tabs.value.find(tab => tab.name === name)!);
  };
  const handleUpdateKeyword = (v: string) => {
    keyword.value = v;
  };

  /**
   * 点击Agent 消息工具操作
   * @param tool - 工具
   * @param messages - 消息
   */
  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    // 点击分享按钮，切换到分享模式
    if (tool.id === 'share') {
      isShareMode.value = true;
      return;
    }
    return props.onAgentAction?.(tool, messages);
  };
  /**
   * 点击确认分享
   */
  const handleConfirmShare = () => {
    emits('confirmShare', onConfirmShare());
    nextTick(() => {
      isShareMode.value = false;
      selectedUserMessages.value = [];
    });
  };

  const handleResizing = (w: number) => {
    resizeAsideWidth.value = w;
  };
  onUnmounted(() => {
    resetCustomTab();
    // 卸载时清理 body 上的字号主题标记，避免残留影响其他场景
    if (typeof document !== 'undefined') {
      delete document.body.dataset.aiSize;
    }
  });

  defineExpose({
    selectedTab,
    addCustomTab,
    removeCustomTab,
    selectCustomTab,
    enterShareMode: () => {
      isShareMode.value = true;
    },
    exitShareMode: () => {
      onCancelShare();
    },
  });
</script>
<style lang="scss">
  .ai-chat-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    font-size: var(--ai-font-size, 12px);
    border: none;
    border-top: 1px solid transparent;

    &-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
    }

    .collapse-button {
      position: absolute;
      top: 50%;
      left: -16px;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 16px;
      min-height: 64px;
      padding: 8px 2px;
      font-size: 14px;
      color: #fff;
      background: #dcdee5;
      border-radius: 4px 0 0 4px;

      // box-shadow: 2px 0 4px 0 #0000001a;
      transform: translateY(-50%);

      .ai-common-icon {
        width: 14px;
        height: 14px;
        margin-bottom: 2px;
        font-size: 14px;
        transition: transform 0.2s ease-in-out;
      }

      &.is-collapsed {
        .ai-common-icon {
          transform: rotate(180deg);
        }
      }

      &.is-right {
        right: -17px;
        left: auto;
        border-radius: 0 4px 4px 0;

        .ai-common-icon {
          transform: rotate(180deg) !important;
        }

        &.is-collapsed {
          .ai-common-icon {
            transform: rotate(0deg) !important;
          }
        }
      }

      &:hover {
        color: #fff;
        cursor: pointer;
        background: #3a84ff;
        box-shadow: 2px 0 4px 0 #0000001a;
      }
    }

    &-tab {
      padding: 0 16px;

      .bk-tab-header-nav {
        &::-webkit-scrollbar {
          display: inline;
          width: unset;
          height: 0;
        }
      }

      .bk-tab-content {
        display: none;
      }

      .bk-tab-header-item {
        padding: 0 16px;
        font-size: 14px;
      }

      .ai-execution-summary-label {
        display: flex;
        gap: 4px;
        align-items: center;
        justify-content: center;

        &-text {
          max-width: 100px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .ai-execution-close-icon {
        margin-left: 4px;
        cursor: pointer;

        &:hover {
          opacity: 0.8;
        }
      }

      .screen-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;

        // padding-left: 8px;
        color: #979ba5;

        &::before {
          position: absolute;
          top: 14px;
          left: -8px;
          display: block;
          width: 1px;
          height: 12px;
          content: '';
          background: #eaebf0;
        }

        .screen-btn {
          font-size: var(--ai-font-size, 12px);
        }

        .ai-common-icon {
          /* stylelint-disable-next-line no-descending-specificity */
          &:hover {
            color: #3a84ff;
            cursor: pointer;
          }
        }
      }
    }

    &-resize-layout {
      width: 100%;
      height: 100%;
      border: none !important;

      > main,
      > aside {
        display: flex !important;
        flex-direction: column !important;
        height: 100%;
      }

      > aside > div:first-child {
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
      }

      > main {
        position: relative;
        width: var(--resize-main-width);
        padding: 8px;

        // overflow: visible;

        // 空态下快捷指令保持在输入框位置（贴底），内容过高时向上生长并遮挡欢迎内容，而非被压缩
        .ai-shortcut-render.is-welcome-overlay {
          position: absolute;
          right: 8px;
          bottom: 8px;
          left: 8px;
          z-index: 1;

          // 覆盖自身的 width: 100%，由 left/right 决定宽度，避免超出
          width: auto;
          max-height: calc(100% - 16px);

          // 高度随内容自然撑开，超过可视高度时由外层 max-height 兜底滚动
          .ai-shortcut-render-content {
            max-height: none;
          }
        }
      }

      &.ai-is-collapse {
        > aside {
          flex: 0 0 0 !important;
          width: 0;
          padding: 0;
          border: none;

          &::after {
            display: none;
          }

          > i {
            display: none;
          }
        }
      }

      .ai-full-screen-wrapper {
        width: 100%;
        height: 100%;
        background-color: white;
      }
    }

    &-message-slot {
      width: 100%;
      height: calc(100% - 40px);

      .ai-locate-button {
        margin-left: auto;
        font-size: var(--ai-font-size, 12px);
        font-weight: normal;
      }
    }

    .ai-welcome-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      max-width: 1000px;
      min-height: 0;
      padding: 16px;
      margin: 0 auto;
      text-align: center;

      .ai-blueking-banner-icon {
        flex-shrink: 0;
        width: 309px;
        height: auto;
      }

      .ai-welcome-title {
        flex-shrink: 0;
        margin: 0 0 16px;
        font-size: 20px;
        font-weight: 600;
        line-height: 28px;
        color: #313238;
      }

      .ai-welcome-remark {
        flex: 0 1 auto;
        width: 100%;
        min-height: 0;
        margin-bottom: 24px;
        overflow-y: auto;
        scrollbar-color: #dcdee5 transparent;
        scrollbar-width: thin;

        &::-webkit-scrollbar {
          width: 4px;
        }

        &::-webkit-scrollbar-track {
          background: transparent;
        }

        &::-webkit-scrollbar-thumb {
          background: #dcdee5;
          border-radius: 2px;
        }

        &::-webkit-scrollbar-thumb:hover {
          background: #c4c6cc;
        }

        .ai-markdown-content {
          height: auto;
        }
      }
    }
  }
</style>
