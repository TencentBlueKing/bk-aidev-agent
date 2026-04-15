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
import type { ComputedRef, Ref, ShallowRef } from 'vue';
import { computed, ref as deepRef, shallowRef, watch, watchEffect } from 'vue';

import {
  type ActivityMessage,
  type AssistantMessage,
  type Message,
  MessageContentType,
  MessageRole,
  MessageStatus,
} from '../ag-ui/types';
import { generateUUID } from '../utils';

import type { BkFlowMessageContent } from '../ag-ui/types/contents';

export type MessageGroup = {
  checked: boolean;
  isHover: boolean;
  messages: Message[];
  pause?: boolean;
  startTime?: number; // 执行时间
  type: MessageRole;
  uid: string;
  userMessageTitle?: number | string;
};

type SearchTextExtractor = (message: Message) => string[];

const SEARCH_TEXT_EXTRACTORS: Record<string, SearchTextExtractor> = {
  toolCall(message) {
    const { toolCalls } = message as AssistantMessage;
    if (!toolCalls?.length) return [];
    return toolCalls.flatMap(
      tc =>
        [tc.function.name, tc.function.mcpName, tc.function.description, tc.function.arguments, tc.id].filter(
          Boolean,
        ) as string[],
    );
  },
  [MessageContentType.FlowAgent](message) {
    const content = (message as ActivityMessage).content as BkFlowMessageContent;
    if (!content) return [];
    return [content.task_name, ...Object.values(content.nodes ?? {}).map(n => n.name)].filter(Boolean);
  },
};

const getMessageSearchKey = (message: Message): string | undefined => {
  if (message.role === MessageRole.Assistant && (message as AssistantMessage).toolCalls?.length) {
    return 'toolCall';
  }
  if (message.role === MessageRole.Activity) {
    return (message as ActivityMessage).activityType;
  }
  return undefined;
};

const isExecutionMessage = (m: Message): boolean => {
  return (
    (m.role === MessageRole.Assistant && !!(m as AssistantMessage).toolCalls?.length) ||
    (m.role === MessageRole.Activity && (m as ActivityMessage).activityType === MessageContentType.FlowAgent)
  );
};

const messageMatchesKeyword = (message: Message, keyword: string): boolean => {
  const key = getMessageSearchKey(message);
  if (!key) return true;
  const extractor = SEARCH_TEXT_EXTRACTORS[key];
  if (!extractor) return true;
  return extractor(message).some(text => text.toLowerCase().includes(keyword));
};

export const useMessageGroup = (options: {
  keyword?: ShallowRef<string>;
  messages: ComputedRef<Message[]>;
  selectedUserMessages: Ref<Message[] | undefined>;
}) => {
  const messageGroups = deepRef<MessageGroup[]>([]);
  /**
   * 是否为分享模式
   */
  const isShareMode = shallowRef(false);

  watchEffect(() => {
    let assistantMessages: Message[] = [];
    const list: MessageGroup[] = [];
    for (const message of options.messages.value) {
      if (!message?.uid) {
        message.uid = generateUUID();
      }
      if (message.role === MessageRole.User) {
        if (assistantMessages.length > 0) {
          list.push({
            messages: assistantMessages,
            type: MessageRole.Assistant,
            isHover: false,
            checked: false,
            uid: generateUUID(),
            pause: assistantMessages?.some(m => m.property?.extra?.pause) ?? false,
          });
          assistantMessages = [];
        }
        list.push({
          messages: [message],
          type: MessageRole.User,
          isHover: false,
          checked: false,
          uid: generateUUID(),
        });
        continue;
      }
      if (message.role === MessageRole.Tool) {
        const toolMessage = options.messages.value.find(
          m => m.role === MessageRole.Assistant && m.toolCalls?.some(t => t.id === message.toolCallId),
        ) as AssistantMessage | undefined;
        if (toolMessage) {
          const toolCall = toolMessage.toolCalls!.find(t => t.id === message.toolCallId)!;
          toolCall.toolMessage = message;
          toolMessage.status = message.error ? MessageStatus.Error : toolMessage.status || MessageStatus.Complete;
          continue;
        }
      }
      assistantMessages.push(message);
    }
    if (assistantMessages.length > 0) {
      list.push({
        messages: assistantMessages,
        type: MessageRole.Assistant,
        isHover: false,
        checked: false,
        uid: generateUUID(),
        pause: assistantMessages?.some(m => m.property?.extra?.pause) ?? false,
      });
    }
    if (options.messages.value.at(-1)?.role === MessageRole.User) {
      list.push({
        messages: [
          {
            role: MessageRole.Loading,
            content: '',
            status: MessageStatus.Pending,
            messageId: '',
            id: 'loading',
            uid: generateUUID(),
          },
        ],
        type: MessageRole.Loading,
        isHover: false,
        checked: false,
        uid: generateUUID(),
      });
    }
    messageGroups.value = list;
  });

  const executionGroups = computed<MessageGroup[]>(() => {
    const kw = options.keyword?.value?.trim().toLowerCase();
    const isMatch = (m: Message) => isExecutionMessage(m) && (!kw || messageMatchesKeyword(m, kw));

    return messageGroups.value
      .filter((group, index) => {
        if (group.messages.some(isMatch)) {
          const userGroup = messageGroups.value.at(index - 1);
          if (userGroup) {
            const userMessages = userGroup.messages.filter(m => m.role === MessageRole.User);
            if (userMessages?.length) {
              for (const item of userMessages) {
                const content = item.content;
                if (typeof content === 'string') {
                  group.userMessageTitle = content;
                  break;
                } else if (Array.isArray(content) && content.some(item => item.type === MessageContentType.Text)) {
                  group.userMessageTitle = content.filter(item => item.type === MessageContentType.Text)?.join('\n');
                  break;
                }
              }
            }
          }
          if (!group.userMessageTitle) {
            group.userMessageTitle = Date.now();
          }
          return true;
        }
        return false;
      })
      .map(group => ({
        ...group,
        isHover: false,
        messages: group.messages.filter(isMatch),
      }));
  });

  /**
   * 是否为全选
   */
  const isAllSelected = computed(() => {
    return messageGroups.value?.filter(group => group.type === MessageRole.User).every(group => group.checked);
  });

  /**
   * 切换全选
   * @param isAllSelected - 是否全选
   */
  const onToggleShareAll = (isAllSelected: boolean) => {
    options.selectedUserMessages.value = isAllSelected
      ? messageGroups.value
          ?.filter(group => group.type === MessageRole.User)
          .map(group => group.messages)
          .flat()
      : [];
  };
  /**
   * 取消分享
   */
  const onCancelShare = () => {
    options.selectedUserMessages.value = [];
    isShareMode.value = false;
  };

  /**
   * 确认分享
   * @returns 分享的消息
   */
  const onConfirmShare = () => {
    return (
      messageGroups.value
        ?.filter(group => group.checked && group.type === MessageRole.User)
        .map(group => group.messages)
        .flat() ?? []
    );
  };

  watch(
    options.selectedUserMessages,
    selectedList => {
      if (!messageGroups.value.length) return;
      for (const [index, group] of messageGroups.value.entries()) {
        if (group.type === MessageRole.Assistant) {
          continue;
        }
        const isChecked = selectedList?.some(m => group.messages.some(s => m.id === s.id)) ?? false;
        group.checked = isChecked;
        if (group.type === MessageRole.User) {
          const relatedGroup = messageGroups.value.at(index + 1);
          if (relatedGroup) {
            relatedGroup.checked = isChecked;
          }
        }
      }
    },
    {
      immediate: true,
      flush: 'post',
    },
  );

  return {
    messageGroups,
    executionGroups,
    isShareMode,
    isAllSelected,
    onToggleShareAll,
    onCancelShare,
    onConfirmShare,
  };
};
