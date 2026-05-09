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

import { RenderMode } from '../../../common/constants';
import { useRenderModeProvider } from '../../../composables/use-common';
import FlowAgentContent from './flow-agent-content.vue';

import type { BkFlowMessageContent, BkFlowTask } from '../../../ag-ui/types/contents';

const { mockAddCustomTab, mockRemoveCustomTab, mockScrollRef } = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { ref } = require('vue');
  return {
    mockAddCustomTab: vi.fn(),
    mockRemoveCustomTab: vi.fn(),
    mockScrollRef: ref({ autoScrollEnabled: true }),
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
    Pending: 'pending',
    Streaming: 'streaming',
    Success: 'success',
  },
}));

vi.mock('../../../composables', () => ({
  useContainerScrollConsumer: () => mockScrollRef,
}));

vi.mock('../../../composables/use-custom-tab', () => ({
  useCustomTabConsumer: () => ({ addCustomTab: mockAddCustomTab, removeCustomTab: mockRemoveCustomTab }),
}));

// 与业务侧 icons 一致：导出为 VNode，供 cloneVNode / 模板使用
vi.mock('../../../icons', () => ({
  ArrowRightIcon: h('span', { class: 'mock-arrow-right' }),
  BkFlowFailedIcon: h('span', { class: 'mock-bkflow-failed' }),
  BkFlowPendingIcon: h('span', { class: 'mock-bkflow-pending' }),
  BkFlowSuccessIcon: h('span', { class: 'mock-bkflow-success' }),
  BkFlowSuspendedIcon: h('span', { class: 'mock-bkflow-suspended' }),
  NodeOutputIcon: h('span', { class: 'mock-node-output' }),
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

      const text = wrapper.find('.flow-agent-title-label').element.parentElement?.textContent ?? '';
      expect(text).toContain('成功');
      expect(text).toContain('2');
      expect(text).toContain('执行中');
      expect(text).toContain('1');
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

      const text = wrapper.find('.flow-agent-title-label').element.parentElement?.textContent ?? '';
      expect(text).toContain('成功');
      expect(text).toContain('2');
      expect(text).toContain('执行中');
      expect(text).toContain('2');
      expect(text).toContain('失败');
      expect(text).toContain('1');
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

      const text = wrapper.find('.flow-agent-title-label').element.parentElement?.textContent ?? '';
      expect(text).toContain('待执行');
      expect(text).toContain('2');
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

      const pendingItem = wrapper.findAll('.flow-agent-stat-item').find(item => item.text().includes('待执行'));
      const count = pendingItem?.find('.flow-agent-stat-count');
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
      const nodeGroups = wrapper.findAll('.flow-agent-task-nodes');
      await arrows[0].trigger('click');

      expect(nodeGroups[0].isVisible()).toBe(false);
      expect(nodeGroups[1].isVisible()).toBe(true);

      await arrows[0].trigger('click');

      expect(nodeGroups[0].isVisible()).toBe(true);
    });

    it('renderMode 为 Share 时不应渲染节点耗时和详情入口', () => {
      const Parent = defineComponent({
        setup() {
          useRenderModeProvider({ renderMode: RenderMode.Share });
          return () =>
            h(FlowAgentContent, {
              content: createContent(),
            });
        },
      });

      wrapper = mount(Parent);

      expect(wrapper.find('.flow-agent-node-trailing').exists()).toBe(false);
      expect(wrapper.find('.flow-agent-node-time').exists()).toBe(false);
      expect(wrapper.find('.flow-agent-node-detail-btn').exists()).toBe(false);
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

    it('打开节点详情时应将 messageUid 传入自定义 Tab 的 data', async () => {
      const messageUid = 'flow-msg-uid-1';
      wrapper = mount(FlowAgentContent, {
        props: {
          content: createContent(),
          messageUid,
        },
      });

      const detailBtn = wrapper.find('.flow-agent-node-detail-btn');
      await detailBtn.trigger('click');

      expect(mockAddCustomTab).toHaveBeenCalled();
      const payload = mockAddCustomTab.mock.calls[0]?.[0] as { data?: { messageUid?: string } };
      expect(payload?.data?.messageUid).toBe(messageUid);
    });
  });
});
