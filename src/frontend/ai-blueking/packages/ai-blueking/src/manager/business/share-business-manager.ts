/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { ShareResult } from './types';
import type { IMessage, IMessageModule, ISessionModule } from '@blueking/chat-helper';

/**
 * 分享业务管理器
 *
 * 职责：
 * - 封装消息分享的业务流程
 * - 调用 AG-UI SDK 的 shareMessages 接口
 * - 构造分享链接、提取 user message IDs
 * - 不管理 UI 状态（loading、Toast 等），只编排业务流程
 */
export class ShareBusinessManager {
  private messageModule: IMessageModule;
  private sessionModule: ISessionModule;

  constructor(messageModule: IMessageModule, sessionModule: ISessionModule) {
    this.messageModule = messageModule;
    this.sessionModule = sessionModule;
  }

  /**
   * 分享消息
   *
   * 调用 SDK 分享接口，构造分享链接，提取 user message IDs。
   * UI 层负责处理 loading 状态、Toast 提示、剪贴板复制等。
   *
   * @param messages 要分享的消息列表
   * @returns 分享结果（包含分享链接和 user message IDs）
   * @throws Error 当消息为空、无活跃会话或 API 调用失败时
   */
  async shareMessages(messages: IMessage[]): Promise<ShareResult> {
    if (messages.length === 0) {
      throw new Error('No messages to share');
    }

    const sessionCode = this.sessionModule.current?.value?.sessionCode;
    if (!sessionCode) {
      throw new Error('No active session');
    }

    const result = await this.messageModule.shareMessages(sessionCode, messages);

    if (!result) {
      throw new Error('Share failed: no result returned');
    }

    // 构造分享链接
    const shareUrl = `${result.share_page}share-page/${result.share_token}`;

    // 提取 message IDs（用于事件通知）
    // messages 已由 MessageContainer v-model:selectedUserMessages 保证只含 user 消息
    // chat-helper 层 shareMessages 内部也会再次过滤 role === User 作为防御
    const userMessageIds = messages.map(m => String(m.id));

    return { shareUrl, userMessageIds };
  }
}
