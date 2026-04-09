/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { SessionBusinessManager } from '../../manager/business/session-business-manager';

/**
 * AI Header 组件 Props 定义
 */
export interface AIHeaderProps {
  title?: string;
  agentName?: string;
  sessionName?: string;
  isCompressionHeight?: boolean;
  draggable?: boolean;
  showHistoryIcon?: boolean;
  showNewChatIcon?: boolean;
  showCompressionIcon?: boolean;
  showMoreIcon?: boolean;
  enableChatSession?: boolean;
  hasPermission?: boolean;
  chatGroup?: {
    enabled: boolean;
    staff: string[];
    username: string;
  };
  hasSessionContents?: boolean;
  dropdownMenuConfig?: {
    showRename?: boolean;
    showAutoGenerate?: boolean;
    showShare?: boolean;
  };
  // V2 新增：会话业务管理器
  sessionBusinessManager?: SessionBusinessManager;
}

/**
 * AI Header 组件 Emits 定义
 */
export type AIHeaderEmits = {
  close: [];
  'toggle-compression': [];
  'new-chat': [];
  'history-click': [event: Event];
  'auto-generate-name': [];
  'help-click': [];
  rename: [newName: string];
  share: [];
  // V2 新增：历史会话事件
  'history-session-switch': [sessionCode: string];
  'history-session-delete': [sessionCode: string];
  'history-session-rename': [sessionCode: string, newName: string];
};
