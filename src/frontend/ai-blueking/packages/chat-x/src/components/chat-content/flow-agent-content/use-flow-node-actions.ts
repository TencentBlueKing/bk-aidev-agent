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

import type { Component, Ref } from 'vue';

import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
// TODO: 重试 / 跳过 图标暂复用 CopyIcon，待设计补充专用图标后替换
import { NodeOutputIcon, RebuildIcon, SkipIcon } from '../../../icons';
import { t } from '../../../lang/lang';

import type { BkFlowNode, BkFlowTask } from '../../../ag-ui/types/contents';
import type { FlowNodeResume, OnInterruptResume } from '../../../ag-ui/types/interrupt';
import type { FlowNodeVM, FlowTaskVM } from './use-flow-agent';

/** 节点行尾操作类型标识 */
export type FlowNodeActionId =
  | 'detail'
  | InterruptResumeOperation.FlowNodeRetry
  | InterruptResumeOperation.FlowNodeSkip;

/** 节点行尾操作视图模型：详情 / 重试 / 跳过统一为同一渲染单元（图标 + 文案 + 点击） */
export interface FlowNodeActionVM {
  /** 按钮图标组件 */
  icon: Component;
  /** 唯一标识，用于 v-for key 与样式钩子 */
  id: FlowNodeActionId;
  /** 国际化文案 */
  label: string;
  /** 点击执行 */
  run: () => void;
}

/**
 * 单条 resume 操作定义：声明「何时可见 + 用哪个操作枚举」，便于后续扩展更多节点动作。
 * 可见性默认要求节点处于失败态（设计稿：重试 / 跳过仅在失败节点出现），
 * 并叠加节点自身的能力位（retryable / skippable）。
 */
interface FlowNodeResumeActionDef {
  icon: Component;
  id: InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;
  label: () => string;
  /** 该操作是否对当前节点可见 */
  visible: (node: FlowNodeVM) => boolean;
}

/**
 * 失败节点上的 resume 操作注册表（顺序即展示顺序：重试 → 跳过）。
 * 新增节点级 resume 操作只需在此追加一项。
 */
const RESUME_ACTION_DEFS: FlowNodeResumeActionDef[] = [
  {
    icon: RebuildIcon,
    id: InterruptResumeOperation.FlowNodeRetry,
    label: () => t('重试'),
    visible: node => node.convergedState === 'failed' && node.retryable,
  },
  {
    icon: SkipIcon,
    id: InterruptResumeOperation.FlowNodeSkip,
    label: () => t('跳过'),
    visible: node => node.convergedState === 'failed' && node.skippable,
  },
];

/**
 * flow-agent 节点行尾操作 composable。
 *
 * 将「详情（打开侧栏）」与「重试 / 跳过（回传 Agent resume）」聚合为统一的、声明式的
 * 操作列表，组件层只需遍历渲染，显隐与点击行为均收敛于此，便于复用、单测与扩展。
 */
export const useFlowNodeActions = (options: {
  /** resume 回调（与第三方审批取消同一回调，按 payload.operation 分流） */
  onInterruptResume: Ref<OnInterruptResume | undefined>;
  /** 打开节点详情侧栏（复用 useFlowTab 的能力） */
  openNodeDetail: (task: BkFlowTask, node: BkFlowNode) => void;
}) => {
  const { onInterruptResume, openNodeDetail } = options;

  /** 触发 resume 回调；流程节点无 interrupt，定位信息随 payload 回传 */
  const resume = (operation: FlowNodeResume['operation'], task: BkFlowTask, node: BkFlowNode) => {
    onInterruptResume.value?.({ payload: { node_id: node.id, task_id: task.task_id }, operation });
  };

  /** 计算单个节点行尾应展示的操作列表（重试 / 跳过按需，详情恒在末尾） */
  const getNodeActions = (task: FlowTaskVM, node: FlowNodeVM): FlowNodeActionVM[] => {
    const actions: FlowNodeActionVM[] = RESUME_ACTION_DEFS.filter(def => def.visible(node)).map(def => ({
      icon: def.icon,
      id: def.id,
      label: def.label(),
      run: () => resume(def.id, task.raw, node.raw),
    }));
    actions.push({
      icon: NodeOutputIcon,
      id: 'detail',
      label: t('详情'),
      run: () => openNodeDetail(task.raw, node.raw),
    });
    return actions;
  };

  return { getNodeActions };
};
