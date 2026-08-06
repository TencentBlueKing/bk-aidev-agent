/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref } from 'vue';

import { ResumeStatus, UserOperation, type IResume } from '@blueking/chat-helper';
import {
  InterruptReason,
  InterruptResumeOperation,
  type Interrupt,
  type InterruptResume,
  type ToolApprovalResume,
  type UserMessage,
  type UserQuestionResume,
} from '@blueking/chat-x';

import type { IChatHelper } from '../../types';
import type { ReportChatBotError } from './use-error-reporter';

// ApprovalRefresh 无对应后端 userOperation，仅触发一次轮询拉取单据最新状态，故不在此映射内
const USER_OPERATION_MAP: Partial<Record<InterruptResumeOperation, UserOperation>> = {
  [InterruptResumeOperation.ApprovalCancel]: UserOperation.ApprovalCancel,
  [InterruptResumeOperation.FlowNodeRetry]: UserOperation.FlowNodeRetry,
  [InterruptResumeOperation.FlowNodeSkip]: UserOperation.FlowNodeSkip,
};

export interface UseInterruptResumeParams {
  chatHelper: Ref<IChatHelper | null>;
  reportError: ReportChatBotError;
}

export interface UseInterruptResumeReturn {
  handleInterruptResume: (payload: InterruptResume, interrupt?: Interrupt) => Promise<void>;
  resumeUserQuestionWithInput: (
    content: UserMessage['content'],
    options: { interrupt?: Interrupt; payload?: InterruptResume },
  ) => Promise<void>;
}

function isUserOperationResume(payload: InterruptResume): payload is
  | ToolApprovalResume
  | {
      operation: InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;
      payload: { node_id: string; task_id: number };
    } {
  return 'operation' in payload;
}

function isUserQuestionResume(payload: InterruptResume): payload is UserQuestionResume {
  return 'interruptId' in payload && 'reason' in payload && payload.reason === InterruptReason.UserQuestion;
}

function toResumeStatus(status: UserQuestionResume['status']): ResumeStatus {
  return status === 'cancelled' ? ResumeStatus.Cancelled : ResumeStatus.Resolved;
}

function getSessionCode(chatHelper: IChatHelper | null): string {
  const sessionCode = chatHelper?.session.current?.value?.sessionCode;
  if (!sessionCode) {
    throw new Error('[ChatBot] Cannot resume interrupt: no active session');
  }
  return sessionCode;
}

function toIResume(resume: UserQuestionResume): IResume {
  return {
    interruptId: resume.interruptId,
    status: toResumeStatus(resume.status),
    payload: resume.payload,
  };
}

export function useInterruptResume(params: UseInterruptResumeParams): UseInterruptResumeReturn {
  const { chatHelper, reportError } = params;

  const handleUserOperationResume = async (payload: InterruptResume) => {
    const helper = chatHelper.value;
    if (!helper) {
      throw new Error('[ChatBot] Cannot resume interrupt: chatHelper not initialized');
    }

    if (!isUserOperationResume(payload)) {
      throw new Error('[ChatBot] Unsupported interrupt resume payload');
    }

    const sessionCode = getSessionCode(helper);

    // 刷新审批单状态：复用 chat-x（chat-helper）的轮询能力，主动拉取一次单据最新状态即可
    if (payload.operation === InterruptResumeOperation.ApprovalRefresh) {
      const agent = helper.agent as typeof helper.agent & {
        pollResumeSession: (sessionCode: string) => void;
      };
      agent.pollResumeSession(sessionCode);
      return;
    }

    const operation = USER_OPERATION_MAP[payload.operation];
    if (!operation) {
      throw new Error(`[ChatBot] Unsupported interrupt resume operation: ${payload.operation}`);
    }
    const agent = helper.agent as typeof helper.agent & {
      userOperationStreamRequest: (
        sessionCode: string,
        operation: UserOperation,
        payload: { interrupt_id: number | string } | { node_id: string; task_id: string },
      ) => Promise<void>;
    };

    if (payload.operation === InterruptResumeOperation.ApprovalCancel) {
      await agent.userOperationStreamRequest(sessionCode, operation, { interrupt_id: payload.payload.interrupt_id });
      return;
    }

    if (
      payload.operation === InterruptResumeOperation.FlowNodeRetry ||
      payload.operation === InterruptResumeOperation.FlowNodeSkip
    ) {
      await agent.userOperationStreamRequest(sessionCode, operation, {
        node_id: payload.payload.node_id,
        task_id: String(payload.payload.task_id),
      });
    }
  };

  const handleUserQuestionResume = async (payload: UserQuestionResume, input?: string) => {
    const helper = chatHelper.value;
    if (!helper) {
      throw new Error('[ChatBot] Cannot resume interrupt: chatHelper not initialized');
    }

    const sessionCode = getSessionCode(helper);
    const agent = helper.agent as typeof helper.agent & {
      streamRequest: (options: { sessionCode: string; resume?: IResume; input?: string }) => Promise<void>;
    };

    await agent.streamRequest({
      sessionCode,
      resume: toIResume(payload),
      ...(input ? { input } : {}),
    });
  };

  const handleInterruptResume = async (payload: InterruptResume, _interrupt?: Interrupt) => {
    try {
      if (isUserOperationResume(payload)) {
        await handleUserOperationResume(payload);
        return;
      }

      if (isUserQuestionResume(payload)) {
        await handleUserQuestionResume(payload);
        return;
      }

      throw new Error('[ChatBot] Unsupported interrupt resume payload');
    } catch (error) {
      reportError(error, 'Failed to handle interrupt resume');
    }
  };

  const resumeUserQuestionWithInput = async (
    content: UserMessage['content'],
    options: { interrupt?: Interrupt; payload?: InterruptResume },
  ) => {
    try {
      if (!options.payload || !isUserQuestionResume(options.payload)) {
        throw new Error('[ChatBot] Invalid user question resume options');
      }

      const input = typeof content === 'string' ? content.trim() : '';
      if (!input) {
        throw new Error('[ChatBot] User question free text input is empty');
      }

      // 用户未做结构化选择：直接沿用 chat-x 的 skip payload（cancelled + 空 answers），
      // 自由文本不塞进 answers，只通过 input 传给后端
      await handleUserQuestionResume(options.payload, input);
    } catch (error) {
      reportError(error, 'Failed to resume user question with input');
    }
  };

  return {
    handleInterruptResume,
    resumeUserQuestionWithInput,
  };
}
