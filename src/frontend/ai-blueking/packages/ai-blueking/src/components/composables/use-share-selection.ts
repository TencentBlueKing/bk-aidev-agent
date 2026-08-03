/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref } from 'vue';

import { Message as BkMessage } from 'bkui-vue';

import { ShareBusinessManager } from '../../manager/business/share-business-manager';
import { copyToClipboard } from '../../utils';

import type { IChatHelper } from '../../types';
import type { ChatBotEmitFn } from './use-chatbot-init';
import type { IMessage } from '@blueking/chat-helper';
import type { IToolBtn, Message } from '@blueking/chat-x';

export interface UseShareSelectionParams {
  chatHelper: Ref<IChatHelper | null>;
  emit: ChatBotEmitFn;
  isStandaloneMode: Ref<boolean>;
}

export interface UseShareSelectionReturn {
  handleConfirmShare: (messages: Message[], source?: IToolBtn) => Promise<void>;
}

/** 内置分享：source 为空（兼容旧分享）或 id 为 share */
export const isBuiltinShareSource = (source?: IToolBtn): boolean => !source || source.id === 'share';

/**
 * 分享确认的业务逻辑。
 * 选择模式的 UI 交互（全选、取消、SelectionFooter 等）已内聚在 ChatContainer 中，
 * 此 composable 仅处理「确认分享」时的业务操作（独立模式下调用 ShareBusinessManager）。
 * 自定义 triggerSelection 按钮确认时不走内置分享，仅向外 emit。
 */
export function useShareSelection(params: UseShareSelectionParams): UseShareSelectionReturn {
  const { emit, chatHelper, isStandaloneMode } = params;

  const doShareMessages = async (messagesToShare: Message[]) => {
    if (!chatHelper.value || messagesToShare.length === 0) return;

    try {
      const shareManager = new ShareBusinessManager(chatHelper.value.message, chatHelper.value.session);
      const result = await shareManager.shareMessages(messagesToShare as unknown as IMessage[]);
      await copyToClipboard(result.shareUrl);
      BkMessage({ message: '分享链接已复制到剪贴板', theme: 'success' });
    } catch (error) {
      console.error('[ChatBot] Failed to share messages:', error);
      BkMessage({ message: '分享失败，请重试', theme: 'error' });
    }
  };

  const handleConfirmShare = async (messages: Message[], source?: IToolBtn) => {
    if (isStandaloneMode.value && isBuiltinShareSource(source)) {
      await doShareMessages(messages);
    }

    emit('confirm-share', messages, source);
  };

  return {
    handleConfirmShare,
  };
}
