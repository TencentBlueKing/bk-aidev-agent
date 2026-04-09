/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { ref } from 'vue';
import type { Ref } from 'vue';

import { Message as BkMessage } from 'bkui-vue';

import { t } from '../lang';
import { copyToClipboard } from '../utils';

import type ChatBot from '../components/chat-bot.vue';
import type { ShareBusinessManager } from '../manager/business/share-business-manager';
import type { IMessage } from '../types';
import type { EventForwarders } from './use-ai-blueking-init';
import type { Message } from '@blueking/chat-x';

export interface UseShareHandlersParams {
  chatBotRef: Ref<InstanceType<typeof ChatBot> | undefined>;
  forwarders: EventForwarders;
  shareBusinessManager: ShareBusinessManager;
  handleError: (error: Error) => void;
}

export function useShareHandlers(params: UseShareHandlersParams) {
  const { shareBusinessManager, chatBotRef, forwarders, handleError } = params;

  const isShareLoading = ref(false);

  /**
   * 进入分享选择模式
   * 通过 ChatBot expose 委托给 ChatContainer
   */
  const handleShare = () => {
    chatBotRef.value?.enterShareMode();
    forwarders.share();
  };

  /**
   * 取消分享，退出选择模式
   */
  const handleCancelShare = () => {
    chatBotRef.value?.exitShareMode();
  };

  /**
   * 确认分享：调用后端接口 → 复制链接 → 退出选择模式
   */
  const handleConfirmShare = async (messages: Message[]) => {
    isShareLoading.value = true;

    try {
      const { shareUrl, userMessageIds } = await shareBusinessManager.shareMessages(messages as unknown as IMessage[]);

      await copyToClipboard(shareUrl);

      BkMessage({
        message: t('分享链接已复制到剪贴板'),
        theme: 'success',
      });

      chatBotRef.value?.exitShareMode();

      forwarders.shareMessages(userMessageIds);
    } catch (error) {
      console.error('[AIBlueking] Failed to share messages:', error);
      handleError(error as Error);
    } finally {
      isShareLoading.value = false;
    }
  };

  return {
    isShareLoading,
    handleShare,
    handleCancelShare,
    handleConfirmShare,
  };
}
