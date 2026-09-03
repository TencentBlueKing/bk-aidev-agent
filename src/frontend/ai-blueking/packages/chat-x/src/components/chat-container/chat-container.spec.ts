/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { type Ref, defineComponent, h, nextTick } from 'vue';

import { type ComponentMountingOptions, type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { APPROVAL_STATUS, InterruptReason, MessageRole, MessageStatus } from '../../ag-ui/types';
import { LOADING_MESSAGE_ID, RenderMode } from '../../common';
import { useCustomTabProvider } from '../../composables/use-custom-tab';
import { useGlobalConfig } from '../../composables/use-global-config';
import ChatContainer, { type ChatContainerProps } from './chat-container.vue';

import type { AssistantMessage, Message, UserMessage, UserQuestionInterrupt } from '../../ag-ui/types';

/** defineExpose 暴露的实例 API */
type ChatContainerExposed = {
  addCustomTab: (tab: { data?: Record<string, unknown>; label: string; name: string }) => void;
  enterShareMode: () => void;
  exitShareMode: () => void;
  removeCustomTab: (name: string) => void;
  selectCustomTab: (tab: unknown) => void;
  selectedTab: unknown;
};

/** 测试 mount 时使用的 props 集合 */
type ChatContainerMountProps = ChatContainerProps & {
  messages: Message[];
  messageStatus: MessageStatus;
  modelValue: string;
  renderMode?: RenderMode;
};

type MockMessageGroup = {
  messages: Array<{ id?: string }>;
  type?: string;
  uid?: string;
};

const getChatContainerExposed = (w: VueWrapper): ChatContainerExposed => w.vm as unknown as ChatContainerExposed;

const getMountProps = (w: VueWrapper): ChatContainerMountProps => w.props() as ChatContainerMountProps;

/** 供 useMessageGroup mock 注入，用于验证 inputStatus 对 Loading 占位消息的推导 */
const mockMessageGroupsRef = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { ref: vueRef } = require('vue');
  return vueRef([]) as Ref<MockMessageGroup[]>;
});
const mockExecutionGroupsRef = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { ref: vueRef } = require('vue');
  return vueRef([]) as Ref<unknown[]>;
});
/** 供 useMessageGroup mock 注入会话级文件产物，验证 ensureCustomTab 常驻挂载 */
const mockSessionArtifactsRef = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { ref: vueRef } = require('vue');
  return vueRef([]) as Ref<Array<{ name: string; outputId: string; size: number; type: string }>>;
});
const mockUseMessageGroup = vi.hoisted(() => vi.fn());
const mockUseRenderModeProvider = vi.hoisted(() => vi.fn());

vi.mock('bkui-vue', () => {
  const Button = defineComponent({
    name: 'Button',
    props: {
      size: { type: String, default: '' },
      text: { type: Boolean, default: false },
      theme: { type: String, default: 'default' },
    },
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () =>
        h('button', { class: 'mock-bk-button', type: 'button', onClick: () => emit('click') }, slots.default?.());
    },
  });

  const TabPanel = defineComponent({
    name: 'TabPanel',
    props: { name: String, label: [String, Function] },
    setup(props, { slots }) {
      return () =>
        h('div', { class: 'mock-tab-panel', 'data-name': props.name }, [
          typeof props.label === 'function' ? props.label() : props.label,
          slots.default?.(),
        ]);
    },
  });

  const Tab = defineComponent({
    name: 'Tab',
    props: {
      active: String,
      labelHeight: Number,
      type: String,
    },
    emits: ['change'],
    setup(_, { slots }) {
      return () =>
        h('div', { class: 'mock-tab' }, [
          slots.default?.(),
          slots.setting ? h('div', { class: 'mock-tab-setting' }, slots.setting()) : null,
        ]);
    },
  });
  (Tab as unknown as Record<string, unknown>).TabPanel = TabPanel;

  return {
    Button,
    ResizeLayout: defineComponent({
      name: 'ResizeLayout',
      props: {
        collapsible: Boolean,
        disabled: Boolean,
        immediate: Boolean,
        initialDivide: [Number, String],
        max: Number,
        min: Number,
        placement: String,
      },
      emits: ['resizing', 'after-resize'],
      setup(_, { slots }) {
        return () =>
          h('div', { class: 'mock-resize-layout' }, [
            h('div', { class: 'bk-resize-layout-aside' }, slots.aside?.()),
            h('div', { class: 'bk-resize-layout-main' }, slots.main?.()),
          ]);
      },
    }),
    Tab,
  };
});

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../composables', () => ({
  useMessageGroup: mockUseMessageGroup.mockImplementation(
    (_options: { keyword: { value: string }; messages: { value: Message[] } }) => {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { computed, shallowRef } = require('vue');
      const messageGroups = mockMessageGroupsRef;
      const executionGroups = computed(() => mockExecutionGroupsRef.value);
      const pendingApprovalCount = computed(() =>
        _options.messages.value.reduce((count, message) => {
          if (message.role !== MessageRole.Interrupt || message.content?.outcome?.type !== 'interrupt') {
            return count;
          }
          return (
            count +
            message.content.outcome.interrupts.filter(
              interrupt =>
                interrupt.reason === InterruptReason.AIDevToolApproval &&
                [APPROVAL_STATUS.PENDING, APPROVAL_STATUS.DRAFT].includes(interrupt.metadata?.ticket?.status),
            ).length
          );
        }, 0),
      );
      const pendingApprovalTipText = computed(() =>
        pendingApprovalCount.value ? `当前会话有 ${pendingApprovalCount.value} 个待审批单，如需继续，请先取消审批` : '',
      );
      const activeUserQuestionInterrupt = computed(() => {
        for (let index = _options.messages.value.length - 1; index >= 0; index--) {
          const message = _options.messages.value[index];
          if (message.role !== MessageRole.Interrupt || message.content?.outcome?.type !== 'interrupt') {
            continue;
          }
          const question = message.content.outcome.interrupts.find(
            interrupt => interrupt.reason === InterruptReason.UserQuestion,
          );
          if (question) return question;
        }
        return undefined;
      });
      const isShareMode = shallowRef(false);
      const isAllSelected = computed(() => false);
      return {
        messageGroups,
        executionGroups,
        sessionArtifacts: computed(() => mockSessionArtifactsRef.value),
        activeUserQuestionInterrupt,
        pendingApprovalCount,
        pendingApprovalTipText,
        isShareMode,
        isAllSelected,
        onToggleShareAll: vi.fn(),
        onCancelShare: vi.fn(() => {
          isShareMode.value = false;
        }),
        onConfirmShare: vi.fn(() => []),
      };
    },
  ),
}));

vi.mock('../../composables/use-common', () => ({
  useCommonTippyProvider: vi.fn(),
  useKeywordProvider: () => ({
    keyword: { value: '' },
  }),
  useRenderModeProvider: mockUseRenderModeProvider,
}));

vi.mock('../../composables/use-global-config', () => ({
  useGlobalConfig: vi.fn(() => ({
    supportUpload: { value: false },
  })),
}));

vi.mock('../../directives', () => ({
  OverflowTips: { mounted: vi.fn(), updated: vi.fn(), unmounted: vi.fn() },
}));

vi.mock('../../composables/use-custom-tab', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { shallowRef, ref: deepRef, computed, provide } = require('vue');
  const CUSTOM_TAB_TOKEN = Symbol('CUSTOM_TAB_TOKEN');
  const EXECUTION_TAB_NAME = 'execution';
  const DEFAULT_TAB_ORDER = 100;
  return {
    CUSTOM_TAB_TOKEN,
    DEFAULT_TAB_ORDER,
    EXECUTION_TAB_NAME,
    useCustomTabProvider: vi.fn(
      (_options: {
        collapsed?: { value: boolean };
        executionTabVisible?: () => boolean | undefined;
        onTabChange?: (tab: unknown) => void;
      }) => {
        const EXECUTION_TAB = { closable: false, label: '执行情况', name: EXECUTION_TAB_NAME, order: 0 };
        const tabs = shallowRef([EXECUTION_TAB]);
        const selectedTab = deepRef(EXECUTION_TAB);
        // 折叠态由容器以受控 ref 注入，缺省退化为内部状态
        const isCollapse = _options.collapsed ?? shallowRef(true);

        const isExecutionVisible = () => _options.executionTabVisible?.() ?? true;
        const displayTabs = computed(() =>
          tabs.value
            .filter((tab: { name: string; visible?: boolean }) =>
              tab.name === EXECUTION_TAB_NAME ? isExecutionVisible() : tab.visible !== false,
            )
            .slice()
            .sort(
              (a: { order?: number }, b: { order?: number }) =>
                (a.order ?? DEFAULT_TAB_ORDER) - (b.order ?? DEFAULT_TAB_ORDER),
            ),
        );

        const ensureCustomTab = vi.fn((tab: { label: string; name: string }) => {
          if (!tabs.value.find((t: { name: string }) => t.name === tab.name)) {
            tabs.value = [...tabs.value, tab];
          }
        });
        const addCustomTab = vi.fn((tab: { label: string; name: string }) => {
          ensureCustomTab(tab);
          isCollapse.value = false;
        });
        const removeCustomTab = vi.fn((name: string) => {
          tabs.value = tabs.value.filter((t: { name: string }) => t.name !== name);
        });
        const selectCustomTab = vi.fn((tab: unknown) => {
          selectedTab.value = tab ?? EXECUTION_TAB;
          _options.onTabChange?.(tab);
        });
        const resetCustomTab = vi.fn(() => {
          tabs.value = [EXECUTION_TAB];
          selectedTab.value = EXECUTION_TAB;
          isCollapse.value = true;
        });

        provide(CUSTOM_TAB_TOKEN, {
          tabs,
          displayTabs,
          selectedTab,
          addCustomTab,
          ensureCustomTab,
          removeCustomTab,
          selectCustomTab,
          resetCustomTab,
        });

        return {
          tabs,
          displayTabs,
          selectedTab,
          isCollapse,
          addCustomTab,
          ensureCustomTab,
          removeCustomTab,
          selectCustomTab,
          resetCustomTab,
        };
      },
    ),
    useCustomTabConsumer: vi.fn(() => undefined),
  };
});

vi.mock('../../icons', () => ({
  CloseIcon: defineComponent({
    name: 'CloseIcon',
    setup() {
      return () => h('span', { class: 'mock-close-icon' });
    },
  }),
  ExecutionIcon: defineComponent({
    name: 'ExecutionIcon',
    setup() {
      return () => h('span', { class: 'mock-execution-icon' });
    },
  }),
  FullScreenIcon: defineComponent({
    name: 'FullScreenIcon',
    setup() {
      return () => h('span', { class: 'mock-full-screen-icon' });
    },
  }),
  UnFullScreenIcon: defineComponent({
    name: 'UnFullScreenIcon',
    setup() {
      return () => h('span', { class: 'mock-un-full-screen-icon' });
    },
  }),
  NodeTabIcon: defineComponent({
    name: 'NodeTabIcon',
    setup() {
      return () => h('span', { class: 'mock-node-tab-icon' });
    },
  }),
  AIBluekingBannerIcon: defineComponent({
    name: 'AIBluekingBannerIcon',
    setup() {
      return () => h('span', { class: 'mock-banner-icon' });
    },
  }),
  // 文件产物 Tab 默认图标：设计稿 16×16 线性折角文档
  ArtifactTabIcon: defineComponent({
    name: 'ArtifactTabIcon',
    setup() {
      return () => h('span', { class: 'mock-artifact-tab-icon' });
    },
  }),
}));

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('vue-tippy', () => ({
  directive: {
    mounted: vi.fn(),
    unmounted: vi.fn(),
  },
}));

vi.mock('../ai-shortcut/shortcut-render/shortcut-render.vue', () => ({
  default: defineComponent({
    name: 'ShortcutRender',
    props: {
      class: { type: [String, Object, Array], default: '' },
    },
    emits: ['close', 'submit'],
    setup(props) {
      return () => h('div', { class: ['mock-shortcut-render', props.class] });
    },
  }),
}));

vi.mock('../chat-content/content-render/content-render.vue', () => ({
  default: defineComponent({
    name: 'ContentRender',
    props: { content: String },
    setup(props) {
      return () => h('div', { class: 'mock-content-render' }, props.content);
    },
  }),
}));

vi.mock('../chat-input/chat-input.vue', () => ({
  default: defineComponent({
    name: 'ChatInput',
    props: {
      modelValue: [String, Array],
      messageStatus: String,
      placeholder: String,
      prompts: Array,
      resources: Array,
      shortcuts: Array,
      skills: Array,
      models: Array,
      selectedModel: String,
      supportUpload: Boolean,
      cite: String,
      shortcutId: String,
      sendDisabledTip: String,
      onSendMessage: Function,
      onStopSending: Function,
      onUpload: Function,
      tippyOptions: Object,
    },
    emits: [
      'update:modelValue',
      'update:cite',
      'update:selectedModel',
      'selectShortcut',
      'deleteShortcut',
      'modelChange',
    ],
    setup(_, { slots }) {
      return () => h('div', { class: 'mock-chat-input' }, [slots.top?.(), slots.interrupt?.()]);
    },
  }),
}));

vi.mock('../chat-input/input-info-alert.vue', () => ({
  default: defineComponent({
    name: 'InputInfoAlert',
    props: {
      content: String,
    },
    setup(props) {
      return () => h('div', { class: 'mock-input-info-alert' }, props.content);
    },
  }),
}));

vi.mock('../chat-message/interrupt-message/user-question', () => ({
  buildSkipResumePayload: (interrupt?: UserQuestionInterrupt) => ({
    interruptId: interrupt?.id ?? '',
    reason: InterruptReason.UserQuestion,
    status: 'cancelled',
    payload: { answers: [] },
  }),
  UserQuestionCard: defineComponent({
    name: 'UserQuestionCard',
    props: {
      interrupt: Object,
      onResume: Function,
    },
    setup() {
      return () => h('div', { class: 'mock-user-question-card' });
    },
  }),
}));

vi.mock('../chat-message/message-container/message-container.vue', () => ({
  default: defineComponent({
    name: 'MessageContainer',
    props: {
      messages: Array,
      messageGroups: Array,
      messageStatus: String,
      messageToolsStatus: String,
      messageToolsTippyOptions: Object,
      enableSelection: Boolean,
      selectedUserMessages: Array,
      onAgentAction: Function,
      onAgentFeedback: Function,
      onUserAction: Function,
      onUserInputConfirm: Function,
      onUserShortcutConfirm: Function,
      renderMode: String,
      updateTools: Array,
      userMessageTools: Array,
    },
    emits: ['stopStreaming', 'update:selectedUserMessages'],
    setup(props, { slots }) {
      return () =>
        h(
          'div',
          { class: 'mock-message-container', 'data-render-mode': props.renderMode },
          (
            props.messageGroups as Array<{
              messages: Array<{ id?: string }>;
              type: string;
              uid: string;
            }>
          )?.map(group => slots.group?.({ group }) ?? h('div', { class: 'default-group-fallback' })),
        );
    },
  }),
}));

vi.mock('../message-loading/message-loading.vue', () => ({
  default: defineComponent({
    name: 'MessageLoading',
    setup() {
      return () => h('div', { class: 'mock-message-loading' });
    },
  }),
}));

vi.mock('../execution-summary/execution-summary.vue', () => ({
  default: defineComponent({
    name: 'ExecutionSummary',
    props: { messageGroups: Array },
    emits: ['locateMessageGroup', 'updateKeyword'],
    setup() {
      return () => h('div', { class: 'mock-execution-summary' });
    },
  }),
}));

vi.mock('../selection-footer/selection-footer.vue', () => ({
  default: defineComponent({
    name: 'SelectionFooter',
    props: {
      isAllSelected: Boolean,
      loading: Boolean,
      selectedCount: Number,
    },
    emits: ['cancel', 'confirm', 'toggle-all'],
    setup() {
      return () => h('div', { class: 'mock-selection-footer' });
    },
  }),
}));

const createUserMessage = (id: string, content: string): UserMessage => ({
  id,
  content,
  messageId: id,
  role: MessageRole.User,
  status: MessageStatus.Complete,
});

const createAssistantMessage = (id: string, content: string): AssistantMessage => ({
  id,
  content,
  messageId: id,
  role: MessageRole.Assistant,
  status: MessageStatus.Complete,
});

const createApprovalInterruptMessage = (id: string, status: APPROVAL_STATUS): Message =>
  ({
    id,
    messageId: id,
    role: MessageRole.Interrupt,
    status: MessageStatus.Complete,
    content: {
      outcome: {
        type: 'interrupt',
        interrupts: [
          {
            id: `${id}-interrupt`,
            reason: InterruptReason.AIDevToolApproval,
            toolCallId: `${id}-tool`,
            metadata: {
              ticket: {
                approvers: ['张三'],
                sn: `REV-${id}`,
                status,
                submit_time: '2026-04-24 14:30:15',
                title: '算法方案评审单',
                url: 'https://example.com/ticket',
              },
            },
          },
        ],
      },
    },
  }) as Message;

const createUserQuestionInterruptMessage = (id: string): Message =>
  ({
    id,
    messageId: id,
    role: MessageRole.Interrupt,
    status: MessageStatus.Pending,
    content: {
      outcome: {
        type: 'interrupt',
        interrupts: [
          {
            id: `${id}-interrupt`,
            reason: InterruptReason.UserQuestion,
            toolCallId: `${id}-tool`,
            message: '请回答问题',
            metadata: {
              questions: [
                {
                  header: '请回答问题',
                  multiSelect: false,
                  question: '请选择语言',
                  options: [{ label: 'A', description: 'Java' }],
                },
              ],
            },
          },
        ],
      },
    },
  }) as Message;

describe('ChatContainer', () => {
  let wrapper: VueWrapper;

  const defaultProps: ChatContainerMountProps = {
    messages: [],
    messageStatus: MessageStatus.Complete,
    /** ChatInput 必填 v-model，避免测试告警 */
    modelValue: '',
  };

  /** welcome 插槽单测：仅注入 welcome，避免补齐全部 slots 类型 */
  const mountWithWelcomeSlot = (openingRemark: string) => {
    const options = {
      props: { ...defaultProps, openingRemark },
      slots: {
        welcome: ({ openingRemark: remark }: { openingRemark?: string }) =>
          h('div', { class: 'custom-welcome' }, `自定义: ${remark ?? ''}`),
      },
    } as unknown as ComponentMountingOptions<typeof ChatContainer>;
    return mount(ChatContainer, options);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockMessageGroupsRef.value = [];
    mockExecutionGroupsRef.value = [];
    mockSessionArtifactsRef.value = [];
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.find('.ai-chat-container').exists()).toBe(true);
    });

    it('执行摘要 Tab 图标尺寸应为 16px', () => {
      const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'chat-container.vue'), 'utf-8');
      expect(source).toMatch(/\.ai-execution-summary-icon[\s\S]*?width:\s*16px/);
    });

    it('chatLoading 为 true 时应该显示 loading', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, chatLoading: true },
      });

      expect(wrapper.find('.ai-chat-container-loading').exists()).toBe(true);
      expect(wrapper.find('.mock-message-loading').exists()).toBe(true);
    });

    it('chatLoading 为 false 时应该显示主体内容', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, chatLoading: false },
      });

      expect(wrapper.find('.mock-resize-layout').exists()).toBe(true);
    });

    it('无消息时应该显示欢迎内容', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages: [] },
      });

      expect(wrapper.find('.ai-welcome-content').exists()).toBe(true);
      expect(wrapper.find('.mock-banner-icon').exists()).toBe(true);
    });

    it('欢迎态应将 ai-is-welcome 加在 resize-layout 上，便于主栏单独承担 padding-top', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages: [] },
      });

      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).toContain('ai-is-welcome');
    });

    it('有消息时不应带 ai-is-welcome', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).not.toContain('ai-is-welcome');
    });

    it('有消息时应该显示 MessageContainer', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      expect(wrapper.find('.mock-message-container').exists()).toBe(true);
    });

    it('有 openingRemark 时应该渲染开场白', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, openingRemark: '欢迎使用' },
      });

      expect(wrapper.find('.ai-welcome-remark').exists()).toBe(true);
      expect(wrapper.find('.mock-content-render').text()).toBe('欢迎使用');
    });

    it('无 openingRemark 时不渲染开场白', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.find('.ai-welcome-remark').exists()).toBe(false);
    });

    it('应该支持 welcome 插槽自定义欢迎内容', () => {
      wrapper = mountWithWelcomeSlot('默认开场白');

      expect(wrapper.find('.custom-welcome').exists()).toBe(true);
      expect(wrapper.find('.custom-welcome').text()).toBe('自定义: 默认开场白');
      expect(wrapper.find('.ai-welcome-remark').exists()).toBe(false);
    });

    it('使用 welcome 插槽时应替换整块默认欢迎区（含 Banner 与默认标题）', () => {
      wrapper = mountWithWelcomeSlot('默认开场白');

      expect(wrapper.find('.mock-banner-icon').exists()).toBe(false);
      expect(wrapper.find('.ai-welcome-title').exists()).toBe(false);
    });

    it('不传 welcome 插槽时应使用默认开场白渲染', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, openingRemark: '欢迎使用' },
      });

      expect(wrapper.find('.ai-welcome-remark').exists()).toBe(true);
      expect(wrapper.find('.mock-content-render').text()).toBe('欢迎使用');
    });

    it('空态下选中快捷指令时应为 ShortcutRender 添加 is-welcome-overlay 类', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          messages: [],
          selectedShortcut: {
            id: 'shortcut1',
            name: '测试快捷指令',
            components: [{ id: 'c1', key: 'field1', type: 'input', name: '字段1' }],
          },
        },
      });

      expect(wrapper.find('.mock-shortcut-render.is-welcome-overlay').exists()).toBe(true);
      expect(wrapper.find('.ai-welcome-content').exists()).toBe(true);
    });

    it('有消息时选中快捷指令不应添加 is-welcome-overlay 类', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          messages,
          selectedShortcut: {
            id: 'shortcut1',
            name: '测试快捷指令',
            components: [{ id: 'c1', key: 'field1', type: 'input', name: '字段1' }],
          },
        },
      });

      expect(wrapper.find('.mock-shortcut-render').exists()).toBe(true);
      expect(wrapper.find('.mock-shortcut-render.is-welcome-overlay').exists()).toBe(false);
    });

    it('应该支持 group 插槽自定义消息组渲染', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockMessageGroupsRef.value = [
        { messages: [{ id: '1' }], type: MessageRole.User, uid: 'group-user-1' },
        { messages: [{ id: '2' }], type: MessageRole.Assistant, uid: 'group-assistant-2' },
      ];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
        slots: {
          group: ({ group }: { group: { type: string; uid: string } }) =>
            h('div', { class: 'custom-group', 'data-uid': group.uid, 'data-type': group.type }, 'Custom Group'),
        },
      });

      const customGroups = wrapper.findAll('.custom-group');
      expect(customGroups.length).toBe(2);
      expect(customGroups[0].attributes('data-uid')).toBe('group-user-1');
      expect(customGroups[0].attributes('data-type')).toBe(MessageRole.User);
      expect(customGroups[1].attributes('data-uid')).toBe('group-assistant-2');
      expect(customGroups[1].attributes('data-type')).toBe(MessageRole.Assistant);
    });
  });

  describe('ChatInput 测试', () => {
    it('默认应该渲染 ChatInput', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.find('.mock-chat-input').exists()).toBe(true);
    });

    it('当分组中存在 LOADING_MESSAGE_ID 占位消息时，MessageContainer 与 ChatInput 应收到 Fetching 状态', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockMessageGroupsRef.value = [{ messages: [{ id: LOADING_MESSAGE_ID }] }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, messageStatus: MessageStatus.Complete },
      });

      const mc = wrapper.findComponent({ name: 'MessageContainer' });
      const ci = wrapper.findComponent({ name: 'ChatInput' });
      expect(mc.props('messageStatus')).toBe(MessageStatus.Fetching);
      expect(ci.props('messageStatus')).toBe(MessageStatus.Fetching);
    });

    it('无 Loading 占位时 messageStatus 应透传为 props.messageStatus', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockMessageGroupsRef.value = [{ messages: [{ id: 'other-id' }] }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, messageStatus: MessageStatus.Streaming },
      });

      const mc = wrapper.findComponent({ name: 'MessageContainer' });
      const ci = wrapper.findComponent({ name: 'ChatInput' });
      expect(mc.props('messageStatus')).toBe(MessageStatus.Streaming);
      expect(ci.props('messageStatus')).toBe(MessageStatus.Streaming);
    });

    it('应该将 skills 属性透传给 ChatInput', () => {
      const skills = [{ skill_code: 'test_skill', skill_name: 'Test Skill', description: 'A test skill', icon: '' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, skills },
      });

      const ci = wrapper.findComponent({ name: 'ChatInput' });
      expect(ci.props('skills')).toEqual(skills);
    });

    it('应该将 models 与 selectedModel 透传给 ChatInput', () => {
      const models = [{ id: 1, llm_name: 'GPT-4' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, models, selectedModel: 'GPT-4' },
      });

      const ci = wrapper.findComponent({ name: 'ChatInput' });
      expect(ci.props('models')).toEqual(models);
      expect(ci.props('selectedModel')).toBe('GPT-4');
    });

    it('ChatInput 触发 modelChange 时应向上冒泡', async () => {
      const models = [{ id: 1, llm_name: 'GPT-4' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, models },
      });

      const ci = wrapper.findComponent({ name: 'ChatInput' });
      await ci.vm.$emit('modelChange', models[0]);

      expect(wrapper.emitted('modelChange')?.[0]).toEqual([models[0]]);
    });

    it('存在待审批第三方审批单时应通过 slot 展示提示，并将阻断文案传给 ChatInput', () => {
      const messages = [
        createApprovalInterruptMessage('pending-1', APPROVAL_STATUS.PENDING),
        createApprovalInterruptMessage('draft-1', APPROVAL_STATUS.DRAFT),
        createApprovalInterruptMessage('revoked-1', APPROVAL_STATUS.REVOKED),
      ];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      const ci = wrapper.findComponent({ name: 'ChatInput' });
      expect(ci.props('sendDisabledTip')).toBe('当前会话有 2 个待审批单，如需继续，请先取消审批');
      expect(wrapper.find('.mock-input-info-alert').text()).toBe('当前会话有 2 个待审批单，如需继续，请先取消审批');
    });

    it('存在 UserQuestion 时，发送消息应附带 skip resume 选项且不清空输入', async () => {
      const messages = [createUserQuestionInterruptMessage('user-question-1')];
      const onSendMessage = vi.fn();

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, modelValue: '自由文本', onSendMessage },
      });

      const ci = wrapper.findComponent({ name: 'ChatInput' });
      const send = ci.props('onSendMessage') as (
        content: string,
        docSchema: Record<string, unknown>,
        options?: { interrupt?: UserQuestionInterrupt; payload?: unknown },
      ) => Promise<void>;
      const docSchema = {};
      await send('自由文本', docSchema);

      expect(onSendMessage).toHaveBeenCalledWith('自由文本', docSchema, {
        payload: expect.objectContaining({
          interruptId: 'user-question-1-interrupt',
          reason: InterruptReason.UserQuestion,
          status: 'cancelled',
          payload: { answers: [] },
        }),
        interrupt: expect.objectContaining({ id: 'user-question-1-interrupt' }),
      });
      expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    });

    it('无 UserQuestion 时，发送消息不应附带第三参数 options', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, modelValue: '普通消息', onSendMessage },
      });

      const ci = wrapper.findComponent({ name: 'ChatInput' });
      const send = ci.props('onSendMessage') as (
        content: string,
        docSchema: Record<string, unknown>,
        options?: unknown,
      ) => Promise<void>;
      const docSchema = {};
      await send('普通消息', docSchema);

      expect(onSendMessage).toHaveBeenCalledWith('普通消息', docSchema, undefined);
    });
  });

  describe('折叠测试', () => {
    it('不应再渲染内置折叠按钮（展开/收起交由外部）', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockExecutionGroupsRef.value = [{ id: 'group-1' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });
      await nextTick();

      expect(wrapper.find('.collapse-button').exists()).toBe(false);
      expect(wrapper.find('.mock-collapsed-icon').exists()).toBe(false);
    });

    it('默认应为折叠态', async () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });
      await nextTick();

      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).toContain('ai-is-collapse');
    });

    it('asideCollapsed 为 false 时侧栏应展开并渲染 Tab 栏', async () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, asideCollapsed: false },
      });
      await nextTick();

      expect(wrapper.find('.ai-chat-container-tab').exists()).toBe(true);
      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).not.toContain('ai-is-collapse');
    });

    it('根节点不应通过 inline border-top 绘制顶部分割线（改由业务 Header 贯穿全宽）', async () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, asideCollapsed: false },
      });
      await nextTick();

      const style = wrapper.find('.ai-chat-container').attributes('style') ?? '';
      expect(style).not.toMatch(/border-top/i);
    });

    it('外部切换 asideCollapsed 应触发 collapseChange', async () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, asideCollapsed: true },
      });
      await nextTick();

      await wrapper.setProps({ asideCollapsed: false });

      expect(wrapper.emitted('collapseChange')?.[0]?.[0]).toBe(false);
    });

    it('受控时内部展开动作只发 update:asideCollapsed，外部不改则保持折叠', async () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, asideCollapsed: true },
      });
      await nextTick();

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      expect(wrapper.emitted('update:asideCollapsed')?.[0]).toEqual([false]);
      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).toContain('ai-is-collapse');
    });

    it('未传 asideCollapsed 时内部展开动作应直接展开（非受控兜底）', async () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });
      await nextTick();

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).not.toContain('ai-is-collapse');
    });
  });

  describe('commonTippyOptions 测试', () => {
    const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

    it('非全屏未传 commonTippyOptions 时不应向子组件注入 appendTo', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      expect(wrapper.findComponent({ name: 'MessageContainer' }).props('messageToolsTippyOptions')).not.toHaveProperty(
        'appendTo',
      );
      expect(wrapper.findComponent({ name: 'ChatInput' }).props('tippyOptions')).not.toHaveProperty('appendTo');
    });

    it('非全屏应透传外部 commonTippyOptions.appendTo', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, commonTippyOptions: { appendTo: 'parent' } },
      });

      expect(wrapper.findComponent({ name: 'MessageContainer' }).props('messageToolsTippyOptions')).toMatchObject({
        appendTo: 'parent',
      });
      expect(wrapper.findComponent({ name: 'ChatInput' }).props('tippyOptions')).toMatchObject({
        appendTo: 'parent',
      });
    });
  });

  describe('全屏测试', () => {
    it('侧栏展开时应渲染全屏按钮区域', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockExecutionGroupsRef.value = [{ id: 'group-1' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      expect(wrapper.find('.screen-wrapper').exists()).toBe(true);
      expect(wrapper.find('.screen-btn').exists()).toBe(true);
      expect(wrapper.find('.mock-full-screen-icon').exists()).toBe(true);
    });
  });

  describe('Expose 测试', () => {
    it('应该暴露 selectedTab、addCustomTab、removeCustomTab、selectCustomTab', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      const exposed = getChatContainerExposed(wrapper);
      expect(exposed.selectedTab).toBeDefined();
      expect(exposed.addCustomTab).toBeDefined();
      expect(exposed.removeCustomTab).toBeDefined();
      expect(exposed.selectCustomTab).toBeDefined();
    });

    it('应该暴露 enterShareMode 和 exitShareMode 方法', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      const exposed = getChatContainerExposed(wrapper);
      expect(typeof exposed.enterShareMode).toBe('function');
      expect(typeof exposed.exitShareMode).toBe('function');
    });
  });

  describe('placement 测试', () => {
    it('侧栏应固定从右侧展开', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.findComponent({ name: 'ResizeLayout' }).props('placement')).toBe('right');
    });
  });

  describe('size 字号主题测试', () => {
    it('传入 size 为 normal 时根元素 data-ai-size 应为 normal', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, size: 'normal' },
      });

      expect(wrapper.find('.ai-chat-container').attributes('data-ai-size')).toBe('normal');
    });

    it('未传 size 时根元素 data-ai-size 默认应为 small', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.find('.ai-chat-container').attributes('data-ai-size')).toBe('small');
    });

    it('挂载时应将 size 同步到 document.body，供浮层继承字号主题', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, size: 'normal' },
      });

      expect(document.body.dataset.aiSize).toBe('normal');
    });

    it('size 变更时应更新 document.body.dataset.aiSize', async () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, size: 'small' },
      });
      expect(document.body.dataset.aiSize).toBe('small');

      await wrapper.setProps({ size: 'normal' });
      expect(document.body.dataset.aiSize).toBe('normal');
    });

    it('卸载时应清理 document.body 上的字号主题标记', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, size: 'normal' },
      });
      expect(document.body.dataset.aiSize).toBe('normal');

      wrapper.unmount();
      wrapper = undefined as unknown as VueWrapper;
      expect(document.body.dataset.aiSize).toBeUndefined();
    });
  });

  describe('timezone 消息时间时区测试', () => {
    /** 取本次挂载传给 useGlobalConfig 的配置对象 */
    const getInjectedConfig = () => vi.mocked(useGlobalConfig).mock.calls[0][0];

    it('传入 timezone 时应注入全局配置，供 MessageTime 读取', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, timezone: 'Asia/Shanghai' },
      });

      expect(getInjectedConfig().timezone?.value).toBe('Asia/Shanghai');
    });

    it('未传 timezone 时注入值应为 undefined（由 MessageTime 回退浏览器时区）', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(getInjectedConfig().timezone?.value).toBeUndefined();
    });
  });

  describe('resizeProps 测试', () => {
    it('ResizeLayout 应接收默认合并后的 resize 相关 props', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      const resize = wrapper.findComponent({ name: 'ResizeLayout' });
      expect(resize.props('collapsible')).toBe(false);
      expect(resize.props('immediate')).toBe(true);
      expect(resize.props('min')).toBe(400);
      expect(resize.props('placement')).toBe('right');
    });

    it('传入 resizeProps 应覆盖默认 min 并合并 initialDivide、max、disabled', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          resizeProps: { disabled: true, initialDivide: 500, max: 1000, min: 300 },
        },
      });

      const resize = wrapper.findComponent({ name: 'ResizeLayout' });
      expect(resize.props('min')).toBe(300);
      expect(resize.props('initialDivide')).toBe(500);
      expect(resize.props('max')).toBe(1000);
      expect(resize.props('disabled')).toBe(true);
      expect(resize.props('collapsible')).toBe(false);
      expect(resize.props('placement')).toBe('right');
    });

    it('resizeProps 不能覆盖固定的右侧 placement', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          resizeProps: { min: 200 },
        },
      });

      const resize = wrapper.findComponent({ name: 'ResizeLayout' });
      expect(resize.props('placement')).toBe('right');
      expect(resize.props('min')).toBe(200);
    });

    it('resizeProps.initialDivide 支持百分比字符串', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          resizeProps: { initialDivide: '33.33%' },
        },
      });

      const resize = wrapper.findComponent({ name: 'ResizeLayout' });
      expect(resize.props('initialDivide')).toBe('33.33%');
    });

    it('数字型 initialDivide 应作为侧栏初始宽度（--resize-main-width）', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          resizeProps: { initialDivide: 560 },
        },
      });

      expect(wrapper.find('.ai-chat-container').attributes('style')).toContain(
        '--resize-main-width: calc(100% - 560px)',
      );
    });

    it('未传或非数字 initialDivide 时侧栏初始宽度应为 400', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          resizeProps: { initialDivide: '33.33%' },
        },
      });

      expect(wrapper.find('.ai-chat-container').attributes('style')).toContain(
        '--resize-main-width: calc(100% - 400px)',
      );
    });

    it('展开侧栏时 collapseChange 应携带数字型 initialDivide 作为宽度', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockExecutionGroupsRef.value = [{ id: 'group-1' }];

      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          messages,
          resizeProps: { initialDivide: 560 },
        },
      });
      await nextTick();

      await wrapper.setProps({ asideCollapsed: false });

      const events = wrapper.emitted('collapseChange');
      expect(events).toBeTruthy();
      expect(events?.[0]).toEqual([false, 560]);
    });

    it('折叠后再展开应恢复侧栏宽度', async () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          asideCollapsed: false,
          resizeProps: { initialDivide: 560 },
        },
      });
      await nextTick();

      await wrapper.setProps({ asideCollapsed: true });
      expect(wrapper.find('.ai-chat-container').attributes('style')).toContain('--resize-main-width: calc(100% - 0px)');

      await wrapper.setProps({ asideCollapsed: false });
      expect(wrapper.find('.ai-chat-container').attributes('style')).toContain(
        '--resize-main-width: calc(100% - 560px)',
      );
    });
  });

  describe('renderMode 测试', () => {
    it('renderMode 默认应为 RenderMode.Chat', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      const mc = wrapper.findComponent({ name: 'MessageContainer' });
      expect(mc.attributes('data-render-mode')).toBe(RenderMode.Chat);
    });

    it('传入 renderMode 应透传给 MessageContainer', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Test },
      });

      const mc = wrapper.findComponent({ name: 'MessageContainer' });
      expect(mc.attributes('data-render-mode')).toBe(RenderMode.Test);
    });

    it('传入 userMessageTools 应透传给 MessageContainer', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      const userMessageTools = [{ id: 'edit', hidden: true }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, userMessageTools },
      });

      const mc = wrapper.findComponent({ name: 'MessageContainer' });
      expect(mc.props('userMessageTools')).toEqual(userMessageTools);
    });

    it('应将 renderMode 提供给后代组件', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, renderMode: RenderMode.Share },
      });

      const providerOptions = mockUseRenderModeProvider.mock.calls.at(-1)?.[0] as {
        renderMode: { value: RenderMode };
      };
      expect(providerOptions.renderMode.value).toBe(RenderMode.Share);
    });

    it('renderMode 为 Share 时应开放侧栏 Tab（只读查看）', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockExecutionGroupsRef.value = [{ id: 'group-1' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Share },
      });
      await nextTick();

      // 展开侧栏后，Tab（节点详情/证据/执行情况面板）在分享态可见
      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();
      expect(wrapper.find('.ai-chat-container-tab').exists()).toBe(true);
    });

    it('renderMode 为 Share 时不再强制 ai-is-collapse（展开后侧栏展开）', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      mockExecutionGroupsRef.value = [{ id: 'group-1' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Share },
      });
      await nextTick();

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).not.toContain('ai-is-collapse');
    });

    it('renderMode 为 Share 时底部输入区域（ChatInput、SelectionFooter、ShortcutRender）不应渲染', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Share },
      });

      expect(wrapper.find('.mock-chat-input').exists()).toBe(false);
      expect(wrapper.find('.mock-selection-footer').exists()).toBe(false);
      expect(wrapper.find('.mock-shortcut-render').exists()).toBe(false);
    });

    it('renderMode 非 Share 时底部输入区域应正常渲染', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Chat },
      });

      expect(wrapper.find('.mock-chat-input').exists()).toBe(true);
    });
  });

  describe('侧边栏渲染扩展', () => {
    it('应接收 getSideRenderComponent 与 getSideTabRenderComponent 属性', () => {
      const getSideRenderComponent = vi.fn();
      const getSideTabRenderComponent = vi.fn();

      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          getSideRenderComponent,
          getSideTabRenderComponent,
        },
      });

      expect(getMountProps(wrapper).getSideRenderComponent).toBe(getSideRenderComponent);
      expect(getMountProps(wrapper).getSideTabRenderComponent).toBe(getSideTabRenderComponent);
    });

    it('无 executionGroups、无产物时 asideCollapsed 为 false 仍应展开并渲染 Tab', async () => {
      mockExecutionGroupsRef.value = [];
      mockSessionArtifactsRef.value = [];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, asideCollapsed: false },
      });
      await nextTick();

      expect(wrapper.find('.ai-chat-container-tab').exists()).toBe(true);
      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).not.toContain('ai-is-collapse');
    });

    it('executionGroups 变空时不应调用 resetCustomTab', async () => {
      mockExecutionGroupsRef.value = [{ id: 'group-1' }];

      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          asideCollapsed: false,
          messages: [createUserMessage('1', 'Hello')],
        },
      });
      await nextTick();

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      const providerApi = vi.mocked(useCustomTabProvider).mock.results.at(-1)?.value as {
        resetCustomTab: ReturnType<typeof vi.fn>;
      };
      providerApi.resetCustomTab.mockClear();

      mockExecutionGroupsRef.value = [];
      await nextTick();

      expect(providerApi.resetCustomTab).not.toHaveBeenCalled();
      expect(wrapper.find('.ai-chat-container-tab').exists()).toBe(true);
    });

    it('asideCollapsed 为 false 时即使无搜索关键词也应展示 Tab', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, asideCollapsed: false },
      });
      await nextTick();

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      expect(wrapper.find('.ai-chat-container-tab').exists()).toBe(true);
      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).not.toContain('ai-is-collapse');
    });

    it('传入 getSideTabRenderComponent 时应优先使用其渲染 Tab 标签', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];
      const getSideTabRenderComponent = vi.fn((createElement, tab) =>
        createElement('span', { class: 'custom-tab-label' }, tab.name),
      );

      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          messages,
          asideCollapsed: false,
          getSideTabRenderComponent,
        },
      });
      await nextTick();

      getChatContainerExposed(wrapper).addCustomTab({ label: '自定义 Tab', name: 'custom-tab' });
      await nextTick();

      expect(getSideTabRenderComponent).toHaveBeenCalled();
      expect(wrapper.find('.custom-tab-label').exists()).toBe(true);
    });

    it('无文件产物时也应常驻挂上文件产物 Tab', async () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });
      await nextTick();

      const providerApi = vi.mocked(useCustomTabProvider).mock.results.at(-1)?.value as {
        ensureCustomTab: ReturnType<typeof vi.fn>;
        tabs: { value: { name: string }[] };
      };

      expect(providerApi.ensureCustomTab).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'file-artifact', closable: false, order: -1 }),
      );
      expect(providerApi.tabs.value.some(tab => tab.name === 'file-artifact')).toBe(true);
    });

    it('有 sessionArtifacts 时应 ensureCustomTab 挂上文件产物且不展开', async () => {
      mockSessionArtifactsRef.value = [{ name: '报告.pdf', outputId: 'out-1', size: 1024, type: 'pdf' }];
      // 文件产物 Tab 常驻挂上；展开/选中由 useCustomTab 自身规则负责（本用例 mock 只验挂载与不展开）
      mockExecutionGroupsRef.value = [{ messages: [{ id: 't1' }], type: MessageRole.Tool, uid: 'exec-1' }];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages: [createUserMessage('1', 'Hello')] },
      });
      await nextTick();

      const providerApi = vi.mocked(useCustomTabProvider).mock.results.at(-1)?.value as {
        addCustomTab: ReturnType<typeof vi.fn>;
        ensureCustomTab: ReturnType<typeof vi.fn>;
        isCollapse: { value: boolean };
        tabs: { value: { name: string }[] };
      };

      expect(providerApi.ensureCustomTab).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'file-artifact', closable: false, order: -1 }),
      );
      expect(providerApi.addCustomTab).not.toHaveBeenCalled();
      expect(providerApi.tabs.value.some(tab => tab.name === 'file-artifact')).toBe(true);
      expect(providerApi.isCollapse.value).toBe(true);
    });
  });

  describe('多选态触发与来源参数测试', () => {
    const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

    // MessageContainer 的 onAgentAction 即内部 handleAgentAction
    const getAgentAction = () =>
      wrapper.findComponent({ name: 'MessageContainer' }).props('onAgentAction') as (
        tool: Record<string, unknown>,
        msgs: Message[],
      ) => Promise<unknown>;

    it('点击标记 triggerSelection 的工具应进入多选态（渲染 SelectionFooter）', async () => {
      wrapper = mount(ChatContainer, { props: { ...defaultProps, messages } });
      await nextTick();
      expect(wrapper.find('.mock-selection-footer').exists()).toBe(false);

      await getAgentAction()({ id: 'save', triggerSelection: true }, []);
      await nextTick();

      expect(wrapper.find('.mock-selection-footer').exists()).toBe(true);
    });

    it('点击 share 按钮应进入多选态', async () => {
      wrapper = mount(ChatContainer, { props: { ...defaultProps, messages } });
      await nextTick();

      await getAgentAction()({ id: 'share' }, []);
      await nextTick();

      expect(wrapper.find('.mock-selection-footer').exists()).toBe(true);
    });

    it('普通工具（无 triggerSelection）不应进入多选态且应调用 onAgentAction', async () => {
      const onAgentAction = vi.fn();
      wrapper = mount(ChatContainer, { props: { ...defaultProps, messages, onAgentAction } });
      await nextTick();

      const copyTool = { id: 'copy' };
      await getAgentAction()(copyTool, []);
      await nextTick();

      expect(wrapper.find('.mock-selection-footer').exists()).toBe(false);
      expect(onAgentAction).toHaveBeenCalledWith(copyTool, []);
    });

    it('确认多选应 emit confirmShare 并携带来源工具对象作为第二参数', async () => {
      wrapper = mount(ChatContainer, { props: { ...defaultProps, messages } });
      await nextTick();

      const saveTool = { id: 'save', name: '保存', triggerSelection: true };
      await getAgentAction()(saveTool, []);
      await nextTick();

      await wrapper.findComponent({ name: 'SelectionFooter' }).vm.$emit('confirm');
      await nextTick();

      const emitted = wrapper.emitted('confirmShare');
      expect(emitted).toBeTruthy();
      // onConfirmShare mock 返回 []，第二参数为来源工具对象
      expect(emitted?.[0]?.[0]).toEqual([]);
      expect(emitted?.[0]?.[1]).toEqual(saveTool);
    });

    it('share 确认时第二参数来源应为 share 工具对象', async () => {
      wrapper = mount(ChatContainer, { props: { ...defaultProps, messages } });
      await nextTick();

      await getAgentAction()({ id: 'share' }, []);
      await nextTick();

      await wrapper.findComponent({ name: 'SelectionFooter' }).vm.$emit('confirm');
      await nextTick();

      const emitted = wrapper.emitted('confirmShare');
      expect(emitted?.[0]?.[1]).toEqual({ id: 'share' });
    });
  });
});
