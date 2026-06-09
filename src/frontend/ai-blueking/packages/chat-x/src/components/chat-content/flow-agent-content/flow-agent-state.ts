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

import { type VNode, cloneVNode } from 'vue';

import {
  BkFlowFailedIcon,
  BkFlowPendingIcon,
  BkFlowSkippedIcon,
  BkFlowSuccessIcon,
  BkFlowSuspendedIcon,
} from '../../../icons';
import { t } from '../../../lang/lang';

/** 归一后的执行状态 */
export type ConvergedState = 'failed' | 'pending' | 'running' | 'skipped' | 'success' | 'suspended';

/** 单个归一状态的完整定义 */
interface FlowStateDef {
  /** 状态主题色，供统计标签文字与图标语义复用 */
  color: string;
  /** 节点状态点的边框色，缺省回退到 color（仅 pending 与主题色不同） */
  dotColor?: string;
  /** 状态图标（VNode）；running 走 Loading 动画，故为 null */
  icon: null | VNode;
  /** 归一状态标识 */
  key: ConvergedState;
  /** 国际化标签 */
  label: string;
  /** 归一到该状态的后端原始状态枚举 */
  rawStates: string[];
}

/**
 * 执行状态唯一配置源（Single Source of Truth）。
 * 新增 / 调整状态只需维护此处：归一映射、统计标签、颜色、图标均由它派生，
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
    rawStates: ['FAILED', 'REVOKED', 'ROLL_BACK_FAILED'],
  },
  {
    color: '#F59500',
    icon: BkFlowSuspendedIcon,
    key: 'suspended',
    label: t('挂起'),
    rawStates: ['SUSPENDED'],
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

/** 状态主题色（用于统计标签文字） */
export const getStateColor = (state: ConvergedState): string => STATE_DEF_MAP[state].color;

/** 节点状态点边框色 */
export const getStateDotColor = (state: ConvergedState): string =>
  STATE_DEF_MAP[state].dotColor ?? STATE_DEF_MAP[state].color;

/** 取状态图标，返回克隆的 VNode 以支持多处复用；running 无图标返回 null */
export const getStateIcon = (state: ConvergedState): null | VNode => {
  const icon = STATE_DEF_MAP[state].icon;
  return icon ? cloneVNode(icon) : null;
};
