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
import { type MaybeRefOrGetter, computed, onScopeDispose, shallowRef, toValue, watch } from 'vue';

import { type Message, MessageContentType, MessageRole } from '../ag-ui/types';
import MarkdownIt from '../markdown-it/index';

import type { Token } from '../markdown-it';
import type { MessageGroup } from './use-message-group';

/** 提问超过 4 条才展示定位器 */
export const MESSAGE_MINIMAP_MIN_ROUNDS = 5;
/** 预览只展示两行，提取到这个长度即可停止解析 */
export const MESSAGE_MINIMAP_PREVIEW_LIMIT = 300;

/** 一轮问答：用户提问组 + 紧随其后的助手组（没有回答或仍在等待时为空） */
export type MessageMinimapRound = {
  answerGroup?: MessageGroup;
  userGroup: MessageGroup;
};

const normalizeText = (text: string) => text.replace(/\s+/g, ' ').trim();

const createPlainTextParser = () => new MarkdownIt();
let plainTextParser: ReturnType<typeof createPlainTextParser> | undefined;

/** 只收集行内文字与行内代码，图片不算可提取的文字；与消息渲染一致不启用 HTML，原始标签按文字保留 */
const collectInlineText = (tokens: Token[]) =>
  tokens
    .map(token => {
      if (token.type === 'text' || token.type === 'code_inline') return token.content;
      if (token.type === 'softbreak' || token.type === 'hardbreak') return ' ';
      return '';
    })
    .join('');

/**
 * 从消息组列表配对出问答轮次，Loading 组不算回答
 */
export const resolveMinimapRounds = (groups: MessageGroup[] = []): MessageMinimapRound[] =>
  groups.reduce<MessageMinimapRound[]>((rounds, group, index) => {
    if (group.type !== MessageRole.User) return rounds;
    const nextGroup = groups[index + 1];
    rounds.push({
      userGroup: group,
      answerGroup: nextGroup?.type === MessageRole.Assistant ? nextGroup : undefined,
    });
    return rounds;
  }, []);

/**
 * 提问的纯文本：字符串内容原样使用，多模态内容只取文本片段
 */
export const getQuestionText = (message?: Message): string => {
  if (message?.role !== MessageRole.User) return '';
  const { content } = message;
  if (typeof content === 'string') return normalizeText(content);
  if (!Array.isArray(content)) return '';
  return normalizeText(content.map(item => (item.type === MessageContentType.Text ? item.text : '')).join(' '));
};

/**
 * 回答的纯文本：只取 assistant 消息的 markdown 正文，跳过代码块与图片；
 * reasoning / tool / activity 等过程消息不参与。没有可提取的文字时返回空字符串
 */
export const getAnswerText = (messages: Message[] = []): string => {
  const parts: string[] = [];
  let length = 0;
  for (const message of messages) {
    if (message.role !== MessageRole.Assistant || typeof message.content !== 'string' || !message.content.trim()) {
      continue;
    }
    plainTextParser ??= createPlainTextParser();
    for (const token of plainTextParser.parse(message.content, {})) {
      if (token.type !== 'inline' || !token.children) continue;
      const text = normalizeText(collectInlineText(token.children));
      if (!text) continue;
      parts.push(text);
      length += text.length;
      if (length >= MESSAGE_MINIMAP_PREVIEW_LIMIT) {
        return parts.join(' ').slice(0, MESSAGE_MINIMAP_PREVIEW_LIMIT);
      }
    }
  }
  return parts.join(' ');
};

/** 消息容器内所有消息组元素（消息组按问答轮次包在一层 wrapper 里，不一定是直接子节点） */
const getMessageGroupElements = (container: HTMLElement | null | undefined) =>
  Array.from(container?.querySelectorAll<HTMLElement>('[data-message-group-id]') ?? []);

/** 在消息容器内按 uid 找消息组元素 */
export const findMessageGroupElement = (container: HTMLElement | null | undefined, uid: string) =>
  getMessageGroupElements(container).find(element => element.dataset.messageGroupId === uid);

/**
 * 消息定位器的数据逻辑：配对问答轮次，并以消息容器为 root 计算哪些轮次出现在可视区
 */
export const useMessageMinimap = (options: {
  container: MaybeRefOrGetter<HTMLElement | null | undefined>;
  messageGroups: MaybeRefOrGetter<MessageGroup[]>;
}) => {
  const rounds = computed(() => resolveMinimapRounds(toValue(options.messageGroups)));
  const visible = computed(() => rounds.value.length >= MESSAGE_MINIMAP_MIN_ROUNDS);
  // 当前出现在可视区的轮次序号（提问组或回答组任意一个可见即算）
  const activeIndexes = shallowRef<number[]>([]);

  let observer: IntersectionObserver | null = null;
  const intersectingUids = new Set<string>();

  const updateActiveIndexes = () => {
    activeIndexes.value = rounds.value.reduce<number[]>((list, round, index) => {
      const answerUid = round.answerGroup?.uid;
      if (intersectingUids.has(round.userGroup.uid) || (answerUid && intersectingUids.has(answerUid))) {
        list.push(index);
      }
      return list;
    }, []);
  };

  const disconnect = () => {
    observer?.disconnect();
    observer = null;
    intersectingUids.clear();
  };

  // 消息组增删时 uid 会重新生成，需等 DOM 更新后重新观察
  watch(
    [() => toValue(options.container), rounds, visible],
    ([container, list, isVisible]) => {
      disconnect();
      if (!container || !isVisible) {
        activeIndexes.value = [];
        return;
      }
      observer = new IntersectionObserver(
        entries => {
          for (const entry of entries) {
            const uid = (entry.target as HTMLElement).dataset.messageGroupId;
            if (!uid) continue;
            if (entry.isIntersecting) {
              intersectingUids.add(uid);
            } else {
              intersectingUids.delete(uid);
            }
          }
          updateActiveIndexes();
        },
        { root: container },
      );
      const uids = new Set(list.flatMap(round => [round.userGroup.uid, round.answerGroup?.uid ?? '']));
      for (const element of getMessageGroupElements(container)) {
        if (uids.has(element.dataset.messageGroupId ?? '')) {
          observer.observe(element);
        }
      }
    },
    { immediate: true, flush: 'post' },
  );

  onScopeDispose(disconnect);

  return {
    activeIndexes,
    rounds,
    visible,
  };
};
