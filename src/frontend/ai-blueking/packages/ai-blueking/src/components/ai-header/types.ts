/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { SessionBusinessManager } from '../../manager/business/session-business-manager';
import type { RenderMode } from '@blueking/chat-x';

/**
 * AI Header 组件 Emits 定义
 */
export type AIHeaderEmits = {
  'auto-generate-name': [];
  close: [];
  'help-click': [];
  'history-click': [event: Event];
  'history-session-delete': [sessionCode: string];
  'history-session-rename': [sessionCode: string, newName: string];
  // V2 新增：历史会话事件
  'history-session-switch': [sessionCode: string];
  'new-chat': [];
  // 新增会话成功事件
  'new-chat-created': [session: { createdAt?: string; sessionCode: string; sessionName?: string }];
  rename: [newName: string];
  share: [];
  'toggle-aside': [];
  'toggle-compression': [];
};

/**
 * AI Header 组件 Props 定义
 */
export interface AIHeaderProps {
  agentName?: string;
  /** 侧栏是否折叠（仅用于图标/tooltip 展示） */
  asideCollapsed?: boolean;
  autoGenerateLoading?: boolean;
  draggable?: boolean;
  enableChatSession?: boolean;
  hasPermission?: boolean;
  hasSessionContents?: boolean;
  isCompressionHeight?: boolean;
  /** 渲染模式：chat(默认)、share(分享)、test(测试) */
  renderMode?: RenderMode;
  /** 当前选中模型 llm_code（新建会话时写入 session.model） */
  selectedLlmCode?: string;
  // V2 新增：会话业务管理器
  sessionBusinessManager?: SessionBusinessManager;
  sessionName?: string;
  /** 是否展示侧栏展开/收起按钮，默认 true */
  showAsideToggle?: boolean;
  showCompressionIcon?: boolean;
  showHistoryIcon?: boolean;
  showMoreIcon?: boolean;
  showNewChatIcon?: boolean;
  title?: string;
  chatGroup?: {
    enabled: boolean;
    staff: string[];
    username: string;
  };
  dropdownMenuConfig?: {
    showAutoGenerate?: boolean;
    showRename?: boolean;
    showShare?: boolean;
  };
}
