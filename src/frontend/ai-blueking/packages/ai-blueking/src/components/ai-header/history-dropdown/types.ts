/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { SessionBusinessManager } from '../../../manager/business/session-business-manager';
import type { ISession } from '@blueking/chat-helper';

/**
 * 历史下拉面板 Emits 定义
 */
export type HistoryDropdownEmits = {
  close: [];
  'session-delete': [sessionCode: string];
  'session-rename': [sessionCode: string, newName: string];
  'session-switch': [sessionCode: string];
};

/**
 * 历史下拉面板 Props 定义
 *
 * 注意：会话操作回调通过 emit 机制传递（session-switch / session-delete / session-rename），
 * 不在 props 中定义回调函数，避免通过 h() 渲染时 emit 和 prop 双重触发。
 */
export interface HistoryDropdownProps {
  sessionBusinessManager: SessionBusinessManager;
}

/**
 * 历史分组 Props 定义
 */
export interface HistoryGroupProps {
  currentSessionCode?: string;
  sessions: ISession[];
  title: string;
}

/**
 * 历史会话项 Emits 定义
 */
export type HistoryItemEmits = {
  click: [session: ISession];
  delete: [sessionCode: string];
  edit: [session: ISession];
  'rename-cancel': [];
  'rename-confirm': [sessionCode: string, newName: string];
};

/**
 * 历史会话项 Props 定义
 */
export interface HistoryItemProps {
  isActive: boolean;
  isEditing: boolean;
  session: ISession;
}

/**
 * 历史搜索 Emits 定义
 */
export type HistorySearchEmits = {
  'update:modelValue': [value: string];
};

/**
 * 历史搜索 Props 定义
 */
export interface HistorySearchProps {
  modelValue: string;
  placeholder?: string;
}

/**
 * 时间分组数据结构
 */
export interface TimeBucket {
  alias: string;
  key: TimeBucketKey;
  sessionList: ISession[];
}

/**
 * 时间分组键类型
 */
export type TimeBucketKey = '1week' | '3days' | '5days' | 'before' | 'today' | 'yesterday';
