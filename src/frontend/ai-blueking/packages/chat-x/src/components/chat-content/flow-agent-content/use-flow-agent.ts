/* eslint-disable @typescript-eslint/consistent-type-assertions */
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

import { type ComputedRef, type Ref, type VNode, computed, shallowRef } from 'vue';

import { formatElapsedTime } from '../../../utils/utils';
import { type ConvergedState, getConvergedState, getStateDotColor, getStateIcon, STATE_DEFS } from './flow-agent-state';

import type { BkFlowMessageContent, BkFlowNode, BkFlowTask } from '../../../ag-ui/types/contents';

/** 节点视图模型：模板直接消费，避免重复 Object.values / 状态归一 / 时间格式化 */
export interface FlowNodeVM {
  convergedState: ConvergedState;
  dotColor: string;
  elapsedTimeText: string;
  id: string;
  name: string;
  raw: BkFlowNode;
  /** 是否可重试（失败节点行尾「重试」按钮的显隐依据） */
  retryable: boolean;
  /** 是否可跳过（失败节点行尾「跳过」按钮的显隐依据） */
  skippable: boolean;
}

/** 统计概览项视图模型 */
export interface FlowStatVM {
  /** 计数文字色 */
  color: string;
  display: string;
  /** 状态圆点（环）边框色，pending 等需与文字色区分时回退到独立 dotColor */
  dotColor: string;
  key: ConvergedState;
  label: string;
}

/** 任务视图模型 */
export interface FlowTaskVM {
  confidenceTitle?: string;
  convergedState: ConvergedState;
  hasConfidence: boolean;
  isActive: boolean;
  nodes: FlowNodeVM[];
  raw: BkFlowTask;
  stateIcon: null | VNode;
  taskId: number;
  taskName: string;
  totalTimeText: string;
}

/**
 * flow-agent 视图模型 composable。
 * 将原始 BkFlowTask[] 转换为模板友好的视图模型，并集中处理统计聚合与展开态，
 * 纯派生逻辑（不依赖注入），便于复用与单测。
 */
export const useFlowAgent = (contentRef: Ref<BkFlowMessageContent | undefined>) => {
  const taskList = computed<BkFlowTask[]>(() =>
    Array.isArray(contentRef.value) ? contentRef.value : [contentRef.value ?? ({} as BkFlowTask)],
  );

  /** task_id -> 是否展开；缺省视为展开 */
  const taskExpandedMap = shallowRef<Record<number, boolean>>({});
  const isTaskExpanded = (task: BkFlowTask) => taskExpandedMap.value[task.task_id] !== false;
  const toggleTaskExpanded = (task: BkFlowTask) => {
    taskExpandedMap.value = {
      ...taskExpandedMap.value,
      [task.task_id]: !isTaskExpanded(task),
    };
  };

  const viewTasks: ComputedRef<FlowTaskVM[]> = computed(() =>
    taskList.value.map(task => {
      const nodes: FlowNodeVM[] = Object.values(task.nodes ?? {}).map(node => {
        const convergedState = getConvergedState(node.state);
        return {
          convergedState,
          dotColor: getStateDotColor(convergedState),
          elapsedTimeText: formatElapsedTime(node.elapsed_time),
          id: node.id,
          name: node.name,
          raw: node,
          retryable: Boolean(node.retryable),
          skippable: Boolean(node.skippable),
        };
      });
      const totalElapsed = nodes.reduce((sum, node) => sum + node.raw.elapsed_time, 0);
      const convergedState = getConvergedState(task.task_state ?? '');
      return {
        convergedState,
        hasConfidence: Boolean(task.has_confidence),
        confidenceTitle: task.confidence_title,
        isActive: Boolean(task.is_active),
        nodes,
        raw: task,
        stateIcon: getStateIcon(convergedState),
        taskId: task.task_id,
        taskName: task.task_name,
        totalTimeText: formatElapsedTime(totalElapsed),
      };
    }),
  );

  const visibleStats: ComputedRef<FlowStatVM[]> = computed(() => {
    const aggregated = {} as Record<ConvergedState, number>;
    for (const def of STATE_DEFS) {
      aggregated[def.key] = 0;
    }
    for (const task of taskList.value) {
      for (const [state, count] of Object.entries(task.statistics?.state_counts ?? {})) {
        aggregated[getConvergedState(state)] += count;
      }
    }
    return STATE_DEFS.filter(def => aggregated[def.key] > 0).map(def => ({
      color: def.color,
      display: aggregated[def.key] > 99 ? '99+' : String(aggregated[def.key]),
      dotColor: getStateDotColor(def.key),
      key: def.key,
      label: def.label,
    }));
  });

  return {
    isTaskExpanded,
    taskList,
    toggleTaskExpanded,
    viewTasks,
    visibleStats,
  };
};
