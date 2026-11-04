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
import { nextTick } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { type Message, MessageRole, MessageStatus } from '../../../ag-ui/types';
import MessageMinimap from './message-minimap.vue';

import type { MessageGroup } from '../../../composables/use-message-group';

const tippyMock = vi.hoisted(() => {
  const instance = {
    destroy: vi.fn(),
    hide: vi.fn(),
    popperInstance: { update: vi.fn() },
    show: vi.fn(),
  };
  return { instance, factory: vi.fn((_target: Element, _options: Record<string, unknown>) => instance) };
});

vi.mock('tippy.js', () => ({ default: tippyMock.factory }));

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// 测试只关心 entries 中的可见性与目标元素
type ObserverStub = { callback: (entries: Pick<IntersectionObserverEntry, 'isIntersecting' | 'target'>[]) => void };
let observers: ObserverStub[] = [];

beforeEach(() => {
  observers = [];
  tippyMock.factory.mockClear();
  Object.values(tippyMock.instance).forEach(fn => typeof fn === 'function' && fn.mockClear());
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      disconnect = vi.fn();
      observe = vi.fn();
      unobserve = vi.fn();
      constructor(callback: IntersectionObserverCallback) {
        observers.push({ callback: callback as unknown as ObserverStub['callback'] });
      }
    },
  );
  vi.stubGlobal(
    'ResizeObserver',
    class {
      disconnect = vi.fn();
      observe = vi.fn();
      unobserve = vi.fn();
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const createMessage = (role: MessageRole, content: unknown) => {
  const message = { id: `${role}-${Math.random()}`, messageId: '', role, content, status: MessageStatus.Complete };
  return message as Message;
};

const createGroup = (uid: string, type: MessageRole, messages: Message[]): MessageGroup => ({
  checked: false,
  isHover: false,
  messages,
  type,
  uid,
});

/** count 轮问答；withoutAnswer 中的轮次只有提问 */
const createGroups = (count: number, withoutAnswer: number[] = []) =>
  Array.from({ length: count }).flatMap((_, index) => {
    const user = createGroup(`user-${index}`, MessageRole.User, [createMessage(MessageRole.User, `问题 ${index}`)]);
    if (withoutAnswer.includes(index)) return [user];
    return [
      user,
      createGroup(`answer-${index}`, MessageRole.Assistant, [
        createMessage(MessageRole.Assistant, `**回答** ${index}`),
      ]),
    ];
  });

const createContainer = (groups: MessageGroup[], clientHeight = 600) => {
  const container = document.createElement('div');
  Object.defineProperty(container, 'clientHeight', { configurable: true, value: clientHeight });
  for (const group of groups) {
    const element = document.createElement('div');
    element.dataset.messageGroupId = group.uid;
    container.appendChild(element);
  }
  return container;
};

let wrapper: undefined | VueWrapper;

const mountMinimap = async (groups: MessageGroup[], container = createContainer(groups)) => {
  wrapper = mount(MessageMinimap, {
    attachTo: document.body,
    props: { container, messageGroups: groups },
  });
  await nextTick();
  await nextTick();
  return { container, wrapper };
};

const lineWidths = (target: VueWrapper) =>
  target.findAll('.ai-message-minimap-item-line').map(line => (line.element as HTMLElement).style.width);

afterEach(() => {
  wrapper?.unmount();
  wrapper = undefined;
});

describe('MessageMinimap', () => {
  describe('显示条件', () => {
    it('提问不超过 4 条时不渲染', async () => {
      const { wrapper } = await mountMinimap(createGroups(4));
      expect(wrapper.find('.ai-message-minimap').exists()).toBe(false);
    });

    it('提问超过 4 条时渲染，刻度数等于提问数', async () => {
      const { wrapper } = await mountMinimap(createGroups(5, [4]));
      expect(wrapper.find('.ai-message-minimap').exists()).toBe(true);
      expect(wrapper.findAll('.ai-message-minimap-item')).toHaveLength(5);
      expect(wrapper.find('nav').attributes('aria-label')).toBe('消息定位');
      expect(wrapper.findAll('.ai-message-minimap-item')[0].attributes('aria-label')).toBe('问题 0');
    });

    it('应把消息容器可视高度写入 CSS 变量，供垂直居中与最大高度使用', async () => {
      const groups = createGroups(5);
      const { wrapper } = await mountMinimap(groups, createContainer(groups, 480));
      const root = wrapper.find('.ai-message-minimap').element as HTMLElement;
      expect(root.style.getPropertyValue('--ai-message-minimap-viewport-height')).toBe('480px');
    });
  });

  describe('贴主栏左侧', () => {
    const rect = (left: number) =>
      ({
        bottom: 0,
        height: 0,
        left,
        right: 0,
        top: 0,
        width: 0,
        x: left,
        y: 0,
        toJSON() {
          return {};
        },
      }) as DOMRect;

    const mountInMain = async (gutter: number, offsetTop = 0) => {
      const groups = createGroups(5);
      const main = document.createElement('div');
      const container = createContainer(groups);
      Object.defineProperty(container, 'offsetTop', { configurable: true, value: offsetTop });
      main.appendChild(container);
      document.body.appendChild(main);
      vi.spyOn(main, 'getBoundingClientRect').mockReturnValue(rect(0));
      vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(rect(gutter));
      const mounted = await mountMinimap(groups, container);
      return { ...mounted, main };
    };

    it('刻度会压到消息列时标记遮罩，并记下消息列左缘', async () => {
      const { main, wrapper } = await mountInMain(10, 12);
      const root = wrapper.find('.ai-message-minimap').element as HTMLElement;
      expect(root.classList.contains('is-overlap')).toBe(true);
      expect(root.style.getPropertyValue('--ai-message-minimap-mask-left')).toBe('10px');
      expect(root.style.getPropertyValue('--ai-message-minimap-top')).toBe('12px');
      main.remove();
    });

    it('左侧空白够宽时不遮消息', async () => {
      const { main, wrapper } = await mountInMain(120);
      const root = wrapper.find('.ai-message-minimap').element as HTMLElement;
      expect(root.classList.contains('is-overlap')).toBe(false);
      expect(root.style.getPropertyValue('--ai-message-minimap-mask-left')).toBe('120px');
      main.remove();
    });
  });

  describe('可视区高亮', () => {
    it('观察器回调后，可见轮次的刻度应加 is-active', async () => {
      const groups = createGroups(5);
      const { container, wrapper } = await mountMinimap(groups);
      const target = container.children[3]; // answer-1
      observers.at(-1)?.callback([{ isIntersecting: true, target }]);
      await nextTick();
      const items = wrapper.findAll('.ai-message-minimap-item');
      expect(items[1].classes()).toContain('is-active');
      expect(items.filter(item => item.classes().includes('is-active'))).toHaveLength(1);
    });

    it('hover 时只高亮当前刻度，离开后恢复视口高亮', async () => {
      const groups = createGroups(5);
      const { container, wrapper } = await mountMinimap(groups);
      observers.at(-1)?.callback([{ isIntersecting: true, target: container.children[0] }]);
      await nextTick();
      const items = wrapper.findAll('.ai-message-minimap-item');
      expect(items[0].classes()).toContain('is-active');

      await items[2].trigger('mouseenter');
      expect(items[2].classes()).toContain('is-hover');
      expect(items.some(item => item.classes().includes('is-active'))).toBe(false);

      await wrapper.find('nav').trigger('mouseleave');
      expect(items[0].classes()).toContain('is-active');
      expect(items.some(item => item.classes().includes('is-hover'))).toBe(false);
    });
  });

  describe('hover 预览', () => {
    it('hover 刻度时按距离呈鱼眼宽度，离开后恢复 6px', async () => {
      const { wrapper } = await mountMinimap(createGroups(9));
      const items = wrapper.findAll('.ai-message-minimap-item');
      await items[4].trigger('mouseenter');
      expect(wrapper.find('.ai-message-minimap').classes()).toContain('is-hover');
      expect(items[4].classes()).toContain('is-hover');
      expect(lineWidths(wrapper)).toEqual(['6px', '12px', '18px', '24px', '30px', '24px', '18px', '12px', '6px']);
      await wrapper.find('nav').trigger('mouseleave');
      expect(wrapper.find('.ai-message-minimap').classes()).not.toContain('is-hover');
      expect(lineWidths(wrapper).every(width => width === '6px')).toBe(true);
      expect(tippyMock.instance.hide).toHaveBeenCalled();
    });

    it('有回答时预览展示提问与纯文本回答', async () => {
      const { wrapper } = await mountMinimap(createGroups(5));
      await wrapper.findAll('.ai-message-minimap-item')[2].trigger('mouseenter');
      await nextTick();
      expect(tippyMock.factory).toHaveBeenCalledTimes(1);
      const options = tippyMock.factory.mock.calls[0][1];
      expect(options).toMatchObject({ placement: 'right', trigger: 'manual', maxWidth: 'none' });
      const content = options.content as HTMLElement;
      expect(content.querySelector('.ai-message-minimap-preview-question')?.textContent).toBe('问题 2');
      expect(content.querySelector('.ai-message-minimap-preview-answer')?.textContent?.trim()).toBe('回答 2');
      expect(tippyMock.instance.show).toHaveBeenCalled();
    });

    it('没有回答时预览只展示提问', async () => {
      const { wrapper } = await mountMinimap(createGroups(5, [1]));
      await wrapper.findAll('.ai-message-minimap-item')[1].trigger('mouseenter');
      await nextTick();
      const content = tippyMock.factory.mock.calls[0][1].content as HTMLElement;
      expect(content.querySelector('.ai-message-minimap-preview-question')?.textContent).toBe('问题 1');
      expect(content.querySelector('.ai-message-minimap-preview-answer')).toBeNull();
    });

    it('卸载时销毁预览浮层', async () => {
      const { wrapper: current } = await mountMinimap(createGroups(5));
      await current.findAll('.ai-message-minimap-item')[0].trigger('mouseenter');
      await nextTick();
      current.unmount();
      wrapper = undefined;
      expect(tippyMock.instance.destroy).toHaveBeenCalled();
    });
  });

  describe('滚轮', () => {
    const wheelOnMinimap = (target: VueWrapper, deltaY: number, deltaMode = WheelEvent.DOM_DELTA_PIXEL) => {
      const event = new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaMode, deltaY });
      target.find('.ai-message-minimap').element.dispatchEvent(event);
      return event;
    };

    it('滚轮应被拦截，消息区不会收到冒泡', async () => {
      const { wrapper } = await mountMinimap(createGroups(5));
      const event = wheelOnMinimap(wrapper, 40);
      expect(event.defaultPrevented).toBe(true);
      expect(event.cancelBubble).toBe(true);
    });

    it('刻度超出定位器高度时，滚轮只滚动定位器列表', async () => {
      const { wrapper } = await mountMinimap(createGroups(9));
      const list = wrapper.find('nav').element as HTMLElement;
      Object.defineProperty(list, 'clientHeight', { configurable: true, value: 24 });
      Object.defineProperty(list, 'scrollHeight', { configurable: true, value: 72 });

      wheelOnMinimap(wrapper, 30);
      expect(list.scrollTop).toBe(30);

      wheelOnMinimap(wrapper, 1, WheelEvent.DOM_DELTA_LINE);
      expect(list.scrollTop).toBe(46);

      wheelOnMinimap(wrapper, 100);
      expect(list.scrollTop).toBe(48);
    });

    it('刻度未超出时不滚动定位器列表', async () => {
      const { wrapper } = await mountMinimap(createGroups(5));
      const list = wrapper.find('nav').element as HTMLElement;
      Object.defineProperty(list, 'clientHeight', { configurable: true, value: 80 });
      Object.defineProperty(list, 'scrollHeight', { configurable: true, value: 40 });

      wheelOnMinimap(wrapper, 30);
      expect(list.scrollTop).toBe(0);
    });
  });

  describe('点击定位', () => {
    it('点击刻度应抛出对应提问组的 uid', async () => {
      const { wrapper } = await mountMinimap(createGroups(5));
      await wrapper.findAll('.ai-message-minimap-item')[3].trigger('click');
      expect(wrapper.emitted('locate')?.[0]).toEqual(['user-3']);
    });
  });

  describe('首尾渐隐', () => {
    it('列表可滚动时在还有内容的一端渐隐，未超出时不渐隐', async () => {
      const { wrapper } = await mountMinimap(createGroups(5));
      const nav = wrapper.find('nav');
      expect(nav.classes()).not.toContain('is-fade-top');
      expect(nav.classes()).not.toContain('is-fade-bottom');

      const list = nav.element as HTMLElement;
      Object.defineProperty(list, 'clientHeight', { configurable: true, value: 20 });
      Object.defineProperty(list, 'scrollHeight', { configurable: true, value: 40 });
      list.scrollTop = 10;
      await nav.trigger('scroll');
      expect(nav.classes()).toContain('is-fade-top');
      expect(nav.classes()).toContain('is-fade-bottom');

      list.scrollTop = 20;
      await nav.trigger('scroll');
      expect(nav.classes()).toContain('is-fade-top');
      expect(nav.classes()).not.toContain('is-fade-bottom');
    });
  });
});
