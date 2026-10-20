/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { MessageRole, MessageStatus } from '../../../ag-ui/types/constants';

/** 会话仍在生成；「停止生成」按钮与过程状态栏共用这一判断 */
const GENERATING_MESSAGE_STATUSES = new Set<MessageStatus>([
  MessageStatus.Streaming,
  MessageStatus.StopLoading,
  MessageStatus.Fetching,
  MessageStatus.Pending,
]);

export type ProcessLabelKey = '处理中' | '失败' | '已停止' | '已完成' | '已禁用';

/** 入参为容器级 messageStatus，不是单条消息的状态 */
export const isMessageGenerating = (status?: MessageStatus) =>
  status !== undefined && GENERATING_MESSAGE_STATUSES.has(status);

/**
 * 生成中统一显示「处理中」。
 * 终态文案看最后一条：失败 / 停止 / 禁用各自独立，其余归为「已完成」。
 */
export const resolveProcessLabelKey = (
  messages: readonly { status?: MessageStatus }[],
  generating: boolean,
): ProcessLabelKey => {
  if (generating) {
    return '处理中';
  }
  switch (messages.at(-1)?.status) {
    case MessageStatus.Error:
      return '失败';
    case MessageStatus.Stop:
      return '已停止';
    case MessageStatus.Disabled:
      return '已禁用';
    default:
      return '已完成';
  }
};

/** 每一轮助手回复都显示状态栏 */
export const shouldShowMessageProcess = (group: { messages: readonly unknown[]; type: string }) =>
  group.type === MessageRole.Assistant && group.messages.length > 0;

/** 终态且至少两条消息时才有可折叠的前序过程 */
export const canCollapseProcess = (messages: readonly unknown[], generating: boolean) =>
  !generating && messages.length >= 2;
