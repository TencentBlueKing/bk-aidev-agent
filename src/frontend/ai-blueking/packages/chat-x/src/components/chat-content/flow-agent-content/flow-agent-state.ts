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

import { type VNode, cloneVNode, isVNode } from 'vue';

import {
  BkFlowFailedIcon,
  BkFlowPendingIcon,
  BkFlowSkippedIcon,
  BkFlowSuccessIcon,
  BkFlowSuspendedIcon,
  BkFlowTerminatedIcon,
} from '../../../icons';
import { t } from '../../../lang/lang';

/** 归一后的执行状态 */
export type ConvergedState = 'failed' | 'pending' | 'running' | 'skipped' | 'success' | 'suspended' | 'terminated';

/** 单个归一状态的完整定义 */
export interface FlowStateDef {
  /** 状态主题色，供统计标签文字、整体 header 文案与图标语义复用 */
  color: string;
  /** 节点 / 统计圆点的边框色，缺省回退到 color（仅 pending 与主题色不同） */
  dotColor?: string;
  /** 节点 / 统计圆点的填充色；缺省透明（空心环）。已终止等实心底圆点在此声明 */
  dotFill?: string;
  /**
   * 任一任务 task_state 命中该状态时，标题栏前置该标签并括号包裹统计。
   * 后续若有同类「整体覆盖态」，只需在对应 def 上打开此标记。
   */
  flowHeader?: boolean;
  /** 状态图标（VNode）；running 走 Loading 动画，故为 null */
  icon: null | VNode;
  /** 归一状态标识 */
  key: ConvergedState;
  /** 国际化标签 */
  label: string;
  /** 归一到该状态的后端原始状态枚举 */
  rawStates: string[];
  /** 是否出现在标题栏 / tooltip 统计；缺省 true */
  showInStats?: boolean;
}

/**
 * 执行状态唯一配置源（Single Source of Truth）。
 * 新增 / 调整状态只需维护此处：归一映射、统计标签、颜色、图标、整体 header 覆盖均由它派生，
 * 避免状态逻辑散落在组件与 SCSS 多处。
 * 数组顺序即统计概览（visibleStats）的展示顺序。
 */
export const STATE_DEFS: FlowStateDef[] = [
  {
    color: '#3A84FF',
    icon: null,
    key: 'running',
    label: t('执行中'),
    rawStates: ['CREATED', 'LOOP_READY', 'READY', 'RUNNING', 'BLOCKED', 'ROLLING_BACK', 'ROLL_BACK_SUCCESS'],
  },
  {
    color: '#65C389',
    icon: BkFlowSuccessIcon,
    key: 'success',
    label: t('成功'),
    rawStates: ['FINISHED'],
  },
  {
    color: '#EA3636',
    icon: BkFlowFailedIcon,
    key: 'failed',
    label: t('失败'),
    rawStates: ['FAILED', 'ROLL_BACK_FAILED'],
  },
  {
    color: '#F59500',
    icon: BkFlowSuspendedIcon,
    key: 'suspended',
    label: t('挂起'),
    rawStates: ['SUSPENDED'],
  },
  {
    // 叶子节点 / 统计圆点：浅橙底 + 橙红描边（设计稿 947:13593）；header 文案同色
    color: '#F55B0E',
    dotFill: '#FEE8DD',
    flowHeader: true,
    icon: BkFlowTerminatedIcon,
    key: 'terminated',
    label: t('已终止'),
    rawStates: ['REVOKED'],
  },
  {
    color: '#4D4F56',
    dotColor: '#DCDEE5',
    icon: BkFlowPendingIcon,
    key: 'pending',
    label: t('待执行'),
    rawStates: ['PENDING'],
  },
  {
    color: '#5B7290',
    icon: BkFlowSkippedIcon,
    key: 'skipped',
    label: t('跳过'),
    rawStates: ['SKIPPED'],
  },
];

const STATE_DEF_MAP = Object.fromEntries(STATE_DEFS.map(def => [def.key, def])) as Record<ConvergedState, FlowStateDef>;

/** 后端原始状态 -> 归一状态 的查表 */
const RAW_STATE_TO_CONVERGED = Object.fromEntries(
  STATE_DEFS.flatMap(def => def.rawStates.map(raw => [raw, def.key] as const)),
) as Record<string, ConvergedState>;

/** 后端原始状态归一；未知状态回退 running（保持原有行为） */
export const getConvergedState = (rawState: string): ConvergedState => RAW_STATE_TO_CONVERGED[rawState] ?? 'running';

/**
 * 根据任务原始状态扫描整体 header 覆盖定义。
 * 只遍历 task_state（O(任务数)），命中首个 flowHeader 即返回。
 */
export const getFlowHeaderDef = (rawTaskStates: Iterable<string>): FlowStateDef | undefined => {
  for (const raw of rawTaskStates) {
    const def = STATE_DEF_MAP[getConvergedState(raw)];
    if (def.flowHeader) {
      return def;
    }
  }
  return undefined;
};

/** 是否进入标题栏 / tooltip 统计；未声明时默认展示 */
export const isShownInStats = (def: FlowStateDef): boolean => def.showInStats !== false;

/** 状态主题色（用于统计标签文字） */
export const getStateColor = (state: ConvergedState): string => STATE_DEF_MAP[state].color;

/** 节点 / 统计圆点边框色 */
export const getStateDotColor = (state: ConvergedState): string =>
  STATE_DEF_MAP[state].dotColor ?? STATE_DEF_MAP[state].color;

/** 节点 / 统计圆点填充色；未声明时返回 undefined，保持空心环 */
export const getStateDotFill = (state: ConvergedState): string | undefined => STATE_DEF_MAP[state].dotFill;

/**
 * 深拷贝图标 VNode（含 children），并断开 el / anchor。
 * Vue 的 cloneVNode 是浅拷贝：子 VNode 仍与模块级 h() 源节点共享。
 * 主聊天窗与侧边栏「执行情况」会同时挂载两份 FlowAgentContent，
 * 共享的 path.el 会在 patch 时写到其中一份 DOM，导致另一份状态图标停在旧态。
 */
const cloneIconVNode = (vnode: VNode): VNode => {
  const cloned = cloneVNode(vnode);
  cloned.el = null;
  cloned.anchor = null;
  if (Array.isArray(vnode.children)) {
    cloned.children = vnode.children.map(child => (isVNode(child) ? cloneIconVNode(child) : child));
  }
  return cloned;
};

/** 取状态图标，返回深拷贝的 VNode 以支持多处复用；running 无图标返回 null */
export const getStateIcon = (state: ConvergedState): null | VNode => {
  const icon = STATE_DEF_MAP[state].icon;
  return icon ? cloneIconVNode(icon) : null;
};
