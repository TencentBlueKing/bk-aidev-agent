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
import { defineComponent, h, nextTick, shallowRef } from 'vue';

import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { type Message, MessageContentType, MessageRole, MessageStatus } from '../ag-ui/types';
import {
  MESSAGE_MINIMAP_PREVIEW_LIMIT,
  findMessageGroupElement,
  getAnswerText,
  getQuestionText,
  resolveMinimapRounds,
  useMessageMinimap,
} from './use-message-minimap';

import type { MessageGroup } from './use-message-group';

type IntersectEntry = Pick<IntersectionObserverEntry, 'isIntersecting' | 'target'>;

type ObserverStub = {
  // 测试只关心 entries 中的可见性与目标元素
  callback: (entries: IntersectEntry[]) => void;
  disconnect: ReturnType<typeof vi.fn>;
  observed: Element[];
  options?: IntersectionObserverInit;
};

let observers: ObserverStub[] = [];

beforeEach(() => {
  observers = [];
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      stub: ObserverStub;
      unobserve = vi.fn();
      constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
        this.stub = {
          callback: callback as unknown as ObserverStub['callback'],
          disconnect: vi.fn(),
          observed: [],
          options,
        };
        observers.push(this.stub);
      }
      disconnect() {
        this.stub.disconnect();
      }
      observe(element: Element) {
        this.stub.observed.push(element);
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const createMessage = (role: MessageRole, content: unknown, extra: Partial<Message> = {}) => {
  const message = {
    id: `${role}-${Math.random()}`,
    messageId: `${role}-${Math.random()}`,
    role,
    content,
    status: MessageStatus.Complete,
    ...extra,
  };
  return message as Message;
};

const createGroup = (uid: string, type: MessageRole, messages: Message[] = []): MessageGroup => ({
  checked: false,
  isHover: false,
  messages,
  type,
  uid,
});

/** 生成 count 轮「提问 + 回答」消息组 */
const createRoundGroups = (count: number) =>
  Array.from({ length: count }).flatMap((_, index) => [
    createGroup(`user-${index}`, MessageRole.User, [createMessage(MessageRole.User, `问题 ${index}`)]),
    createGroup(`answer-${index}`, MessageRole.Assistant, [createMessage(MessageRole.Assistant, `回答 ${index}`)]),
  ]);

/** 按消息组创建容器子节点，模拟 MessageContainer 输出的 data-message-group-id */
const createContainer = (groups: MessageGroup[]) => {
  const container = document.createElement('div');
  for (const group of groups) {
    const element = document.createElement('div');
    element.dataset.messageGroupId = group.uid;
    container.appendChild(element);
  }
  return container;
};

const mountMinimap = (groups: MessageGroup[], container: HTMLElement | null) => {
  const groupsRef = shallowRef(groups);
  const containerRef = shallowRef<HTMLElement | null>(container);
  let result: ReturnType<typeof useMessageMinimap> | undefined;
  const wrapper = mount(
    defineComponent({
      setup() {
        result = useMessageMinimap({ container: containerRef, messageGroups: groupsRef });
        return () => h('div');
      },
    }),
  );
  return { containerRef, groupsRef, result: result!, wrapper };
};

const triggerIntersect = (observer: ObserverStub, entries: IntersectEntry[]) => {
  observer.callback(entries);
};

describe('use-message-minimap', () => {
  describe('resolveMinimapRounds', () => {
    it('用户提问组应与紧随其后的助手组配对', () => {
      const groups = createRoundGroups(2);
      const rounds = resolveMinimapRounds(groups);
      expect(rounds).toHaveLength(2);
      expect(rounds[0].userGroup.uid).toBe('user-0');
      expect(rounds[0].answerGroup?.uid).toBe('answer-0');
      expect(rounds[1].answerGroup?.uid).toBe('answer-1');
    });

    it('提问后是 Loading 组或没有下一组时，应视为没有回答', () => {
      const rounds = resolveMinimapRounds([
        createGroup('user-0', MessageRole.User),
        createGroup('loading', MessageRole.Loading),
        createGroup('user-1', MessageRole.User),
      ]);
      expect(rounds).toHaveLength(2);
      expect(rounds[0].answerGroup).toBeUndefined();
      expect(rounds[1].answerGroup).toBeUndefined();
    });

    it('开头的助手组不单独成轮', () => {
      const rounds = resolveMinimapRounds([
        createGroup('info', MessageRole.Assistant),
        createGroup('user-0', MessageRole.User),
      ]);
      expect(rounds.map(round => round.userGroup.uid)).toEqual(['user-0']);
    });
  });

  describe('getQuestionText', () => {
    it('字符串内容应折叠空白后返回', () => {
      expect(getQuestionText(createMessage(MessageRole.User, '  深圳\n\n今日天气  '))).toBe('深圳 今日天气');
    });

    it('多模态内容只取文本片段', () => {
      const message = createMessage(MessageRole.User, [
        { type: MessageContentType.Text, text: '看看这张图' },
        { type: MessageContentType.Binary, mimeType: 'image/png', url: 'a.png' },
        { type: MessageContentType.Text, text: '是什么' },
      ]);
      expect(getQuestionText(message)).toBe('看看这张图 是什么');
    });

    it('非用户消息或缺失时返回空字符串', () => {
      expect(getQuestionText(createMessage(MessageRole.Assistant, '回答'))).toBe('');
      expect(getQuestionText(undefined)).toBe('');
    });
  });

  describe('getAnswerText', () => {
    it('应去掉 markdown 标记，只保留行内文字与行内代码', () => {
      const text = getAnswerText([
        createMessage(MessageRole.Assistant, '# 标题\n\n**加粗**和[链接](https://example.com)\n\n- 列表 `code`'),
      ]);
      expect(text).toBe('标题 加粗和链接 列表 code');
    });

    it('应跳过代码块与图片', () => {
      const text = getAnswerText([createMessage(MessageRole.Assistant, '```ts\nconst a = 1;\n```\n\n![图](a.png)')]);
      expect(text).toBe('');
    });

    it('与消息渲染一致不解析 HTML，原始标签按文字保留', () => {
      expect(getAnswerText([createMessage(MessageRole.Assistant, '<b>说明</b>')])).toBe('<b>说明</b>');
    });

    it('只统计 assistant 消息，reasoning / activity 不参与', () => {
      const text = getAnswerText([
        createMessage(MessageRole.Reasoning, ['思考中']),
        createMessage(MessageRole.Activity, { content: '活动' }),
        createMessage(MessageRole.Assistant, '最终回答'),
      ]);
      expect(text).toBe('最终回答');
    });

    it('没有可提取文字时返回空字符串', () => {
      expect(getAnswerText([createMessage(MessageRole.Activity, { content: '流程' })])).toBe('');
      expect(getAnswerText(undefined)).toBe('');
    });

    it('超长回答应截断到预览长度', () => {
      const text = getAnswerText([createMessage(MessageRole.Assistant, '字'.repeat(MESSAGE_MINIMAP_PREVIEW_LIMIT * 2))]);
      expect(text).toHaveLength(MESSAGE_MINIMAP_PREVIEW_LIMIT);
    });
  });

  describe('findMessageGroupElement', () => {
    it('应按 uid 在容器子节点中查找消息组', () => {
      const groups = createRoundGroups(1);
      const container = createContainer(groups);
      expect(findMessageGroupElement(container, 'answer-0')).toBe(container.children[1]);
      expect(findMessageGroupElement(container, 'missing')).toBeUndefined();
      expect(findMessageGroupElement(null, 'answer-0')).toBeUndefined();
    });

    it('消息组包在问答轮次 wrapper 内时也应能找到', () => {
      const container = document.createElement('div');
      const turn = document.createElement('div');
      const element = document.createElement('div');
      element.dataset.messageGroupId = 'answer-0';
      turn.appendChild(element);
      container.appendChild(turn);
      expect(findMessageGroupElement(container, 'answer-0')).toBe(element);
    });
  });

  describe('useMessageMinimap', () => {
    it('提问不超过 4 条时不展示，也不创建观察器', async () => {
      const groups = createRoundGroups(4);
      const { result, wrapper } = mountMinimap(groups, createContainer(groups));
      await nextTick();
      expect(result.rounds.value).toHaveLength(4);
      expect(result.visible.value).toBe(false);
      expect(observers).toHaveLength(0);
      wrapper.unmount();
    });

    it('提问超过 4 条时展示，并以容器为 root 观察每轮的提问组与回答组', async () => {
      const groups = createRoundGroups(5);
      const container = createContainer(groups);
      const { result, wrapper } = mountMinimap(groups, container);
      await nextTick();
      expect(result.visible.value).toBe(true);
      expect(observers).toHaveLength(1);
      expect(observers[0].options?.root).toBe(container);
      expect(observers[0].observed).toHaveLength(10);
      wrapper.unmount();
    });

    it('提问组或回答组进入可视区时，对应轮次应高亮；离开后取消', async () => {
      const groups = createRoundGroups(5);
      const container = createContainer(groups);
      const { result, wrapper } = mountMinimap(groups, container);
      await nextTick();
      const [observer] = observers;
      triggerIntersect(observer, [
        { isIntersecting: true, target: findMessageGroupElement(container, 'answer-1')! },
        { isIntersecting: true, target: findMessageGroupElement(container, 'user-2')! },
      ]);
      expect(result.activeIndexes.value).toEqual([1, 2]);
      triggerIntersect(observer, [{ isIntersecting: false, target: findMessageGroupElement(container, 'answer-1')! }]);
      expect(result.activeIndexes.value).toEqual([2]);
      wrapper.unmount();
    });

    it('消息组变化后应断开旧观察器并重新观察', async () => {
      const groups = createRoundGroups(5);
      const { containerRef, groupsRef, wrapper } = mountMinimap(groups, createContainer(groups));
      await nextTick();
      const nextGroups = createRoundGroups(6);
      containerRef.value = createContainer(nextGroups);
      groupsRef.value = nextGroups;
      await nextTick();
      expect(observers[0].disconnect).toHaveBeenCalled();
      expect(observers.at(-1)?.observed).toHaveLength(12);
      wrapper.unmount();
    });

    it('没有容器时不创建观察器，卸载时断开观察器', async () => {
      const groups = createRoundGroups(5);
      const { containerRef, wrapper } = mountMinimap(groups, null);
      await nextTick();
      expect(observers).toHaveLength(0);
      containerRef.value = createContainer(groups);
      await nextTick();
      expect(observers).toHaveLength(1);
      wrapper.unmount();
      expect(observers[0].disconnect).toHaveBeenCalled();
    });
  });
});
