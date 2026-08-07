/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { toValue } from 'vue';

import { Message } from 'bkui-vue';

import { t } from '../../lang';
import { toError } from '../../utils';

import type { MaybeRefOrGetter } from 'vue';
import type { IEventEmitter } from '../../manager/business/types';
import type { ChatBotEmitFn } from './use-chatbot-init';

/**
 * 业务管理器中代表「操作失败」的内部事件
 * 其余内部事件（send-message / receive-* / session-switched 等）由 ChatBot 各调用点
 * 自行 emit，此处不转发，避免同一动作对外触发两次
 */
const MANAGER_ERROR_EVENTS = new Set(['chat-error', 'receive-error', 'session-error']);

/** ChatBot 统一错误上报函数 */
export type ReportChatBotError = (error: unknown, context?: string) => Error;

export interface UseErrorReporterOptions {
  /** 是否自动弹 Message；默认 true；支持 ref/getter 以便跟随 props 变化 */
  errorToast?: MaybeRefOrGetter<boolean | undefined>;
}

export interface UseErrorReporterReturn {
  /**
   * 注入业务管理器的事件发射器
   * 业务管理器的失败事件经此汇入同一个错误出口，覆盖调用点没有 catch 的路径
   */
  managerErrorBridge: IEventEmitter;
  /** 统一错误出口：归一化为 Error、按实例去重后 emit('error')，并按需弹 toast */
  reportError: ReportChatBotError;
}

/**
 * ChatBot 错误上报出口
 *
 * 同一个错误可能同时经由业务管理器的失败事件和调用点的 catch 抵达（业务管理器普遍
 * 「emit 后 rethrow」），按 Error 实例去重保证对外只触发一次 `error`。
 */
export function useErrorReporter(
  emit: ChatBotEmitFn,
  options: UseErrorReporterOptions = {},
): UseErrorReporterReturn {
  const reportedErrors = new WeakSet<Error>();

  const reportError: ReportChatBotError = (error, context) => {
    const normalized = toError(error);

    if (reportedErrors.has(normalized)) {
      return normalized;
    }
    reportedErrors.add(normalized);

    console.error(context ? `[ChatBot] ${context}:` : '[ChatBot] error:', error);
    emit('error', normalized);

    if (toValue(options.errorToast) !== false) {
      Message({
        message: normalized.message || t('请求失败'),
        theme: 'error',
      });
    }

    return normalized;
  };

  const managerErrorBridge: IEventEmitter = {
    emit: (event: string, data: unknown) => {
      if (MANAGER_ERROR_EVENTS.has(event)) {
        reportError((data as { error?: unknown } | undefined)?.error);
      }
    },
  };

  return { managerErrorBridge, reportError };
}
