/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { hasRealMessageContent } from '../../utils/message-utils';

import type { CreateSessionOptions, IEventEmitter, SessionBusinessConfig } from './types';
import type { IAgentModule, IMessageModule, ISession, ISessionModule } from '@blueking/chat-helper';
import type { Ref } from 'vue';

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
  private messageModule: IMessageModule | null;
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
    messageModule: IMessageModule | null = null,
  ) {
    this.sessionModule = sessionModule;
    this.agentModule = agentModule;
    this.eventEmitter = eventEmitter;
    this.config = config;
    this.messageModule = messageModule;
  }

  get currentSession(): Ref<ISession | null> {
    return this.sessionModule.current;
  }

  get isCreateLoading(): Ref<boolean> {
    return this.sessionModule.isCreateLoading;
  }

  get isCurrentLoading(): Ref<boolean> {
    return this.sessionModule.isCurrentLoading;
  }

  get isDeleteLoading(): Ref<boolean> {
    return this.sessionModule.isDeleteLoading;
  }

  get isListLoading(): Ref<boolean> {
    return this.sessionModule.isListLoading;
  }

  get isUpdateLoading(): Ref<boolean> {
    return this.sessionModule.isUpdateLoading;
  }

  /**
   * 暴露 AG-UI SDK 的响应式状态
   */
  get sessionList(): Ref<ISession[]> {
    return this.sessionModule.list;
  }

  /**
   * 创建新会话（便捷方法）
   *
   * 提供给 UI 组件直接调用的简洁 API，无需传递任何参数。
   * 自动生成会话编码，使用默认会话名称。
   *
   * 智能复用逻辑：
   * - 当前会话已是空会话 → 不创建，返回 null
   * - sessionList 最新会话是空会话 → 切换到它，返回 null（非新建）
   * - 否则 → 创建新会话，返回新会话
   *
   * @returns 新创建的会话；如果复用了已有空会话则返回 null
   */
  async createNewSession(): Promise<ISession | null> {
    // 如果当前会话已经是空会话，无需创建（以实时消息列表为准，而非后端快照）
    const current = this.currentSession.value;
    if (current?.sessionCode && this.isCurrentSessionEmpty(current)) {
      return null;
    }

    // 刷新会话列表，确保 sessionContentCount 是最新的
    await this.loadSessions();

    // 如果 sessionList 最新的会话是空会话，直接切换到它，避免重复创建。
    // 对「当前正在使用的会话」用实时消息判断，避免后端 count 滞后时误复用刚聊过的会话。
    const sessions = this.sessionList.value;
    if (sessions.length > 0) {
      const latestSession = sessions[0];
      const latestIsEmpty =
        latestSession.sessionCode === current?.sessionCode
          ? this.isCurrentSessionEmpty(latestSession)
          : this.isSessionEmpty(latestSession);
      if (latestIsEmpty) {
        await this.switchSession(latestSession.sessionCode, { loadMessages: false });
        return null;
      }
    }

    await this.createSession({
      name: '新会话',
      sessionCode: this.generateSessionCode(),
    });
    return this.sessionModule.current.value;
  }

  /**
   * 生成新会话编码
   */
  private generateSessionCode(): string {
    return `new_session_${Date.now()}`;
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
        sessionProperty: {
          labels: options.labels,
        },
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
   * 判断会话是否为空（无历史消息）
   *
   * 同时检查 sessionContentCount 和 list 中的最新值。
   * 因为单条会话 API（getSession）可能不返回 session_content_count，
   * 但列表 API（getSessions）始终包含该字段，所以优先使用 list 中的值。
   * 如果两者都没有，保守处理：当作有内容（loadMessages）。
   */
  private isSessionEmpty(session: ISession): boolean {
    const listEntry = this.findSession(session.sessionCode);
    const count = listEntry?.sessionContentCount ?? session.sessionContentCount;
    if (count == null) return false;
    return count === 0;
  }

  /**
   * 判断「当前会话」是否为空（无真实消息）
   *
   * 与 isSessionEmpty 的区别：当前会话的消息已加载到 messageModule，
   * sessionContentCount 是后端快照，聊天发消息后不会更新，会导致误判为空。
   * 因此优先以实时消息列表为准（与 UI 的 hasSessionContents 同源），
   * 仅在无消息模块或消息列表为空时，回退到 sessionContentCount 判断。
   */
  private isCurrentSessionEmpty(session: ISession): boolean {
    if (this.messageModule && hasRealMessageContent(this.messageModule.list.value)) {
      return false;
    }
    return this.isSessionEmpty(session);
  }

  /**
   * 从会话列表中查找指定会话
   */
  private findSession(sessionCode: string): ISession | undefined {
    return this.sessionList.value.find(session => session.sessionCode === sessionCode);
  }

  /**
   * 加载最近会话（初始化入口）
   *
   * 初始化逻辑优先级：
   * 1. 如果指定了 initialSessionCode，切换到该会话
   * 2. 如果会话列表不为空：
   *    - 通过 sessionContentCount 判断最近会话是否有内容（alwaysCreateNewSession 为 true 时跳过判断，直接新建）
   *    - 有内容 → 直接创建新会话（不切换，避免加载消息）
   *    - 无内容 → 切换到该会话（跳过消息加载）
   * 3. 如果会话列表为空，创建新会话
   *
   * @param options.skipLoadSessions 是否跳过加载会话列表（当 useChatBootstrap 已预加载时设为 true）
   * @param options.alwaysCreateNewSession 是否始终创建新会话（优先级高于 config 中的配置）
   */
  async loadRecentSession(options?: { skipLoadSessions?: boolean; alwaysCreateNewSession?: boolean }): Promise<void> {
    try {
      const current = this.currentSession.value;
      if (current?.sessionCode) {
        return;
      }

      // 如果不跳过，则加载会话列表
      // useChatBootstrap 会并行预加载会话列表，此时可传入 skipLoadSessions: true
      if (!options?.skipLoadSessions) {
        await this.loadSessions();
      }

      const sessions = this.sessionList.value;

      // 优先级1：如果有初始会话编码，切换到它
      if (this.config.initialSessionCode) {
        const target = this.findSession(this.config.initialSessionCode);
        await this.switchSession(this.config.initialSessionCode, {
          loadMessages: target ? !this.isSessionEmpty(target) : true,
        });
        return;
      }

      // 优先级2：如果会话列表不为空
      if (sessions.length > 0) {
        const recentSession = sessions[0];
        // 使用 sessionContentCount 判断是否有内容（后端返回的字段）
        const hasContents = (recentSession.sessionContentCount ?? 0) > 0;
        // options 优先级高于 config
        const forceNewSession = options?.alwaysCreateNewSession ?? this.config.alwaysCreateNewSession ?? false;

        if (hasContents || forceNewSession) {
          // 有内容，或强制新建，直接创建新会话，不切换到旧会话（避免不必要的消息加载）。
          // 这里已明确判定必须新建，故直接调用 createSession，不走带「复用空会话」的
          // createNewSession：既避免重复 loadSessions，也保证 alwaysCreateNewSession 语义不被复用逻辑改写。
          await this.createSession({ name: '新会话', sessionCode: this.generateSessionCode() });
        } else {
          // 无内容，切换到该会话（跳过消息加载，因为空会话没有消息）
          await this.switchSession(recentSession.sessionCode, { loadMessages: false });
        }
        return;
      }

      // 优先级3：会话列表为空，直接创建新会话
      await this.createSession({ name: '新会话', sessionCode: this.generateSessionCode() });
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
