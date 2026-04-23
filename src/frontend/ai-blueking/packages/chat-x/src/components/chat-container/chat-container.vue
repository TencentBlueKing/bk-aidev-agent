<template>
  <div
    class="ai-chat-container"
    :style="{ '--resize-main-width': resizeMainWidth }"
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
      :class="{ 'ai-is-collapse': isCollapse || executionGroups?.length < 1 || renderMode === RenderMode.Share }"
      v-bind="resizeProps"
      @resizing="handleResizing"
    >
      <template #aside>
        <template v-if="!isCollapse && executionGroups?.length && renderMode !== RenderMode.Share">
          <Tab
            :active="selectedTab.name"
            class="ai-chat-container-tab"
            :label-height="40"
            type="unborder-card"
            @change="handleUpdateTabActive"
          >
            <TabPanel
              v-for="tab in tabs"
              :key="tab.name"
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
                    [
                      h(tab.name === EXECUTION_TAB_NAME ? ExecutionIcon : NodeTabIcon, {
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
                      tab.name !== EXECUTION_TAB_NAME
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
          </Tab>
          <template v-if="selectedTab?.name === EXECUTION_TAB_NAME">
            <ExecutionSummary
              v-if="!isCollapse"
              :message-groups="executionGroups"
              style="height: calc(100% - 40px)"
              @locate-message-group="handleLocateMessageGroup"
              @update-keyword="handleUpdateKeyword"
            />
          </template>
          <template v-if="selectedTab">
            <div class="ai-chat-container-message-slot">
              <component
                :is="selectedTab?.data?.component"
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
        </template>
        <div
          v-if="executionGroups?.length && renderMode !== RenderMode.Share"
          class="collapse-button"
          :class="{ 'is-right': placement === 'right' }"
          @click="handleCollapse"
        >
          <ExecutionIcon />
          {{ t('执行情况') }}
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
            v-bind="{ openingRemark }"
          >
            <AIBluekingBannerIcon />
            <h2 class="ai-welcome-title">{{ t('你好，我是小鲸') }}</h2>
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
            @close="handleShortcutRenderClose"
            @submit="handleShortcutRenderSubmit"
          />
          <template v-else>
            <ChatInput
              v-model:cite="cite"
              :message-status="inputStatus"
              :model-value="modelValue"
              :on-send-message="onSendMessage"
              :on-stop-sending="onStopSending"
              :on-upload="onUpload"
              :placeholder="placeholder"
              :prompts="prompts"
              :resources="resources"
              :shortcut-id="selectedShortcut?.id"
              :shortcuts="shortcuts"
              :support-upload="supportUpload"
              :tippy-options="commonTippyOptions"
              @delete-shortcut="handleCloseShortcut"
              @select-shortcut="handleSelectShortcut"
              @update:model-value="handleUpdateModelValue"
            />
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
    watch,
    withDirectives,
  } from 'vue';

  import { Button, ResizeLayout, Tab } from 'bkui-vue';

  import { type Message, type UserMessage, MessageStatus } from '../../ag-ui/types';
  import { LOADING_MESSAGE_ID, RenderMode } from '../../common';
  import { useMessageGroup } from '../../composables';
  import { useCommonTippyProvider } from '../../composables/use-common';
  import { EXECUTION_TAB_NAME, useCustomTabProvider } from '../../composables/use-custom-tab';
  import { useGlobalConfig } from '../../composables/use-global-config';
  import { OverflowTips as vOverflowTips } from '../../directives';
  import { CloseIcon, ExecutionIcon, NodeTabIcon } from '../../icons';
  import { AIBluekingBannerIcon } from '../../icons';
  import { t } from '../../lang/lang';
  import ShortcutRender from '../ai-shortcut/shortcut-render/shortcut-render.vue';
  import ContentRender from '../chat-content/content-render/content-render.vue';
  import ChatInput, { type ChatInputEmits, type ChatInputProps } from '../chat-input/chat-input.vue';
  import MessageContainer, {
    type MessageContainerEmits,
    type MessageContainerProps,
  } from '../chat-message/message-container/message-container.vue';
  import ExecutionSummary from '../execution-summary/execution-summary.vue';
  import MessageLoading from '../message-loading/message-loading.vue';
  import SelectionFooter from '../selection-footer/selection-footer.vue';

  import type {
    AITippyProps,
    CustomBkFlowTabData,
    CustomTab,
    IAiSlashMenuItem,
    IToolBtn,
    Shortcut,
    TagSchema,
  } from '../../types';
  import type { Token } from 'markdown-it/index.js';
  export type ChatContainerProps = {
    chatLoading?: boolean;
    commonTippyOptions?: AITippyProps;
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
    message: (props: {
      message: Message;
      messageToolsStatus: MessageContainerProps['messageToolsStatus'];
      onInterruptResume?: MessageContainerProps['onInterruptResume'];
    }) => null | undefined | VNode;
    welcome: (props: { openingRemark: ChatContainerProps['openingRemark'] }) => null | undefined | VNode;
  }>();
  const props = withDefaults(
    defineProps<
      ChatContainerProps &
        ChatInputProps &
        Omit<MessageContainerProps, 'enableSelection' | 'messageGroups' | 'messageToolsTippyOptions'>
    >(),
    {
      placement: 'left',
    },
  );
  const renderMode = defineModel<RenderMode>('renderMode', {
    required: false,
    default: RenderMode.Chat,
  });
  const resizeProps = computed(() => ({
    collapsible: false,
    immediate: true,
    min: 400,
    ...props.resizeProps,
    placement: props.placement,
  }));
  useGlobalConfig({
    supportUpload: computed(() => props.supportUpload ?? false),
  });
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

  const { tabs, selectedTab, isCollapse, addCustomTab, removeCustomTab, selectCustomTab, resetCustomTab } =
    useCustomTabProvider<CustomBkFlowTabData>({
      onTabChange: async tab => {
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
  const resizeAsideWidth = shallowRef<number>(400);
  const resizeMainWidth = computed(() => {
    return `calc(100% - ${resizeAsideWidth.value}px)`;
  });

  const {
    messageGroups,
    executionGroups,
    isShareMode,
    isAllSelected,
    onToggleShareAll,
    onCancelShare,
    onConfirmShare,
  } = useMessageGroup({
    keyword,
    messages: computed(() => props.messages),
    selectedUserMessages,
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
      if (!newVal.length) {
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
    font-size: 12px;
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
    }

    &-resize-layout {
      width: 100%;
      height: 100%;
      border: none !important;

      .bk-resize-layout-main,
      .bk-resize-layout-aside {
        display: flex;
        flex-direction: column;
        height: 100%;

        &-content {
          display: flex;
          flex-direction: column;
          height: 100%;
        }
      }

      .bk-resize-layout-main {
        position: relative;
        width: var(--resize-main-width);

        // width: 100%;
        padding: 8px;
        overflow: visible;
      }

      .bk-resize-layout-aside {
        display: flex;
      }

      &.ai-is-collapse {
        .bk-resize-layout-aside {
          flex: 0 0 0;
          width: 0;
          padding: 0;
          border: none;

          &::after {
            display: none;
          }

          .bk-resize-trigger {
            display: none;
          }

          .bk-resize-proxy {
            display: none;
          }
        }
      }
    }

    &-message-slot {
      width: 100%;
      height: calc(100% - 40px);

      .ai-locate-button {
        margin-left: auto;
        font-size: 12px;
        font-weight: normal;
      }
    }

    .collapse-button {
      position: absolute;
      top: 50%;
      left: -20px;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 20px;
      min-height: 96px;
      padding: 8px 4px;
      font-size: 12px;
      color: #4d4f56;
      background: #dcdee5;
      border-radius: 4px 0 0 4px;

      // box-shadow: 2px 0 4px 0 #0000001a;
      transform: translateY(-50%);

      &.is-right {
        right: -21px;
        left: auto;
        border-radius: 0 4px 4px 0;
      }

      .ai-common-icon {
        width: 12px;
        height: 12px;
        margin-bottom: 2px;
        font-size: 12px;
      }

      &:hover {
        color: #fff;
        cursor: pointer;
        background: #3a84ff;
        box-shadow: 2px 0 4px 0 #0000001a;
      }
    }

    .ai-welcome-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      max-width: 1000px;
      padding: 16px;
      margin: 0 auto;
      text-align: center;

      .ai-blueking-banner-icon {
        width: 309px;
        height: 100%;
      }

      .ai-welcome-title {
        margin: 0 0 16px;
        font-size: 20px;
        font-weight: 600;
        line-height: 28px;
        color: #313238;
      }

      .ai-welcome-remark {
        width: 100%;
        max-height: 240px;
        margin-bottom: 24px;
        flex-shrink: 0;
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
