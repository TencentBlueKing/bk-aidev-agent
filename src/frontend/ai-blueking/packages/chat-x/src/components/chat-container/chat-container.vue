<template>
  <div
    class="ai-chat-container"
    :data-ai-size="size"
    :style="{
      '--resize-main-width': resizeMainWidth,
      '--resize-aside-width': resizeAsideWidthVar,
    }"
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
        'ai-is-collapse': isCollapse || displayTabs.length === 0,
        'ai-is-welcome': !messages?.length,
        'is-resizing': isResizing,
      }"
      v-bind="resizeProps"
      @after-resize="handleAfterResize"
      @resizing="handleResizing"
    >
      <template #aside>
        <Transition name="ai-aside-content">
          <div
            v-if="!isCollapse && displayTabs.length > 0"
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
        </Transition>
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
            :message-tools="messageTools"
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
            :update-tools="updateTools"
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
              @cancel="handleCancelShare"
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
              v-model:selected-model="selectedModel"
              :message-status="inputStatus"
              :model-value="modelValue"
              :models="models"
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
              @model-change="emits('modelChange', $event)"
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
  import { CloseIcon, ExecutionIcon, NodeTabIcon } from '../../icons';
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
    /**
     * 侧栏折叠态，受控：传入后一律以外部值为准，
     * 内部展开动作只发 `update:asideCollapsed`，外部不改则不展开；不传时由组件内部自持。
     */
    asideCollapsed?: boolean;
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
    resizeProps?: {
      disabled?: boolean;
      initialDivide?: number | string;
      max?: number;
      min?: number;
    };
    /** 字号主题档位：small(默认 12px) / normal(14px) */
    size?: AiSizeMode;
    /** 消息时间展示所用的 IANA 时区名（如 Asia/Shanghai）；未配置时按浏览器时区展示 */
    timezone?: string;
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
      // 显式给 undefined，避免 Boolean 类型 prop 在未传时被 Vue 转成 false，从而无法区分「外部受控」与「内部自持」
      asideCollapsed: undefined,
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
    // 侧栏固定从右侧展开，不再支持左侧
    placement: 'right' as const,
  }));

  const sideRenderComponent = computed(() => {
    return props.getSideRenderComponent?.(h, selectedTab.value.data?.props ?? {}) ?? selectedTab.value.data?.component;
  });
  useGlobalConfig({
    size: computed(() => props.size ?? 'small'),
    supportUpload: computed(() => props.supportUpload ?? false),
    timezone: computed(() => props.timezone),
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
  // 当前选中的模型（值为 llm_name），透传给 ChatInput 的模型选择器（v-model:selectedModel）
  const selectedModel = defineModel<string>('selectedModel', {
    required: false,
  });

  const emits = defineEmits<
    ChatInputEmits &
      MessageContainerEmits & {
        (e: 'shortcutClose'): void;
        (e: 'shortcutSubmit', formModel: Record<string, unknown>): void;
        (e: 'confirmShare', messages: Message[], source?: IToolBtn): void;
        (e: 'collapseChange', isCollapse: boolean, resizeAsideWidth: number): void;
        (e: 'update:asideCollapsed', collapsed: boolean): void;
      }
  >();

  /** 外部未绑定 asideCollapsed 时的兜底状态 */
  const localAsideCollapsed = shallowRef(true);
  /**
   * 侧栏折叠态：严格受控。外部传入时读写都以外部为准，
   * 内部展开动作（文件卡片预览、addCustomTab）只发出 update 事件，外部不改则不展开。
   */
  const asideCollapsed = computed<boolean>({
    get: () => props.asideCollapsed ?? localAsideCollapsed.value,
    set: (collapsed: boolean) => {
      if (props.asideCollapsed === undefined) {
        localAsideCollapsed.value = collapsed;
      }
      emits('update:asideCollapsed', collapsed);
    },
  });

  // 全屏时 tippy 默认挂 body 会跑出全屏层，统一把 appendTo 切到全屏容器再注入给子组件
  const commonTippyOptions = computed<AITippyProps>(() => ({
    ...props.commonTippyOptions,
    appendTo: isFullScreen.value && fullScreenRef.value ? fullScreenRef.value : props.commonTippyOptions?.appendTo,
  }));
  useCommonTippyProvider({ tippyOptions: commonTippyOptions });

  const {
    displayTabs,
    tabs,
    selectedTab,
    isCollapse,
    addCustomTab,
    ensureCustomTab,
    removeCustomTab,
    selectCustomTab,
    resetCustomTab,
  } = useCustomTabProvider<CustomBkFlowTabData>({
    collapsed: asideCollapsed,
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

  /** 文件产物 Tab 元信息：排在执行情况之前，不可关闭 */
  const FILE_ARTIFACT_TAB = {
    closable: false,
    label: t('文件产物'),
    name: FILE_ARTIFACT_TAB_NAME,
    order: -1,
  };
  // 常驻挂载：不随产物有无增删，无产物时由面板展示空态
  ensureCustomTab(FILE_ARTIFACT_TAB);

  const keyword = shallowRef('');
  const selectedUserMessages = deepRef<Message[]>([]);
  // 记录触发多选态的按钮（share 或标记 triggerSelection 的自定义按钮），确认时作为来源参数回传
  const selectionSource = shallowRef<IToolBtn>();
  const resolveInitialAsideWidth = () => {
    const divide = props.resizeProps?.initialDivide;
    return typeof divide === 'number' ? divide : 400;
  };
  const resizeAsideWidth = shallowRef<number>(resolveInitialAsideWidth());
  /** 展开态宽度：折叠时 resizeAsideWidth 归零，动画与再次展开都要用它还原 */
  const lastExpandedAsideWidth = shallowRef<number>(resolveInitialAsideWidth());
  const isResizing = shallowRef(false);
  const resizeMainWidth = computed(() => {
    return `calc(100% - ${resizeAsideWidth.value}px)`;
  });
  const resizeAsideWidthVar = computed(() => `${lastExpandedAsideWidth.value}px`);

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

  // 文件卡片点击 → 命中文件并展开侧栏、切到「文件产物」Tab
  const { activeArtifactId, setActiveArtifactId } = useArtifactPreviewProvider({
    getOnArtifactClick: () => props.onArtifactClick,
    onOpen: () => {
      addCustomTab(FILE_ARTIFACT_TAB);
    },
  });

  /** 产物列表变化时维护命中态：无产物清空命中，命中项失效时回落到第一个 */
  watch(
    sessionArtifacts,
    list => {
      if (!list.length) {
        setActiveArtifactId('');
        return;
      }
      if (!list.some(item => item.outputId === activeArtifactId.value)) {
        setActiveArtifactId(list[0].outputId);
      }
    },
    { immediate: true },
  );

  watch(isCollapse, newVal => {
    if (newVal) {
      keyword.value = '';
      resizeAsideWidth.value = 0;
    } else {
      // 展开时还原宽度，避免折叠时置 0 后主区宽度停留在 100%
      resizeAsideWidth.value = lastExpandedAsideWidth.value;
    }
    emits('collapseChange', newVal, resizeAsideWidth.value);
  });
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
    // 点击分享，或业务标记了 triggerSelection 的自定义按钮（如保存），进入多选态；确认复用 confirmShare
    if (tool.id === 'share' || tool.triggerSelection) {
      selectionSource.value = tool;
      isShareMode.value = true;
      return;
    }
    return props.onAgentAction?.(tool, messages);
  };
  /**
   * 点击确认分享
   */
  const handleConfirmShare = () => {
    // 第二个参数为来源按钮对象，业务据此区分 share / save 等不同确认场景
    emits('confirmShare', onConfirmShare(), selectionSource.value);
    nextTick(() => {
      isShareMode.value = false;
      selectedUserMessages.value = [];
      selectionSource.value = undefined;
    });
  };
  // 取消多选态时同步清理来源标记
  const handleCancelShare = () => {
    onCancelShare();
    selectionSource.value = undefined;
  };

  // 拖拽期间关闭侧栏宽度过渡，避免动画与鼠标不跟手
  const handleResizing = (w: number) => {
    isResizing.value = true;
    resizeAsideWidth.value = w;
    lastExpandedAsideWidth.value = w;
  };
  const handleAfterResize = () => {
    isResizing.value = false;
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
      handleCancelShare();
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

    &-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
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

        .ai-execution-summary-icon {
          flex-shrink: 0;
          width: 16px;
          height: 16px;
          font-size: 16px;
        }

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

      > aside {
        // min-width: auto 会以内容最小宽度兜底，收起动画期间内容尚未卸载，需显式放开才能收到 0
        min-width: 0;
        transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      }

      // 拖拽调宽时关闭过渡，保证跟手
      &.is-resizing > aside {
        transition: none;
      }

      > aside > div:first-child {
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
      }

      > main {
        position: relative;
        width: var(--resize-main-width);
        box-sizing: border-box;

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

      // 欢迎态顶距只加在主栏，避免整层 chatbot padding 把侧栏一起顶下去导致错位
      &.ai-is-welcome > main {
        padding-top: 15vh;
      }

      &.ai-is-collapse {
        > aside {
          // bkui 把侧栏宽度写在行内，需 !important 覆盖，宽度才能从实际值过渡到 0
          width: 0 !important;
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

      // 展开时不淡入：内容一开始就可见，由 aside width + overflow 裁切显现，
      // 避免浮窗先加宽、内容再弹出两段动画。收起仍淡出。
      .ai-aside-content-enter-active,
      .ai-aside-content-leave-active {
        width: var(--resize-aside-width);
      }

      .ai-aside-content-leave-active {
        transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      }

      .ai-aside-content-leave-to {
        opacity: 0;
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
