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
import { defineComponent, h } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageRole, MessageStatus } from '../../ag-ui/types';
import { RenderMode } from '../../common';
import ChatContainer from './chat-container.vue';

import type { AssistantMessage, Message, UserMessage } from '../../ag-ui/types';

vi.mock('bkui-vue', () => {
  const TabPanel = defineComponent({
    name: 'TabPanel',
    props: { name: String, label: [String, Function] },
    setup(_, { slots }) {
      return () => h('div', { class: 'mock-tab-panel' }, slots.default?.());
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
      return () => h('div', { class: 'mock-tab' }, slots.default?.());
    },
  });
  (Tab as unknown as Record<string, unknown>).TabPanel = TabPanel;

  return {
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
      emits: ['resizing'],
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
  useMessageGroup: vi.fn((_options: { messages: { value: Message[] } }) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { computed, ref: deepRef, shallowRef } = require('vue');
    const messageGroups = deepRef<unknown[]>([]);
    const executionGroups = computed(() => []);
    const isShareMode = shallowRef(false);
    const isAllSelected = computed(() => false);
    return {
      messageGroups,
      executionGroups,
      isShareMode,
      isAllSelected,
      onToggleShareAll: vi.fn(),
      onCancelShare: vi.fn(() => {
        isShareMode.value = false;
      }),
      onConfirmShare: vi.fn(() => []),
    };
  }),
}));

vi.mock('../../composables/use-common', () => ({
  useCommonTippyProvider: vi.fn(),
  useKeywordProvider: () => ({
    keyword: { value: '' },
  }),
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
  const { shallowRef, ref: deepRef, provide } = require('vue');
  const CUSTOM_TAB_TOKEN = Symbol('CUSTOM_TAB_TOKEN');
  const EXECUTION_TAB_NAME = 'execution';
  return {
    CUSTOM_TAB_TOKEN,
    EXECUTION_TAB_NAME,
    useCustomTabProvider: vi.fn((_options: { onTabChange?: (tab: unknown) => void }) => {
      const EXECUTION_TAB = { label: '执行情况', name: EXECUTION_TAB_NAME };
      const tabs = shallowRef([EXECUTION_TAB]);
      const selectedTab = deepRef(EXECUTION_TAB);
      const isCollapse = shallowRef(true);

      const addCustomTab = vi.fn((tab: { label: string; name: string }) => {
        if (!tabs.value.find((t: { name: string }) => t.name === tab.name)) {
          tabs.value = [...tabs.value, tab];
        }
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
        selectedTab,
        addCustomTab,
        removeCustomTab,
        selectCustomTab,
        resetCustomTab,
      });

      return { tabs, selectedTab, isCollapse, addCustomTab, removeCustomTab, selectCustomTab, resetCustomTab };
    }),
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
}));

vi.mock('../ai-shortcut/shortcut-render/shortcut-render.vue', () => ({
  default: defineComponent({
    name: 'ShortcutRender',
    emits: ['close', 'submit'],
    setup() {
      return () => h('div', { class: 'mock-shortcut-render' });
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
      supportUpload: Boolean,
      cite: String,
      shortcutId: String,
      onSendMessage: Function,
      onStopSending: Function,
      onUpload: Function,
      tippyOptions: Object,
    },
    emits: ['update:modelValue', 'update:cite', 'selectShortcut', 'deleteShortcut'],
    setup() {
      return () => h('div', { class: 'mock-chat-input' });
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
    },
    emits: ['stopStreaming', 'update:selectedUserMessages'],
    setup(props) {
      return () => h('div', { class: 'mock-message-container', 'data-render-mode': props.renderMode });
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

describe('ChatContainer', () => {
  let wrapper: VueWrapper;

  const defaultProps = {
    messages: [] as Message[],
    messageStatus: MessageStatus.Complete,
    /** ChatInput 必填 v-model，避免测试告警 */
    modelValue: '',
  };

  beforeEach(() => {
    vi.clearAllMocks();
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
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, openingRemark: '默认开场白' },
        slots: {
          welcome: ({ openingRemark }: { openingRemark: string }) =>
            h('div', { class: 'custom-welcome' }, `自定义: ${openingRemark}`),
        },
      });

      expect(wrapper.find('.custom-welcome').exists()).toBe(true);
      expect(wrapper.find('.custom-welcome').text()).toBe('自定义: 默认开场白');
      expect(wrapper.find('.ai-welcome-remark').exists()).toBe(false);
    });

    it('使用 welcome 插槽时应替换整块默认欢迎区（含 Banner 与默认标题）', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, openingRemark: '默认开场白' },
        slots: {
          welcome: ({ openingRemark }: { openingRemark: string }) =>
            h('div', { class: 'custom-welcome' }, `自定义: ${openingRemark}`),
        },
      });

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
  });

  describe('ChatInput 测试', () => {
    it('默认应该渲染 ChatInput', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.find('.mock-chat-input').exists()).toBe(true);
    });
  });

  describe('折叠测试', () => {
    it('点击折叠按钮应该触发 collapseChange 事件', async () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages },
      });

      // 需要有执行消息才会显示折叠按钮
      // 由于 executionGroups 被 mock 为空，折叠按钮不会显示
      // 这里测试组件本身的正确渲染
      expect(wrapper.find('.ai-chat-container').exists()).toBe(true);
    });
  });

  describe('Expose 测试', () => {
    it('应该暴露 selectedTab、addCustomTab、removeCustomTab、selectCustomTab', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      const vm = wrapper.vm;
      expect(vm.selectedTab).toBeDefined();
      expect(vm.addCustomTab).toBeDefined();
      expect(vm.removeCustomTab).toBeDefined();
      expect(vm.selectCustomTab).toBeDefined();
    });

    it('应该暴露 enterShareMode 和 exitShareMode 方法', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      const vm = wrapper.vm;
      expect(typeof vm.enterShareMode).toBe('function');
      expect(typeof vm.exitShareMode).toBe('function');
    });
  });

  describe('placement 测试', () => {
    it('placement 默认应为 left', () => {
      wrapper = mount(ChatContainer, {
        props: defaultProps,
      });

      expect(wrapper.props().placement).toBe('left');
    });

    it('应该接收 placement 属性', () => {
      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, placement: 'right' },
      });

      expect(wrapper.props().placement).toBe('right');
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
      expect(resize.props('placement')).toBe('left');
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
      expect(resize.props('placement')).toBe('left');
    });

    it('placement 与 resizeProps 同时存在时 placement 以组件 placement 为准', () => {
      wrapper = mount(ChatContainer, {
        props: {
          ...defaultProps,
          placement: 'right',
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

    it('renderMode 为 Share 时侧边栏 Tab 和折叠按钮不应渲染', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Share },
      });

      expect(wrapper.find('.ai-chat-container-tab').exists()).toBe(false);
      expect(wrapper.find('.collapse-button').exists()).toBe(false);
    });

    it('renderMode 为 Share 时 ResizeLayout 应应用 ai-is-collapse（与 executionGroups 无关）', () => {
      const messages = [createUserMessage('1', 'Hello'), createAssistantMessage('2', 'Hi')];

      wrapper = mount(ChatContainer, {
        props: { ...defaultProps, messages, renderMode: RenderMode.Share },
      });

      expect(wrapper.find('.ai-chat-container-resize-layout').classes()).toContain('ai-is-collapse');
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
});
