/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { IMessageProperty } from '@blueking/chat-helper';

// 重导出旧版本的 IShortcut 以保持完全兼容
export type { IShortcut } from '../../types';

/**
 * 聊天业务管理器配置
 */
export interface ChatBusinessConfig {
  /** 欢迎语 */
  openingRemark?: string;
  /**
   * 会话自动重命名成功回调（首条消息后 AI 生成名称）
   * 用于向上抛出与手动改名一致的 rename 事件；Manager 自身的 eventEmitter 仅接错误桥，不会转发此事件
   * @param newName ai_rename 返回的新名称
   * @param sessionCode 被重命名的会话编码（异步返回时可能已非当前会话）
   */
  onSessionRenamed?: (newName: string, sessionCode: string) => void;
  /** 占位文本 */
  placeholder?: string;
  /** 预定义问题 */
  predefinedQuestions?: string[];
}

/**
 * 创建会话选项
 */
export interface CreateSessionOptions {
  /** 是否为临时会话 */
  isTemporary?: boolean;
  /** 会话标签 */
  labels?: string[];
  /** 会话绑定的模型 llm_code（与 sessionCode 同级写入后台） */
  model?: string;
  /** 会话名称 */
  name?: string;
  /** 会话编码 */
  sessionCode?: string;
}

/**
 * 简化的事件发射器接口
 * 用于 Business Managers 发射事件，不依赖具体的 EventManager 实现
 */
export interface IEventEmitter {
  emit: (event: string, data: any) => void;
}

/**
 * 发送消息选项
 */
export interface SendMessageOptions {
  /** 额外的上下文 */
  context?: Record<string, unknown>;
  /** 是否包含历史记录 */
  includeHistory?: boolean;
  /**
   * 热切换模型 llm_code；传入时覆盖当前选中模型；
   * 未传时使用 ChatBusinessManager.selectedLlmCode
   */
  model?: string;
  /** 消息属性，用于传递引用内容或快捷键相关信息 */
  property?: IMessageProperty;
}

/**
 * 会话业务管理器配置
 */
export interface SessionBusinessConfig {
  /** 是否自动切换到初始会话 */
  autoSwitchToInitialSession?: boolean;
  /** 是否始终创建新会话（初始化时不判断最近会话是否有内容，直接新建） */
  alwaysCreateNewSession?: boolean;
  /** 是否启用会话管理 */
  enableChatSession?: boolean;
  /** 初始会话编码 */
  initialSessionCode?: string;
  /** 挂载时是否加载最近会话 */
  loadRecentSessionOnMount?: boolean;
}

/**
 * 分享消息结果
 */
export interface ShareResult {
  /** 分享链接 */
  shareUrl: string;
  /** 被分享的 user 消息 ID 列表（用于事件通知） */
  userMessageIds: string[];
}

// IShortcut 已在上面从旧版本重导出

/**
 * 快捷方式过滤函数类型
 */
export type ShortcutFilterFn = (shortcut: import('../../types').IShortcut, selectedText: string) => boolean;
