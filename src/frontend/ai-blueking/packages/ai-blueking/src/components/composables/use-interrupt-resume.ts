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
  type UserQuestionInterrupt,
  type UserQuestionResume,
} from '@blueking/chat-x';

import type { IChatHelper } from '../../types';
import type { ChatBotEmitFn } from './use-chatbot-init';

const OTHERS_OPTION_LABEL = 'others';

// ApprovalRefresh 无对应后端 userOperation，仅触发一次轮询拉取单据最新状态，故不在此映射内
const USER_OPERATION_MAP: Partial<Record<InterruptResumeOperation, UserOperation>> = {
  [InterruptResumeOperation.ApprovalCancel]: UserOperation.ApprovalCancel,
  [InterruptResumeOperation.FlowNodeRetry]: UserOperation.FlowNodeRetry,
  [InterruptResumeOperation.FlowNodeSkip]: UserOperation.FlowNodeSkip,
};

export interface UseInterruptResumeParams {
  chatHelper: Ref<IChatHelper | null>;
  emit: ChatBotEmitFn;
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

/**
 * 用户在 chat-input 直接输入时的自由文本 resume。
 * chat-x 第三参会携带 cancelled + 空答案的 skip payload，业务层需转为 resolved + Others 答案。
 */
function buildFreeTextUserQuestionResume(
  interrupt: UserQuestionInterrupt | undefined,
  text: string,
  baseResume: UserQuestionResume,
): UserQuestionResume {
  const firstQuestion = interrupt?.metadata?.questions?.[0]?.question ?? '';
  return {
    interruptId: baseResume.interruptId,
    reason: InterruptReason.UserQuestion,
    status: 'resolved',
    payload: {
      answers: [
        {
          question: firstQuestion,
          multiSelect: false,
          answer: [{ label: OTHERS_OPTION_LABEL, description: text }],
        },
      ],
    },
  };
}

export function useInterruptResume(params: UseInterruptResumeParams): UseInterruptResumeReturn {
  const { chatHelper, emit } = params;

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
      console.error('[ChatBot] Failed to handle interrupt resume:', error);
      emit('error', error instanceof Error ? error : new Error(String(error)));
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

      const resume = buildFreeTextUserQuestionResume(
        options.interrupt as UserQuestionInterrupt | undefined,
        input,
        options.payload,
      );

      await handleUserQuestionResume(resume, input);
    } catch (error) {
      console.error('[ChatBot] Failed to resume user question with input:', error);
      emit('error', error instanceof Error ? error : new Error(String(error)));
    }
  };

  return {
    handleInterruptResume,
    resumeUserQuestionWithInput,
  };
}
