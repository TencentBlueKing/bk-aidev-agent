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
import { defineComponent, h, ref } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
import { useFlowNodeActions } from './use-flow-node-actions';

import type { BkFlowNode, BkFlowTask } from '../../../ag-ui/types/contents';
import type { FlowNodeVM, FlowTaskVM } from './use-flow-agent';

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

vi.mock('../../../icons', () => ({
  NodeOutputIcon: { name: 'NodeOutputIcon' },
  RebuildIcon: { name: 'RebuildIcon' },
  SkipIcon: { name: 'SkipIcon' },
}));

const createRawNode = (overrides: Partial<BkFlowNode> = {}): BkFlowNode => ({
  elapsed_time: 1,
  finish_time: '',
  id: 'n1',
  loop: 0,
  name: '节点一',
  retry: 0,
  skip: false,
  start_time: '',
  state: 'FAILED',
  type: 'task',
  ...overrides,
});

const createRawTask = (overrides: Partial<BkFlowTask> = {}): BkFlowTask => ({
  nodes: { n1: createRawNode() },
  statistics: { state_counts: { FAILED: 1 }, total: 1 },
  task_id: 100,
  task_name: '测试任务',
  task_outputs: {},
  task_state: 'FAILED',
  ...overrides,
});

const createNodeVM = (overrides: Partial<FlowNodeVM> = {}): FlowNodeVM => ({
  convergedState: 'failed',
  dotColor: '#f00',
  elapsedTimeText: '1s',
  id: 'n1',
  name: '节点一',
  raw: createRawNode(),
  retryable: true,
  skippable: true,
  ...overrides,
});

const createTaskVM = (overrides: Partial<FlowTaskVM> = {}): FlowTaskVM =>
  ({
    convergedState: 'failed',
    hasConfidence: false,
    isActive: false,
    nodes: [createNodeVM()],
    raw: createRawTask(),
    stateIcon: null,
    taskId: 100,
    taskName: '测试任务',
    totalTimeText: '1s',
    ...overrides,
  }) as FlowTaskVM;

const mountActions = (options?: {
  node?: Partial<FlowNodeVM>;
  onInterruptResume?: ReturnType<typeof vi.fn>;
}) => {
  const onInterruptResume = options?.onInterruptResume ?? vi.fn();
  const openNodeDetail = vi.fn();
  const actionsRef = ref<ReturnType<typeof useFlowNodeActions>['getNodeActions']>();

  const wrapper = mount(
    defineComponent({
      setup() {
        const { getNodeActions } = useFlowNodeActions({
          onInterruptResume: ref(onInterruptResume),
          openNodeDetail,
        });
        actionsRef.value = getNodeActions;
        return () => h('div');
      },
    }),
  );

  const task = createTaskVM();
  const node = createNodeVM(options?.node);
  const actions = actionsRef.value!(task, node);

  return { wrapper, actions, onInterruptResume, openNodeDetail, task, node };
};

describe('useFlowNodeActions', () => {
  it('失败且可重试/可跳过节点应返回重试、跳过与详情操作', () => {
    const { actions, wrapper } = mountActions();

    expect(actions.map(action => action.id)).toEqual([
      InterruptResumeOperation.FlowNodeRetry,
      InterruptResumeOperation.FlowNodeSkip,
      'detail',
    ]);
    expect(actions.map(action => action.label)).toEqual(['重试', '跳过', '详情']);

    wrapper.unmount();
  });

  it('非失败节点不应展示重试与跳过', () => {
    const { actions, wrapper } = mountActions({
      node: { convergedState: 'success', retryable: true, skippable: true },
    });

    expect(actions.map(action => action.id)).toEqual(['detail']);

    wrapper.unmount();
  });

  it('失败但不可重试/不可跳过时不应展示重试与跳过', () => {
    const { actions, wrapper } = mountActions({
      node: { retryable: false, skippable: false },
    });

    expect(actions.map(action => action.id)).toEqual(['detail']);

    wrapper.unmount();
  });

  it('执行重试操作应调用 onInterruptResume 且不带 interrupt', () => {
    const onInterruptResume = vi.fn();
    const { actions, wrapper } = mountActions({ onInterruptResume });

    actions.find(action => action.id === InterruptResumeOperation.FlowNodeRetry)?.run();

    expect(onInterruptResume).toHaveBeenCalledWith({
      operation: InterruptResumeOperation.FlowNodeRetry,
      payload: { node_id: 'n1', task_id: 100 },
    });
    expect(onInterruptResume.mock.calls[0]).toHaveLength(1);

    wrapper.unmount();
  });

  it('执行跳过操作应调用 onInterruptResume 且不带 interrupt', () => {
    const onInterruptResume = vi.fn();
    const { actions, wrapper } = mountActions({ onInterruptResume });

    actions.find(action => action.id === InterruptResumeOperation.FlowNodeSkip)?.run();

    expect(onInterruptResume).toHaveBeenCalledWith({
      operation: InterruptResumeOperation.FlowNodeSkip,
      payload: { node_id: 'n1', task_id: 100 },
    });
    expect(onInterruptResume.mock.calls[0]).toHaveLength(1);

    wrapper.unmount();
  });

  it('执行详情操作应调用 openNodeDetail', () => {
    const { actions, openNodeDetail, task, node, wrapper } = mountActions();

    actions.find(action => action.id === 'detail')?.run();

    expect(openNodeDetail).toHaveBeenCalledWith(task.raw, node.raw);

    wrapper.unmount();
  });
});
