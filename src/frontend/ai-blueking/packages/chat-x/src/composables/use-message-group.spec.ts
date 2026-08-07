/* eslint-disable @typescript-eslint/consistent-type-imports */
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
import { computed, ref as deepRef, nextTick, shallowRef } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { APPROVAL_STATUS, InterruptReason, MessageContentType, MessageRole, MessageStatus } from '../ag-ui/types';
import { AIFileType } from '../ag-ui/types/file';
import { LOADING_MESSAGE_ID, RenderMode } from '../common/constants';
import { useMessageGroup } from './use-message-group';

import type { AssistantMessage, Message, ToolMessage, UserMessage } from '../ag-ui/types';
import type { AIFileInfo } from '../ag-ui/types/file';

vi.mock('../utils', async importOriginal => {
  const actual = await importOriginal<typeof import('../utils')>();
  return {
    ...actual,
    generateUUID: vi.fn(() => `uuid-${Math.random().toString(36).slice(2, 8)}`),
  };
});

const createUserMessage = (id: string, content = 'hello'): UserMessage => ({
  id,
  content,
  messageId: id,
  role: MessageRole.User,
  status: MessageStatus.Complete,
});

const createAssistantMessage = (
  id: string,
  content = 'hi',
  overrides: Partial<AssistantMessage> = {},
): AssistantMessage => ({
  id,
  content,
  messageId: id,
  role: MessageRole.Assistant,
  status: MessageStatus.Complete,
  ...overrides,
});

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: 'file.pdf',
  outputId: 'output-1',
  size: 1024,
  type: AIFileType.Pdf,
  ...overrides,
});

const createToolMessage = (id: string, toolCallId: string, content = 'result'): ToolMessage => ({
  id,
  content,
  messageId: id,
  role: MessageRole.Tool,
  status: MessageStatus.Complete,
  toolCallId,
  duration: 100,
});

const createApprovalInterruptMessage = (id: string, status: APPROVAL_STATUS): Message =>
  ({
    id,
    messageId: id,
    role: MessageRole.Interrupt,
    status: MessageStatus.Complete,
    content: {
      outcome: {
        type: 'interrupt',
        interrupts: [
          {
            id: `${id}-interrupt`,
            reason: InterruptReason.AIDevToolApproval,
            toolCallId: `${id}-tool`,
            metadata: {
              ticket: {
                approvers: ['张三'],
                sn: `REV-${id}`,
                status,
                submit_time: '2026-04-24 14:30:15',
                title: '算法方案评审单',
                url: 'https://example.com/ticket',
              },
            },
          },
        ],
      },
    },
  }) as Message;

const setupMessageGroup = (messages: Message[], keyword = '', renderMode?: RenderMode) => {
  const messagesRef = computed(() => messages);
  const selectedUserMessages = deepRef<Message[] | undefined>([]);
  const keywordRef = shallowRef(keyword);
  const renderModeRef = shallowRef(renderMode);

  const result = useMessageGroup({
    keyword: keywordRef,
    messages: messagesRef,
    renderMode: renderModeRef,
    selectedUserMessages,
  });

  return { ...result, selectedUserMessages, keywordRef, messagesRef, renderModeRef };
};

describe('useMessageGroup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('消息分组', () => {
    it('空消息应该返回空分组', async () => {
      const { messageGroups } = setupMessageGroup([]);
      await nextTick();

      expect(messageGroups.value.length).toBe(0);
    });

    it('无 uid 的消息应在分组前被补充 uid', async () => {
      const userMsg = createUserMessage('1');
      expect(userMsg.uid).toBeUndefined();

      const { messageGroups } = setupMessageGroup([userMsg]);
      await nextTick();

      expect(userMsg.uid).toBeDefined();
      expect(messageGroups.value[0]?.messages[0]?.uid).toBe(userMsg.uid);
    });

    it('单条用户消息应该创建 User 组 + Loading 组', async () => {
      const { messageGroups } = setupMessageGroup([createUserMessage('1')]);
      await nextTick();

      expect(messageGroups.value.length).toBe(2);
      expect(messageGroups.value[0]?.type).toBe(MessageRole.User);
      expect(messageGroups.value[1]?.type).toBe(MessageRole.Loading);
    });

    it('Loading 组占位消息 id 应为 LOADING_MESSAGE_ID', async () => {
      const { messageGroups } = setupMessageGroup([createUserMessage('1')]);
      await nextTick();

      const loadingMsg = messageGroups.value[1]?.messages[0];
      expect(loadingMsg?.id).toBe(LOADING_MESSAGE_ID);
    });

    it('单条助手消息应该创建 Assistant 组', async () => {
      const { messageGroups } = setupMessageGroup([createAssistantMessage('1')]);
      await nextTick();

      expect(messageGroups.value.length).toBe(1);
      expect(messageGroups.value[0]?.type).toBe(MessageRole.Assistant);
    });

    it('交替的用户和助手消息应该正确分组', async () => {
      const messages = [
        createUserMessage('1'),
        createAssistantMessage('2'),
        createUserMessage('3'),
        createAssistantMessage('4'),
      ];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(messageGroups.value.length).toBe(4);
      expect(messageGroups.value[0]?.type).toBe(MessageRole.User);
      expect(messageGroups.value[1]?.type).toBe(MessageRole.Assistant);
      expect(messageGroups.value[2]?.type).toBe(MessageRole.User);
      expect(messageGroups.value[3]?.type).toBe(MessageRole.Assistant);
    });

    it('连续的助手消息应该分在同一组', async () => {
      const messages = [createAssistantMessage('1', 'msg1'), createAssistantMessage('2', 'msg2')];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(messageGroups.value.length).toBe(1);
      expect(messageGroups.value[0]?.messages.length).toBe(2);
    });

    it('末尾为用户消息时应追加 Loading 组', async () => {
      const messages = [createUserMessage('1'), createAssistantMessage('2'), createUserMessage('3')];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      const lastGroup = messageGroups.value.at(-1);
      expect(lastGroup?.type).toBe(MessageRole.Loading);
    });

    it('末尾为助手消息时不应追加 Loading 组', async () => {
      const messages = [createUserMessage('1'), createAssistantMessage('2')];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      const lastGroup = messageGroups.value.at(-1);
      expect(lastGroup?.type).toBe(MessageRole.Assistant);
    });

    it('renderMode 为 Share 时末尾为用户消息不应追加 Loading 组', async () => {
      const { messageGroups } = setupMessageGroup([createUserMessage('1')], '', RenderMode.Share);
      await nextTick();

      expect(messageGroups.value.length).toBe(1);
      expect(messageGroups.value[0]?.type).toBe(MessageRole.User);
    });
  });

  describe('Tool 消息关联', () => {
    it('Tool 消息应该关联到对应的 AssistantMessage', async () => {
      const toolCallId = 'tc-1';
      const messages: Message[] = [
        createAssistantMessage('1', 'let me help', {
          toolCalls: [
            { id: toolCallId, type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } },
          ],
        }),
        createToolMessage('2', toolCallId),
      ];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(messageGroups.value.length).toBe(1);
      expect(messageGroups.value[0]?.type).toBe(MessageRole.Assistant);
      const assistant = messageGroups.value[0]?.messages[0] as AssistantMessage;
      expect(assistant.toolCalls?.[0]?.toolMessage?.id).toBe('2');
      expect(assistant.status).toBe(MessageStatus.Complete);
    });

    it('Tool 消息 error 为真时应将关联的 AssistantMessage status 设为 Error', async () => {
      const toolCallId = 'tc-err';
      const toolMessage = createToolMessage('2', toolCallId);
      toolMessage.error = 'tool failed';
      const messages: Message[] = [
        createAssistantMessage('1', 'calling tool', {
          status: MessageStatus.Streaming,
          toolCalls: [
            { id: toolCallId, type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } },
          ],
        }),
        toolMessage,
      ];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      const assistant = messageGroups.value[0]?.messages[0] as AssistantMessage;
      expect(assistant.toolCalls?.[0]?.toolMessage?.error).toBe('tool failed');
      expect(assistant.status).toBe(MessageStatus.Error);
    });

    it('Tool 成功且 Assistant status 为空时应兜底为 Complete', async () => {
      const toolCallId = 'tc-empty-status';
      const messages: Message[] = [
        createAssistantMessage('1', 'calling tool', {
          status: '' as MessageStatus,
          toolCalls: [
            { id: toolCallId, type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } },
          ],
        }),
        createToolMessage('2', toolCallId),
      ];
      const { messageGroups } = setupMessageGroup(messages);
      await nextTick();

      const assistant = messageGroups.value[0]?.messages[0] as AssistantMessage;
      expect(assistant.status).toBe(MessageStatus.Complete);
    });
  });

  describe('pause 标记', () => {
    it('包含 pause 的助手消息组应该标记 pause', async () => {
      const pausedMessage: AssistantMessage = {
        ...createAssistantMessage('1'),
        property: { extra: { pause: true } },
      };
      const { messageGroups } = setupMessageGroup([pausedMessage]);
      await nextTick();

      expect(messageGroups.value[0]?.pause).toBe(true);
    });
  });

  describe('executionGroups', () => {
    it('应该过滤出包含执行消息的组', async () => {
      const messages: Message[] = [
        createAssistantMessage('1', 'thinking', {
          toolCalls: [{ id: 'tc1', type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } }],
        }),
        createToolMessage('2', 'tc1'),
        createUserMessage('3'),
        createAssistantMessage('4', 'plain response'),
      ];
      const { executionGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(executionGroups.value.length).toBeGreaterThan(0);
    });

    it('无执行消息时应该返回空', async () => {
      const messages: Message[] = [createUserMessage('1'), createAssistantMessage('2', 'plain response')];
      const { executionGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(executionGroups.value.length).toBe(0);
    });

    it('应从前一组用户消息中提取 userMessageTitle', async () => {
      const messages: Message[] = [
        createUserMessage('1', '帮我分析 Trace 数据'),
        createAssistantMessage('2', 'thinking', {
          toolCalls: [{ id: 'tc1', type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } }],
        }),
        createToolMessage('3', 'tc1'),
      ];
      const { executionGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(executionGroups.value.length).toBeGreaterThan(0);
      expect(executionGroups.value[0]?.userMessageTitle).toBe('帮我分析 Trace 数据');
    });

    it('无前置用户消息时 userMessageTitle 应为数字时间戳', async () => {
      const messages: Message[] = [
        createAssistantMessage('1', 'thinking', {
          toolCalls: [{ id: 'tc1', type: MessageContentType.Function, function: { name: 'search', arguments: '{}' } }],
        }),
        createToolMessage('2', 'tc1'),
      ];
      const { executionGroups } = setupMessageGroup(messages);
      await nextTick();

      expect(executionGroups.value.length).toBeGreaterThan(0);
      expect(typeof executionGroups.value[0]?.userMessageTitle).toBe('number');
    });
  });

  describe('sessionArtifacts', () => {
    it('无文件产物时应返回空数组', async () => {
      const { sessionArtifacts } = setupMessageGroup([createAssistantMessage('1', 'plain')]);
      await nextTick();

      expect(sessionArtifacts.value).toEqual([]);
    });

    it('应拍平所有 AssistantMessage 的 artifacts，并以 outputId 为唯一键', async () => {
      const messages: Message[] = [
        createAssistantMessage('a1', 'with files', {
          uid: 'msg-a',
          property: { artifacts: [createFile({ outputId: 'o1' }), createFile({ outputId: 'o2' })] },
        }),
        createUserMessage('u1'),
        createAssistantMessage('a2', 'more files', {
          uid: 'msg-b',
          property: { artifacts: [createFile({ outputId: 'o3' })] },
        }),
      ];
      const { sessionArtifacts } = setupMessageGroup(messages);
      await nextTick();

      expect(sessionArtifacts.value.map(item => item.outputId)).toEqual(['o1', 'o2', 'o3']);
    });

    it('相同 outputId 应去重并保留最后一次出现（含相对顺序）', async () => {
      const first = createFile({ name: '旧名.pdf', outputId: 'dup', size: 1 });
      const middle = createFile({ outputId: 'keep' });
      const last = createFile({ name: '新名.pdf', outputId: 'dup', size: 99 });
      const messages: Message[] = [
        createAssistantMessage('a1', 'first', {
          property: { artifacts: [first, middle] },
        }),
        createAssistantMessage('a2', 'later', {
          property: { artifacts: [last] },
        }),
      ];
      const { sessionArtifacts } = setupMessageGroup(messages);
      await nextTick();

      expect(sessionArtifacts.value.map(item => item.outputId)).toEqual(['keep', 'dup']);
      expect(sessionArtifacts.value[1]).toMatchObject({ name: '新名.pdf', outputId: 'dup', size: 99 });
    });

    it('仅统计 AssistantMessage 的 artifacts，忽略其它角色', async () => {
      const messages: Message[] = [
        createAssistantMessage('a1', 'files', {
          uid: 'msg-a',
          property: { artifacts: [createFile({ outputId: 'o1' })] },
        }),
      ];
      const { sessionArtifacts } = setupMessageGroup(messages);
      await nextTick();

      expect(sessionArtifacts.value.length).toBe(1);
    });
  });

  describe('待审批单统计', () => {
    it('应统计 pending 与 draft 的 AI Dev 工具审批中断数量', async () => {
      const messages = [
        createApprovalInterruptMessage('pending-1', APPROVAL_STATUS.PENDING),
        createApprovalInterruptMessage('draft-1', APPROVAL_STATUS.DRAFT),
        createApprovalInterruptMessage('revoked-1', APPROVAL_STATUS.REVOKED),
      ];
      const { pendingApprovalCount, pendingApprovalTipText } = setupMessageGroup(messages);
      await nextTick();

      expect(pendingApprovalCount.value).toBe(2);
      expect(pendingApprovalTipText.value).toBe('当前会话有 2 个待审批单，如需继续，请先取消审批');
    });

    it('无待审批单时应返回空提示文案', async () => {
      const messages = [
        createApprovalInterruptMessage('approved-1', APPROVAL_STATUS.APPROVED),
        createAssistantMessage('assistant-1', 'done'),
      ];
      const { pendingApprovalCount, pendingApprovalTipText } = setupMessageGroup(messages);
      await nextTick();

      expect(pendingApprovalCount.value).toBe(0);
      expect(pendingApprovalTipText.value).toBe('');
    });
  });

  describe('分享模式', () => {
    it('isShareMode 初始应为 false', async () => {
      const { isShareMode } = setupMessageGroup([]);
      expect(isShareMode.value).toBe(false);
    });

    it('onToggleShareAll(true) 应该选中所有用户消息', async () => {
      const messages = [
        createUserMessage('1'),
        createAssistantMessage('2'),
        createUserMessage('3'),
        createAssistantMessage('4'),
      ];
      const { onToggleShareAll, selectedUserMessages } = setupMessageGroup(messages);
      await nextTick();

      onToggleShareAll(true);

      expect(selectedUserMessages.value?.length).toBe(2);
      expect(selectedUserMessages.value?.every(m => m.role === MessageRole.User)).toBe(true);
    });

    it('onToggleShareAll(false) 应该清空选中', async () => {
      const messages = [createUserMessage('1'), createAssistantMessage('2')];
      const { onToggleShareAll, selectedUserMessages } = setupMessageGroup(messages);
      await nextTick();

      onToggleShareAll(true);
      expect(selectedUserMessages.value?.length).toBe(1);

      onToggleShareAll(false);
      expect(selectedUserMessages.value?.length).toBe(0);
    });

    it('onCancelShare 应该清空选中并关闭分享模式', async () => {
      const messages = [createUserMessage('1'), createAssistantMessage('2')];
      const { onCancelShare, isShareMode, selectedUserMessages } = setupMessageGroup(messages);
      await nextTick();

      isShareMode.value = true;
      onCancelShare();

      expect(selectedUserMessages.value?.length).toBe(0);
      expect(isShareMode.value).toBe(false);
    });

    it('onConfirmShare 应该返回选中的用户消息', async () => {
      const messages = [
        createUserMessage('1'),
        createAssistantMessage('2'),
        createUserMessage('3'),
        createAssistantMessage('4'),
      ];
      const { onToggleShareAll, onConfirmShare } = setupMessageGroup(messages);
      await nextTick();

      onToggleShareAll(true);
      await nextTick();
      await nextTick();

      const result = onConfirmShare();
      expect(result.length).toBe(2);
      expect(result.every(m => m.role === MessageRole.User)).toBe(true);
    });
  });

  describe('isAllSelected', () => {
    it('所有用户消息组选中时应为 true', async () => {
      const messages = [createUserMessage('1'), createAssistantMessage('2')];
      const { onToggleShareAll, isAllSelected } = setupMessageGroup(messages);
      await nextTick();

      onToggleShareAll(true);
      await nextTick();
      await nextTick();

      expect(isAllSelected.value).toBe(true);
    });

    it('未全选时应为 false', async () => {
      const messages = [
        createUserMessage('1'),
        createAssistantMessage('2'),
        createUserMessage('3'),
        createAssistantMessage('4'),
      ];
      const { isAllSelected } = setupMessageGroup(messages);
      await nextTick();

      expect(isAllSelected.value).toBe(false);
    });
  });

  describe('selectedUserMessages 双向同步', () => {
    it('更新 selectedUserMessages 应同步 group.checked', async () => {
      const user1 = createUserMessage('1');
      const messages = [user1, createAssistantMessage('2')];
      const { messageGroups, selectedUserMessages } = setupMessageGroup(messages);
      await nextTick();

      selectedUserMessages.value = [user1];
      await nextTick();
      await nextTick();

      expect(messageGroups.value[0]?.checked).toBe(true);
      expect(messageGroups.value[1]?.checked).toBe(true);
    });
  });
});
