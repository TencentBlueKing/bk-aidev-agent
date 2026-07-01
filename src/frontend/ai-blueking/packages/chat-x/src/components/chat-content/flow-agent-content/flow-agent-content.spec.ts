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
import { defineComponent, h, nextTick } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
import { RenderMode } from '../../../common/constants';
import { useRenderModeProvider } from '../../../composables/use-common';
import FlowAgentContent from './flow-agent-content.vue';

import type { BkFlowMessageContent, BkFlowTask } from '../../../ag-ui/types/contents';

/** v-show 折叠后 happy-dom 下 isVisible() 仍为 true，改断言 style.display */
const expectTaskNodesCollapsed = (wrapper: VueWrapper, index: number) => {
  const el = wrapper.findAll('.flow-agent-task-nodes')[index].element as HTMLElement;
  expect(el.style.display).toBe('none');
};

const expectTaskNodesExpanded = (wrapper: VueWrapper, index: number) => {
  const el = wrapper.findAll('.flow-agent-task-nodes')[index].element as HTMLElement;
  expect(el.style.display).not.toBe('none');
};

const { mockAddCustomTab, mockRemoveCustomTab, mockScrollRef, mockSelectedTab } = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { ref } = require('vue');
  return {
    mockAddCustomTab: vi.fn(),
    mockRemoveCustomTab: vi.fn(),
    mockScrollRef: ref({ autoScrollEnabled: true }),
    mockSelectedTab: ref<undefined | { name?: string }>(undefined),
  };
});

vi.mock('bkui-vue', () => ({
  Loading: defineComponent({
    name: 'MockLoading',
    props: {
      mode: { type: String, default: '' },
      size: { type: String, default: '' },
      theme: { type: String, default: '' },
    },
    setup() {
      return () => h('span', { class: 'mock-bk-loading' });
    },
  }),
}));

vi.mock('../../../ag-ui/types/constants', () => ({
  MessageContentType: {
    FlowAgent: 'flow_agent',
  },
  MessageStatus: {
    Complete: 'complete',
    Disabled: 'disabled',
    Pending: 'pending',
    Streaming: 'streaming',
    Success: 'success',
  },
}));

// use-flow-tab 从 composables 桶导出消费 useCustomTabConsumer / useContainerScrollConsumer / DEFAULT_TAB_ORDER
vi.mock('../../../composables', () => ({
  DEFAULT_TAB_ORDER: 100,
  useContainerScrollConsumer: () => mockScrollRef,
  useCustomTabConsumer: () => ({
    addCustomTab: mockAddCustomTab,
    removeCustomTab: mockRemoveCustomTab,
    selectedTab: mockSelectedTab,
  }),
}));

// 与业务侧 icons 一致：导出为 VNode，供 cloneVNode / 模板使用
vi.mock('../../../icons', () => ({
  ArrowRightIcon: h('span', { class: 'mock-arrow-right' }),
  BkFlowFailedIcon: h('span', { class: 'mock-bkflow-failed' }),
  BkFlowPendingIcon: h('span', { class: 'mock-bkflow-pending' }),
  BkFlowSkippedIcon: h('span', { class: 'mock-bkflow-skipped' }),
  BkFlowSuccessIcon: h('span', { class: 'mock-bkflow-success' }),
  BkFlowSuspendedIcon: h('span', { class: 'mock-bkflow-suspended' }),
  NodeOutputIcon: h('span', { class: 'mock-node-output' }),
  RebuildIcon: h('span', { class: 'mock-rebuild' }),
  SkipIcon: h('span', { class: 'mock-skip' }),
}));

// Mock tippy 样式与 vue-tippy：将 default / content 插槽同步渲染，便于断言 tooltip 内容
vi.mock('tippy.js/dist/tippy.css', () => ({}));
vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'MockTippy',
    props: {
      arrow: { type: Boolean, default: false },
      placement: { type: String, default: '' },
      tag: { type: String, default: 'span' },
      theme: { type: String, default: '' },
    },
    setup(props, { slots }) {
      return () => h(props.tag, { class: 'mock-tippy' }, [slots.default?.(), slots.content?.()]);
    },
  }),
  // v-tippy 指令：测试中为无操作，避免真实 tippy 依赖
  directive: {},
}));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../ai-loading/ai-loading.vue', () => ({
  default: defineComponent({
    name: 'AiLoading',
    props: { size: { type: Number, default: 12 } },
    setup() {
      return () => h('span', { class: 'mock-ai-loading' });
    },
  }),
}));

vi.mock('../../highlight-keyword/highlight-keyword', () => ({
  default: defineComponent({
    name: 'HighlightKeyword',
    props: { text: { type: String, default: '' } },
    setup(props) {
      return () => h('span', { class: 'mock-highlight-keyword' }, props.text);
    },
  }),
}));

vi.mock('../activity-layout/activity-layout.vue', () => ({
  default: defineComponent({
    name: 'ActivityLayout',
    props: {
      activityType: { type: String, default: '' },
      collapsed: { type: Boolean, default: false },
    },
    emits: ['update:collapsed'],
    setup(_, { slots }) {
      return () =>
        h('div', { class: 'mock-activity-layout' }, [
          h('div', { class: 'mock-activity-title' }, slots.title?.()),
          h('div', { class: 'mock-activity-body' }, slots.default?.()),
        ]);
    },
  }),
}));

vi.mock('./flow-agent-node-detail.vue', () => ({
  default: defineComponent({
    name: 'BkFlowNodeDetail',
    setup() {
      return () => h('div', { class: 'mock-flow-agent-node-detail' });
    },
  }),
}));

const createNode = (overrides: Partial<BkFlowTask['nodes'][string]> = {}) => ({
  elapsed_time: 3,
  finish_time: '',
  id: 'n1',
  loop: 0,
  name: '节点一',
  retry: 0,
  skip: false,
  start_time: '',
  state: 'FINISHED',
  type: 'task',
  ...overrides,
});

const createTask = (overrides: Partial<BkFlowTask> = {}): BkFlowTask => ({
  nodes: {
    n1: createNode({ id: 'n1', name: '节点一' }),
    n2: createNode({ id: 'n2', name: '节点二', state: 'RUNNING', elapsed_time: 1 }),
  },
  statistics: {
    state_counts: { FINISHED: 2, RUNNING: 1 },
    total: 3,
  },
  task_id: 100,
  task_name: '测试任务',
  task_outputs: { key: 'value' },
  task_state: 'FINISHED',
  ...overrides,
});

const createContent = (overrides: Partial<BkFlowTask> = {}): BkFlowMessageContent => [createTask(overrides)];

describe('FlowAgentContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
    mockScrollRef.value = { autoScrollEnabled: true };
    mockSelectedTab.value = undefined;
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent(),
        },
      });

      expect(wrapper.find('.mock-activity-layout').exists()).toBe(true);
      expect(wrapper.find('.flow-agent-activity').exists()).toBe(true);
    });
  });

  describe('统计数据展示', () => {
    it('应根据 statistics.state_counts 展示非零统计项', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            statistics: {
              state_counts: { FINISHED: 2, RUNNING: 1 },
              total: 3,
            },
          }),
        },
      });

      // 条内只展示图标 + 计数；文字标签下沉到 hover tooltip
      const barText = wrapper.find('.ai-activity-message-title-text').text();
      expect(barText).toContain('执行情况');
      const barCounts = wrapper.findAll('.flow-agent-stat-count').map(item => item.text());
      expect(barCounts).toContain('2');
      expect(barCounts).toContain('1');

      const tooltipText = wrapper.find('.flow-agent-stat-tooltip').text();
      expect(tooltipText).toContain('成功');
      expect(tooltipText).toContain('执行中');
    });

    it('应汇总多个任务的 statistics.state_counts', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: [
            createTask({
              statistics: {
                state_counts: { FINISHED: 2 },
                total: 2,
              },
            }),
            createTask({
              task_id: 101,
              statistics: {
                state_counts: { RUNNING: 2, FAILED: 1 },
                total: 3,
              },
            }),
          ],
        },
      });

      const tooltipText = wrapper.find('.flow-agent-stat-tooltip').text();
      expect(tooltipText).toContain('成功');
      expect(tooltipText).toContain('执行中');
      expect(tooltipText).toContain('失败');
      expect(tooltipText).toContain('2');
      expect(tooltipText).toContain('1');
    });

    it('应正确展示待执行状态的统计', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            statistics: {
              state_counts: { FINISHED: 1, PENDING: 2 },
              total: 3,
            },
          }),
        },
      });

      const tooltipText = wrapper.find('.flow-agent-stat-tooltip').text();
      expect(tooltipText).toContain('待执行');
      expect(tooltipText).toContain('2');
    });

    it('应展示跳过状态的统计', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            statistics: {
              state_counts: { FINISHED: 1, SKIPPED: 3 },
              total: 4,
            },
          }),
        },
      });

      const tooltipText = wrapper.find('.flow-agent-stat-tooltip').text();
      expect(tooltipText).toContain('跳过');
      expect(tooltipText).toContain('3');
    });

    it('待执行统计数字应使用主题灰 #4D4F56', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            statistics: {
              state_counts: { PENDING: 1 },
              total: 1,
            },
          }),
        },
      });

      const pendingItem = wrapper.findAll('.flow-agent-stat-tooltip-item').find(item => item.text().includes('待执行'));
      const count = pendingItem?.find('.flow-agent-stat-tooltip-count');
      expect(count?.attributes('style')).toContain('#4D4F56');
    });
  });

  describe('节点列表', () => {
    it('应渲染节点列表项', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent(),
        },
      });

      const items = wrapper.findAll('.flow-agent-node-item');
      expect(items.length).toBe(2);
      expect(wrapper.text()).toContain('节点一');
      expect(wrapper.text()).toContain('节点二');
    });

    it('应渲染多个任务及各自节点', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: [
            createTask(),
            createTask({
              task_id: 101,
              task_name: '第二任务',
              nodes: {
                n3: createNode({ id: 'n3', name: '节点三', state: 'PENDING' }),
              },
              statistics: {
                state_counts: { PENDING: 1 },
                total: 1,
              },
            }),
          ],
        },
      });

      expect(wrapper.findAll('.flow-agent-task-group').length).toBe(2);
      expect(wrapper.findAll('.flow-agent-node-item').length).toBe(3);
      expect(wrapper.text()).toContain('测试任务');
      expect(wrapper.text()).toContain('第二任务');
      expect(wrapper.text()).toContain('节点三');
    });

    it('点击任务箭头应只折叠当前任务节点列表', async () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: [
            createTask(),
            createTask({
              task_id: 101,
              task_name: '第二任务',
              nodes: {
                n3: createNode({ id: 'n3', name: '节点三' }),
              },
            }),
          ],
        },
      });

      const arrows = wrapper.findAll('.flow-agent-task-arrow');
      await arrows[0].trigger('click');
      await nextTick();

      expectTaskNodesCollapsed(wrapper, 0);
      expectTaskNodesExpanded(wrapper, 1);

      await arrows[0].trigger('click');
      await nextTick();

      expectTaskNodesExpanded(wrapper, 0);
    });

    it('renderMode 为 Share 时应保留节点耗时与详情查看入口，但隐藏重试/跳过', () => {
      const Parent = defineComponent({
        setup() {
          useRenderModeProvider({ renderMode: RenderMode.Share });
          return () =>
            h(FlowAgentContent, {
              // 失败可重试/可跳过节点：非分享态会出现重试/跳过，用于验证分享态被过滤
              content: createContent({
                nodes: {
                  n1: createNode({ id: 'n1', name: '失败节点', state: 'FAILED', retryable: true, skippable: true }),
                },
              }),
            });
        },
      });

      wrapper = mount(Parent);

      // 只读查看入口保留：行尾容器、耗时、详情按钮
      expect(wrapper.find('.flow-agent-node-trailing').exists()).toBe(true);
      expect(wrapper.find('.flow-agent-node-time').exists()).toBe(true);
      const actionTexts = wrapper.findAll('.flow-agent-node-action-btn').map(btn => btn.text());
      expect(actionTexts).toContain('详情');
      // 交互式 resume 操作被过滤
      expect(actionTexts).not.toContain('重试');
      expect(actionTexts).not.toContain('跳过');
    });

    it('renderMode 为 Share 时应保留任务耗时与有效证据查看入口', () => {
      const Parent = defineComponent({
        setup() {
          useRenderModeProvider({ renderMode: RenderMode.Share });
          return () =>
            h(FlowAgentContent, {
              content: createContent({ has_confidence: true }),
            });
        },
      });

      wrapper = mount(Parent);

      expect(wrapper.find('.flow-agent-task-trailing').exists()).toBe(true);
      expect(wrapper.find('.flow-agent-task-time').exists()).toBe(true);
      expect(wrapper.find('.flow-agent-task-confidence-btn').exists()).toBe(true);
    });
  });

  describe('有效证据', () => {
    it('has_confidence 为 true 时应展示有效证据按钮', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({ has_confidence: true }),
        },
      });

      expect(wrapper.find('.flow-agent-task-confidence-btn').exists()).toBe(true);
      expect(wrapper.text()).toContain('有效证据');
    });

    it('has_confidence 为 true 时任务头应带 has-confidence 类', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({ has_confidence: true }),
        },
      });

      expect(wrapper.find('.flow-agent-task-header').classes()).toContain('has-confidence');
    });

    it('点击有效证据应打开带 has_confidence 的自定义 Tab', async () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({ has_confidence: true }),
        },
      });

      await wrapper.find('.flow-agent-task-confidence-btn').trigger('click');

      expect(mockAddCustomTab).toHaveBeenCalled();
      const payload = mockAddCustomTab.mock.calls.at(-1)?.[0] as {
        data?: { props?: { has_confidence?: boolean; task_id?: number } };
        label?: string;
        name?: string;
      };
      expect(payload?.label).toBe('有效证据');
      expect(payload?.name).toBe('100');
      expect(payload?.data?.props?.has_confidence).toBe(true);
      expect(payload?.data?.props?.task_id).toBe(100);
    });
  });

  describe('任务选中态', () => {
    it('未手动选 Tab 时 is_active 任务应带 is-selected 类', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({ is_active: true }),
        },
      });

      expect(wrapper.find('.flow-agent-task-header').classes()).toContain('is-selected');
    });

    it('is_active 且 has_confidence 为 true 时应在挂载后自动打开有效证据 Tab', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            is_active: true,
            has_confidence: true,
          }),
        },
      });

      expect(mockAddCustomTab).toHaveBeenCalled();
      const payload = mockAddCustomTab.mock.calls[0]?.[0] as {
        data?: { props?: { has_confidence?: boolean; task_id?: number } };
        label?: string;
        name?: string;
      };
      expect(payload?.label).toBe('有效证据');
      expect(payload?.name).toBe('100');
      expect(payload?.data?.props?.has_confidence).toBe(true);
      expect(payload?.data?.props?.task_id).toBe(100);
    });

    it('无消息容器滚动上下文时不应自动打开有效证据 Tab', () => {
      mockScrollRef.value = undefined as unknown as { autoScrollEnabled: boolean };
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            is_active: true,
            has_confidence: true,
          }),
        },
      });

      expect(mockAddCustomTab).not.toHaveBeenCalled();
    });
  });

  describe('task_outputs', () => {
    // 与模板一致：任务输出展示区块已注释，不在 DOM 中渲染
    it('不应渲染 .flow-agent-task-outputs', () => {
      const outputs = { result: 'ok', n: 1 };
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({ task_outputs: outputs }),
        },
      });

      expect(wrapper.find('.flow-agent-task-outputs').exists()).toBe(false);
    });
  });

  describe('生命周期与自定义 Tab', () => {
    it('存在消息容器滚动上下文时卸载应移除各节点详情 Tab', () => {
      mockScrollRef.value = { autoScrollEnabled: true };
      wrapper = mount(FlowAgentContent, {
        props: {
          content: [
            createTask(),
            createTask({
              task_id: 101,
              task_name: '第二任务',
              nodes: {
                n3: createNode({ id: 'n3', name: '节点三' }),
              },
            }),
          ],
        },
      });

      wrapper.unmount();

      expect(mockRemoveCustomTab).toHaveBeenCalledWith('100');
      expect(mockRemoveCustomTab).toHaveBeenCalledWith('101');
      expect(mockRemoveCustomTab).toHaveBeenCalledWith('100|n1|节点一');
      expect(mockRemoveCustomTab).toHaveBeenCalledWith('100|n2|节点二');
      expect(mockRemoveCustomTab).toHaveBeenCalledWith('101|n3|节点三');
    });

    it('无滚动上下文时卸载不应调用 removeCustomTab', () => {
      mockScrollRef.value = undefined as unknown as { autoScrollEnabled: boolean };
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent(),
        },
      });

      wrapper.unmount();

      expect(mockRemoveCustomTab).not.toHaveBeenCalled();
    });

    it('失败节点可重试/可跳过时应展示重试与跳过按钮', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            nodes: {
              n1: createNode({
                id: 'n1',
                name: '失败节点',
                state: 'FAILED',
                retryable: true,
                skippable: true,
              }),
            },
          }),
        },
      });

      const actionTexts = wrapper.findAll('.flow-agent-node-action-btn').map(btn => btn.text());
      expect(actionTexts).toContain('重试');
      expect(actionTexts).toContain('跳过');
      expect(actionTexts).toContain('详情');
    });

    it('失败节点不可重试/不可跳过时不应展示重试与跳过按钮', () => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            nodes: {
              n1: createNode({
                id: 'n1',
                name: '失败节点',
                state: 'FAILED',
                retryable: false,
                skippable: false,
              }),
            },
          }),
        },
      });

      const actionTexts = wrapper.findAll('.flow-agent-node-action-btn').map(btn => btn.text());
      expect(actionTexts).not.toContain('重试');
      expect(actionTexts).not.toContain('跳过');
      expect(actionTexts).toContain('详情');
    });

    it('点击重试应通过 onInterruptResume 回传 flow_node_retry', async () => {
      const onInterruptResume = vi.fn();
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            nodes: {
              n1: createNode({
                id: 'n1',
                name: '失败节点',
                state: 'FAILED',
                retryable: true,
              }),
            },
          }),
          onInterruptResume,
        },
      });

      const retryBtn = wrapper.findAll('.flow-agent-node-action-btn').find(btn => btn.text().includes('重试'));
      expect(retryBtn).toBeTruthy();
      await retryBtn?.trigger('click');

      expect(onInterruptResume).toHaveBeenCalledWith({
        operation: InterruptResumeOperation.FlowNodeRetry,
        payload: { node_id: 'n1', task_id: 100 },
      });
      expect(onInterruptResume.mock.calls[0]).toHaveLength(1);
    });

    it('点击跳过应通过 onInterruptResume 回传 flow_node_skip', async () => {
      const onInterruptResume = vi.fn();
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            nodes: {
              n1: createNode({
                id: 'n1',
                name: '失败节点',
                state: 'FAILED',
                skippable: true,
              }),
            },
          }),
          onInterruptResume,
        },
      });

      const skipBtn = wrapper.findAll('.flow-agent-node-action-btn').find(btn => btn.text().includes('跳过'));
      expect(skipBtn).toBeTruthy();
      await skipBtn?.trigger('click');

      expect(onInterruptResume).toHaveBeenCalledWith({
        operation: InterruptResumeOperation.FlowNodeSkip,
        payload: { node_id: 'n1', task_id: 100 },
      });
      expect(onInterruptResume.mock.calls[0]).toHaveLength(1);
    });

    it('打开节点详情时应将 messageUid 传入自定义 Tab 的 data', async () => {
      const messageUid = 'flow-msg-uid-1';
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent(),
          messageUid,
        },
      });

      const detailBtn = wrapper.findAll('.flow-agent-node-action-btn').find(btn => btn.text().includes('详情'));
      expect(detailBtn).toBeTruthy();
      await detailBtn?.trigger('click');

      expect(mockAddCustomTab).toHaveBeenCalled();
      const payload = mockAddCustomTab.mock.calls[0]?.[0] as { data?: { messageUid?: string } };
      expect(payload?.data?.messageUid).toBe(messageUid);
    });
  });

  describe('重试/跳过 pending 交互', () => {
    const mountFailedNode = (onInterruptResume = vi.fn()) => {
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent({
            nodes: {
              n1: createNode({
                id: 'n1',
                name: '失败节点',
                state: 'FAILED',
                retryable: true,
                skippable: true,
              }),
            },
          }),
          onInterruptResume,
        },
      });
      return onInterruptResume;
    };

    const findBtn = (text: string) =>
      wrapper.findAll('.flow-agent-node-action-btn').find(btn => btn.text().includes(text));

    it('点击重试后：节点行进入 pending 态，重试变 loading+重试中，重试/跳过均禁用', async () => {
      mountFailedNode();

      await findBtn('重试')?.trigger('click');

      expect(wrapper.find('.flow-agent-node-item').classes()).toContain('is-pending');

      const retryBtn = findBtn('重试中');
      expect(retryBtn).toBeTruthy();
      expect(retryBtn?.find('.mock-bk-loading').exists()).toBe(true);
      expect(retryBtn?.classes()).toContain('is-disabled');

      const skipBtn = findBtn('跳过');
      expect(skipBtn?.classes()).toContain('is-disabled');
    });

    it('pending 态下再次点击重试或点击被禁用的跳过不应重复回传', async () => {
      const onInterruptResume = mountFailedNode();

      await findBtn('重试')?.trigger('click');
      await findBtn('重试中')?.trigger('click');
      await findBtn('跳过')?.trigger('click');

      expect(onInterruptResume).toHaveBeenCalledTimes(1);
      expect(onInterruptResume).toHaveBeenCalledWith({
        operation: InterruptResumeOperation.FlowNodeRetry,
        payload: { node_id: 'n1', task_id: 100 },
      });
    });

    it('点击跳过后：跳过变 loading+跳过中，重试/跳过均禁用', async () => {
      mountFailedNode();

      await findBtn('跳过')?.trigger('click');

      const skipBtn = findBtn('跳过中');
      expect(skipBtn).toBeTruthy();
      expect(skipBtn?.find('.mock-bk-loading').exists()).toBe(true);
      expect(skipBtn?.classes()).toContain('is-disabled');
      expect(findBtn('重试')?.classes()).toContain('is-disabled');
    });
  });
});
