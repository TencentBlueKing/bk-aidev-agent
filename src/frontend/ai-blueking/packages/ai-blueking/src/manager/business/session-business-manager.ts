/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { CreateSessionOptions, IEventEmitter, SessionBusinessConfig } from './types';
import type { IAgentModule, ISessionModule } from '@blueking/chat-helper';

/**
 * 会话业务管理器
 *
 * 职责：
 * - 封装小鲸组件的会话业务流程
 * - 使用 AG-UI SDK 的 session 模块
 * - 处理临时会话、权限检查等小鲸特有逻辑
 * - 不管理数据，只编排业务流程
 */
export class SessionBusinessManager {
  private agentModule: IAgentModule | null;
  private config: SessionBusinessConfig;
  private eventEmitter: IEventEmitter | null;
  private sessionModule: ISessionModule;

  /**
   * 发射事件（内部方法）
   */
  private emit(event: string, data: any): void {
    this.eventEmitter?.emit(event, data);
  }

  constructor(
    sessionModule: ISessionModule,
    agentModule: IAgentModule | null = null,
    eventEmitter: IEventEmitter | null = null,
    config: SessionBusinessConfig = {},
  ) {
    this.sessionModule = sessionModule;
    this.agentModule = agentModule;
    this.eventEmitter = eventEmitter;
    this.config = config;
  }

  get currentSession() {
    return this.sessionModule.current;
  }

  get isCreateLoading() {
    return this.sessionModule.isCreateLoading;
  }

  get isCurrentLoading() {
    return this.sessionModule.isCurrentLoading;
  }

  get isDeleteLoading() {
    return this.sessionModule.isDeleteLoading;
  }

  get isListLoading() {
    return this.sessionModule.isListLoading;
  }

  get isUpdateLoading() {
    return this.sessionModule.isUpdateLoading;
  }

  /**
   * 暴露 AG-UI SDK 的响应式状态
   */
  get sessionList() {
    return this.sessionModule.list;
  }

  /**
   * 创建新会话（便捷方法）
   *
   * 提供给 UI 组件直接调用的简洁 API，无需传递任何参数。
   * 自动生成会话编码，使用默认会话名称。
   *
   * @returns Promise<void>
   * @throws Error 当会话功能被禁用或创建失败时
   *
   * @example
   * ```ts
   * // 在组件中使用
   * await sessionBusinessManager.createNewSession();
   * ```
   */
  async createNewSession(): Promise<void> {
    return this.createSession({
      name: '新会话',
      sessionCode: `new_session_${Date.now()}`,
    });
  }

  /**
   * 创建新会话
   * @param options 创建选项
   */
  async createSession(options: CreateSessionOptions = {}): Promise<void> {
    // 权限检查
    if (this.config.enableChatSession === false) {
      throw new Error('Chat session is disabled');
    }

    try {
      // 构建会话数据
      const sessionData = {
        sessionName: options.name || '新会话',
        sessionCode: options.sessionCode || `session_${Date.now()}`,
        isTemporary: options.isTemporary || false,
      };

      // 调用 AG-UI SDK 创建会话
      await this.sessionModule.createSession(sessionData);

      // 新会话创建后处理角色消息（如开场提示）
      const agentInfo = this.agentModule?.info.value;
      if (agentInfo) {
        this.agentModule?.handleRole(agentInfo, sessionData.sessionCode);
      }

      // 触发事件
      this.emit('session-created', {
        session: this.sessionModule.current.value,
      });
    } catch (error) {
      console.error('Failed to create session:', error);
      this.emit('session-error', {
        action: 'create',
        error,
      });
      throw error;
    }
  }

  /**
   * 删除会话
   * @param sessionCode 会话编码
   */
  async deleteSession(sessionCode: string): Promise<void> {
    try {
      // 调用 AG-UI SDK 删除会话
      await this.sessionModule.deleteSession(sessionCode);

      // 触发事件
      this.emit('session-deleted', {
        sessionCode,
      });
    } catch (error) {
      console.error('Failed to delete session:', error);
      this.emit('session-error', {
        action: 'delete',
        error,
      });
      throw error;
    }
  }

  /**
   * 获取单个会话
   * @param sessionCode 会话编码
   */
  async getSession(sessionCode: string): Promise<void> {
    try {
      await this.sessionModule.getSession(sessionCode);
    } catch (error) {
      console.error('Failed to get session:', error);
      this.emit('session-error', {
        action: 'get',
        error,
      });
      throw error;
    }
  }

  /**
   * 加载最近会话（初始化入口）
   *
   * 初始化逻辑优先级：
   * 1. 如果指定了 initialSessionCode，切换到该会话
   * 2. 如果会话列表不为空：
   *    - 通过 sessionContentCount 判断最近会话是否有内容
   *    - 有内容 → 直接创建新会话（不切换，避免加载消息）
   *    - 无内容 → 切换到该会话（跳过消息加载）
   * 3. 如果会话列表为空，创建新会话
   *
   * @param options.skipLoadSessions 是否跳过加载会话列表（当 useChatBootstrap 已预加载时设为 true）
   */
  async loadRecentSession(options?: { skipLoadSessions?: boolean }): Promise<void> {
    try {
      // 如果不跳过，则加载会话列表
      // useChatBootstrap 会并行预加载会话列表，此时可传入 skipLoadSessions: true
      if (!options?.skipLoadSessions) {
        await this.loadSessions();
      }

      const sessions = this.sessionList.value;

      // 优先级1：如果有初始会话编码，切换到它
      if (this.config.initialSessionCode) {
        await this.switchSession(this.config.initialSessionCode);
        return;
      }

      // 优先级2：如果会话列表不为空
      if (sessions.length > 0) {
        const recentSession = sessions[0];
        // 使用 sessionContentCount 判断是否有内容（后端返回的字段）
        const hasContents = (recentSession.sessionContentCount ?? 0) > 0;

        if (hasContents) {
          // 有内容，直接创建新会话，不切换到旧会话（避免不必要的消息加载）
          await this.createNewSession();
        } else {
          // 无内容，切换到该会话（跳过消息加载，因为空会话没有消息）
          await this.switchSession(recentSession.sessionCode, { loadMessages: false });
        }
        return;
      }

      // 优先级3：会话列表为空，通过统一入口创建新会话
      await this.createNewSession();
    } catch (error) {
      console.error('Failed to load recent session:', error);
      throw error;
    }
  }

  /**
   * 加载会话列表
   */
  async loadSessions(): Promise<void> {
    try {
      await this.sessionModule.getSessions();

      this.emit('sessions-loaded', {
        sessions: this.sessionList.value,
      });
    } catch (error) {
      console.error('Failed to load sessions:', error);
      this.emit('session-error', {
        action: 'load',
        error,
      });
      throw error;
    }
  }

  /**
   * 切换会话
   * @param sessionCode 会话编码
   * @param options 选项
   * @param options.loadMessages 是否加载消息列表，默认 true
   */
  async switchSession(sessionCode: string, options?: { loadMessages?: boolean }): Promise<void> {
    try {
      // 调用 AG-UI SDK 切换会话
      await this.sessionModule.chooseSession(sessionCode, options);

      // 触发事件
      this.emit('session-switched', {
        session: this.sessionModule.current.value,
      });
    } catch (error) {
      console.error('Failed to switch session:', error);
      this.emit('session-error', {
        action: 'switch',
        error,
      });
      throw error;
    }
  }

  /**
   * 更新会话名称
   * @param sessionCode 会话编码
   * @param name 新名称
   */
  async updateSessionName(sessionCode: string, name: string): Promise<void> {
    try {
      const session = this.sessionList.value.find((s: any) => s.sessionCode === sessionCode);
      if (!session) {
        throw new Error(`Session not found: ${sessionCode}`);
      }

      // 更新会话
      await this.sessionModule.updateSession({
        ...session,
        sessionName: name,
      });

      // 触发事件
      this.emit('session-updated', {
        session: this.sessionModule.current.value,
      });
    } catch (error) {
      console.error('Failed to update session name:', error);
      this.emit('session-error', {
        action: 'update',
        error,
      });
      throw error;
    }
  }
}
