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

import { isBuiltinShareSource } from '../components/composables/use-share-selection';
import { t } from '../lang';
import { copyToClipboard } from '../utils';

import type ChatBot from '../components/chat-bot.vue';
import type { ShareBusinessManager } from '../manager/business/share-business-manager';
import type { IMessage, ReportSdkErrorOptions } from '../types';
import type { EventForwarders } from './use-ai-blueking-init';
import type { IToolBtn, Message } from '@blueking/chat-x';

export interface UseShareHandlersParams {
  chatBotRef: Ref<InstanceType<typeof ChatBot> | undefined>;
  emit: (event: 'confirm-share', messages: Message[], source?: IToolBtn) => void;
  forwarders: EventForwarders;
  shareBusinessManager: ShareBusinessManager;
  reportSdkError: (options: ReportSdkErrorOptions) => void;
}

export function useShareHandlers(params: UseShareHandlersParams) {
  const { shareBusinessManager, chatBotRef, emit, forwarders, reportSdkError } = params;

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
   * 确认分享/多选。
   * 仅内置分享（`!source || source.id === 'share'`）走 ShareBusinessManager；
   * 自定义 triggerSelection 按钮只向外 emit，不触发真实分享。
   */
  const handleConfirmShare = async (messages: Message[], source?: IToolBtn) => {
    if (!isBuiltinShareSource(source)) {
      chatBotRef.value?.exitShareMode();
      emit('confirm-share', messages, source);
      return;
    }

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
      emit('confirm-share', messages, source);
    } catch (error) {
      console.error('[AIBlueking] Failed to share messages:', error);
      reportSdkError({ apiName: 'share', action: 'confirmShare', error, source: 'business' });
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
