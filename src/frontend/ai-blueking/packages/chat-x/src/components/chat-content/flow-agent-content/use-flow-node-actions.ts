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

import { type Ref, shallowRef } from 'vue';
import type { Component } from 'vue';

import { InterruptResumeOperation } from '../../../ag-ui/types/interrupt';
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
  /** 是否禁用点击（任一 resume 操作进行中时，重试 / 跳过均禁用） */
  disabled: boolean;
  /** 按钮图标组件 */
  icon: Component;
  /** 唯一标识，用于 v-for key 与样式钩子 */
  id: FlowNodeActionId;
  /** 国际化文案（进行中时切换为「重试中 / 跳过中」） */
  label: string;
  /** 是否处于进行中态：图标切换为 loading，文案切换为进行中文案 */
  loading: boolean;
  /** 因另一操作进行中而禁用时的 hover 提示（设计稿 annotation） */
  tooltip?: string;
  /** 点击执行 */
  run: () => void;
}

/** 节点级 resume 进行中操作（重试 / 跳过其一） */
type FlowNodePendingOp = InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;

/**
 * 单条 resume 操作定义：声明「何时可见 + 用哪个操作枚举」，便于后续扩展更多节点动作。
 * 可见性默认要求节点处于失败态（设计稿：重试 / 跳过仅在失败节点出现），
 * 并叠加节点自身的能力位（retryable / skippable）。
 */
interface FlowNodeResumeActionDef {
  icon: Component;
  id: FlowNodePendingOp;
  /** 被另一操作阻塞（禁用）时的 hover 提示；文案描述「正在进行的那个操作」 */
  blockedTip: () => string;
  label: () => string;
  /** 本操作进行中时的文案（重试中 / 跳过中） */
  pendingLabel: () => string;
  /** 该操作是否对当前节点可见 */
  visible: (node: FlowNodeVM) => boolean;
}

/**
 * 失败节点上的 resume 操作注册表（顺序即展示顺序：重试 → 跳过）。
 * 新增节点级 resume 操作只需在此追加一项。
 */
const RESUME_ACTION_DEFS: FlowNodeResumeActionDef[] = [
  {
    // 重试被跳过阻塞时的提示
    blockedTip: () => t('任务正在跳过中，不可重试'),
    icon: RebuildIcon,
    id: InterruptResumeOperation.FlowNodeRetry,
    label: () => t('重试'),
    pendingLabel: () => t('重试中'),
    visible: node => node.convergedState === 'failed' && node.retryable,
  },
  {
    // 跳过被重试阻塞时的提示
    blockedTip: () => t('任务正在重试中，不可跳过'),
    icon: SkipIcon,
    id: InterruptResumeOperation.FlowNodeSkip,
    label: () => t('跳过'),
    pendingLabel: () => t('跳过中'),
    visible: node => node.convergedState === 'failed' && node.skippable,
  },
];

/**
 * 节点 pending 键：`task_id:node_id:retry`。
 * 携带 retry 计数——重试再次失败（retry 计数 +1）会生成新键，pending 自动失效、
 * 按钮重新可用；无需手动清理，天然随后端状态更新收敛。
 */
const nodePendingKey = (task: BkFlowTask, node: BkFlowNode) => `${task.task_id}:${node.id}:${node.retry}`;

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

  /** node 键 -> 进行中的 resume 操作；点击后写入，收到后端新状态（键变化）后自动失效 */
  const pendingMap = shallowRef<Record<string, FlowNodePendingOp>>({});

  /** 触发 resume 回调；先置 pending 防重复点击，流程节点无 interrupt，定位信息随 payload 回传 */
  const resume = (operation: FlowNodeResume['operation'], task: BkFlowTask, node: BkFlowNode) => {
    const key = nodePendingKey(task, node);
    // 已有进行中操作则忽略（重试 / 跳过点击后二者均禁用，防重复提交）
    if (pendingMap.value[key]) {
      return;
    }
    pendingMap.value = { ...pendingMap.value, [key]: operation };
    onInterruptResume.value?.({ payload: { node_id: node.id, task_id: task.task_id }, operation });
  };

  /** 当前节点是否有进行中的 resume 操作（供视图层常驻显示按钮组） */
  const isNodePending = (task: FlowTaskVM, node: FlowNodeVM): boolean =>
    pendingMap.value[nodePendingKey(task.raw, node.raw)] !== undefined;

  /** 计算单个节点行尾应展示的操作列表（重试 / 跳过按需，详情恒在末尾） */
  const getNodeActions = (task: FlowTaskVM, node: FlowNodeVM): FlowNodeActionVM[] => {
    const pendingOp = pendingMap.value[nodePendingKey(task.raw, node.raw)];
    const actions: FlowNodeActionVM[] = RESUME_ACTION_DEFS.filter(def => def.visible(node)).map(def => {
      const isSelfPending = pendingOp === def.id;
      // 另一操作进行中：本按钮禁用并给出 hover 提示
      const isBlockedByOther = pendingOp !== undefined && !isSelfPending;
      return {
        // 任一 resume 操作进行中，重试 / 跳过均禁用
        disabled: pendingOp !== undefined,
        icon: def.icon,
        id: def.id,
        label: isSelfPending ? def.pendingLabel() : def.label(),
        loading: isSelfPending,
        run: () => resume(def.id, task.raw, node.raw),
        tooltip: isBlockedByOther ? def.blockedTip() : undefined,
      };
    });
    actions.push({
      disabled: false,
      icon: NodeOutputIcon,
      id: 'detail',
      label: t('详情'),
      loading: false,
      run: () => openNodeDetail(task.raw, node.raw),
    });
    return actions;
  };

  return { getNodeActions, isNodePending };
};
