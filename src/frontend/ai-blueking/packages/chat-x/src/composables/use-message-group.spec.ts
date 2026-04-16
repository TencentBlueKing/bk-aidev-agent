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

import { MessageContentType, MessageRole, MessageStatus } from '../ag-ui/types';
import { LOADING_MESSAGE_ID } from '../common/constants';
import { useMessageGroup } from './use-message-group';

import type { AssistantMessage, Message, ToolMessage, UserMessage } from '../ag-ui/types';

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

const createToolMessage = (id: string, toolCallId: string, content = 'result'): ToolMessage => ({
  id,
  content,
  messageId: id,
  role: MessageRole.Tool,
  status: MessageStatus.Complete,
  toolCallId,
  duration: 100,
});

const setupMessageGroup = (messages: Message[], keyword = '') => {
  const messagesRef = computed(() => messages);
  const selectedUserMessages = deepRef<Message[] | undefined>([]);
  const keywordRef = shallowRef(keyword);

  const result = useMessageGroup({
    keyword: keywordRef,
    messages: messagesRef,
    selectedUserMessages,
  });

  return { ...result, selectedUserMessages, keywordRef, messagesRef };
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
