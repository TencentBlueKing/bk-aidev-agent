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

import { t } from '../../lang/lang';
import { APPROVAL_STATUS } from './interrupt';

export enum InterruptReason {
  AIDevToolApproval = 'ai_dev:tool_approval', // AI dev 第三方审批
  HumanApproval = 'human_approval', // 人工审批
  UserMultiChoice = 'user_multi_choice', // 用户多选
  UserSingleChoice = 'user_single_choice', // 用户单选
}

export enum MessageContentType {
  Binary = 'binary',
  FlowAgent = 'flow_agent',
  Function = 'function',
  KeyValue = 'key_value',
  KnowledgeRag = 'knowledge_rag',
  Other = 'other',
  ReferenceDocument = 'reference_document',
  Text = 'text',
}

export enum MessageRole {
  Activity = 'activity',
  Assistant = 'assistant',
  Developer = 'developer',
  Guide = 'guide',
  Hidden = 'hidden',
  HiddenAssistant = 'hidden-assistant',
  HiddenGuide = 'hidden-guide',
  HiddenSystem = 'hidden-system',
  HiddenUser = 'hidden-user',
  Info = 'info',
  Interrupt = 'interrupt',
  Loading = 'loading',
  Pause = 'pause',
  Placeholder = 'placeholder',
  Reasoning = 'reasoning',
  System = 'system',
  TemplateAssistant = 'template-assistant',
  TemplateGuide = 'template-guide',
  TemplateHidden = 'template-hidden',
  TemplateSystem = 'template-system',
  TemplateUser = 'template-user',
  Tool = 'tool',
  User = 'user',
}

export enum MessageStatus {
  Complete = 'complete',
  Disabled = 'disabled',
  Error = 'error',
  Fetching = 'fetching', // 请求中
  Pending = 'pending',
  Stop = 'stop',
  StopLoading = 'stop-loading',
  Streaming = 'streaming',
  Success = 'success',
}

export enum RunFinishedOutcome {
  Interrupt = 'interrupt',
  Success = 'success',
}

export const APPROVAL_STATUS_MAP: Record<APPROVAL_STATUS, string> = {
  [APPROVAL_STATUS.ABANDONED]: t('已废弃'),
  [APPROVAL_STATUS.APPROVED]: t('已批准'),
  [APPROVAL_STATUS.CANCELLED]: t('已取消'),
  [APPROVAL_STATUS.EXPIRED]: t('已过期'),
  [APPROVAL_STATUS.PENDING]: t('评审中'),
  [APPROVAL_STATUS.REJECTED]: t('已拒绝'),
};
