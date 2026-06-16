import { describe, it, expect, vi, beforeEach } from 'vitest';
import { shallowRef } from 'vue';

import { UserOperation } from '@blueking/chat-helper';
import { InterruptReason, InterruptResumeOperation } from '@blueking/chat-x';

import { createMockChatHelper, createMockEmit } from '../../../__tests__/helpers';
import { useInterruptResume } from '../use-interrupt-resume';

function createParams() {
  const chatHelper = shallowRef(createMockChatHelper());
  (chatHelper.value!.session.current as { value: { sessionCode: string } | null }).value = {
    sessionCode: 'session-1',
  };
  return {
    chatHelper,
    emit: createMockEmit(),
  };
}

describe('useInterruptResume', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('flow_node_retry 应调用 userOperationStreamRequest', async () => {
    const params = createParams();
    const { handleInterruptResume } = useInterruptResume(params);

    await handleInterruptResume({
      operation: InterruptResumeOperation.FlowNodeRetry,
      payload: { node_id: 'node-1', task_id: 123 },
    });

    expect(params.chatHelper.value!.agent.userOperationStreamRequest).toHaveBeenCalledWith(
      'session-1',
      UserOperation.FlowNodeRetry,
      { node_id: 'node-1', task_id: '123' },
    );
  });

  it('flow_node_skip 应调用 userOperationStreamRequest', async () => {
    const params = createParams();
    const { handleInterruptResume } = useInterruptResume(params);

    await handleInterruptResume({
      operation: InterruptResumeOperation.FlowNodeSkip,
      payload: { node_id: 'node-2', task_id: 456 },
    });

    expect(params.chatHelper.value!.agent.userOperationStreamRequest).toHaveBeenCalledWith(
      'session-1',
      UserOperation.FlowNodeSkip,
      { node_id: 'node-2', task_id: '456' },
    );
  });

  it('approval_cancel 应调用 userOperationStreamRequest', async () => {
    const params = createParams();
    const { handleInterruptResume } = useInterruptResume(params);

    await handleInterruptResume({
      operation: InterruptResumeOperation.ApprovalCancel,
      payload: { interrupt_id: 987654 },
    });

    expect(params.chatHelper.value!.agent.userOperationStreamRequest).toHaveBeenCalledWith(
      'session-1',
      UserOperation.ApprovalCancel,
      { interrupt_id: 987654 },
    );
  });

  it('approval_cancel 应保留字符串 interrupt_id', async () => {
    const params = createParams();
    const { handleInterruptResume } = useInterruptResume(params);

    await handleInterruptResume({
      operation: InterruptResumeOperation.ApprovalCancel,
      payload: { interrupt_id: 'interrupt-1' },
    });

    expect(params.chatHelper.value!.agent.userOperationStreamRequest).toHaveBeenCalledWith(
      'session-1',
      UserOperation.ApprovalCancel,
      { interrupt_id: 'interrupt-1' },
    );
  });

  it('ask-user-question 结构化回答应调用 streamRequest', async () => {
    const params = createParams();
    const { handleInterruptResume } = useInterruptResume(params);

    await handleInterruptResume({
      interruptId: 'interrupt-1',
      reason: InterruptReason.UserQuestion,
      status: 'resolved',
      payload: {
        answers: [
          {
            question: '请选择环境',
            answer: [{ label: 'prod', description: '生产环境' }],
          },
        ],
      },
    });

    expect(params.chatHelper.value!.agent.streamRequest).toHaveBeenCalledWith({
      sessionCode: 'session-1',
      resume: {
        interruptId: 'interrupt-1',
        status: 'resolved',
        payload: {
          answers: [
            {
              question: '请选择环境',
              answer: [{ label: 'prod', description: '生产环境' }],
            },
          ],
        },
      },
    });
  });

  it('ask-user-question 直接输入应调用 streamRequest 并传入 input', async () => {
    const params = createParams();
    const { resumeUserQuestionWithInput } = useInterruptResume(params);

    await resumeUserQuestionWithInput('自由文本回答', {
      interrupt: {
        id: 'interrupt-1',
        reason: InterruptReason.UserQuestion,
        toolCallId: 'tc-1',
        metadata: {
          questions: [{ header: '问题', question: '请补充说明' }],
        },
      },
      payload: {
        interruptId: 'interrupt-1',
        reason: InterruptReason.UserQuestion,
        status: 'cancelled',
        payload: { answers: [] },
      },
    });

    expect(params.chatHelper.value!.agent.streamRequest).toHaveBeenCalledWith({
      sessionCode: 'session-1',
      input: '自由文本回答',
      resume: {
        interruptId: 'interrupt-1',
        status: 'resolved',
        payload: {
          answers: [
            {
              question: '请补充说明',
              multiSelect: false,
              answer: [{ label: 'others', description: '自由文本回答' }],
            },
          ],
        },
      },
    });
  });

  it('无当前会话时应 emit error', async () => {
    const params = createParams();
    (params.chatHelper.value!.session.current as { value: null }).value = null;
    const { handleInterruptResume } = useInterruptResume(params);

    await handleInterruptResume({
      operation: InterruptResumeOperation.FlowNodeRetry,
      payload: { node_id: 'node-1', task_id: 1 },
    });

    expect(params.emit).toHaveBeenCalledWith('error', expect.any(Error));
  });
});
