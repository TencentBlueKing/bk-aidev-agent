import { afterEach, describe, expect, it, vi } from 'vitest';

import { resolveLocateScrollTop, scrollLocateTarget } from './locate-message-scroll';

const rect = (top: number): DOMRect =>
  ({
    top,
    bottom: top,
    left: 0,
    right: 0,
    width: 0,
    height: 0,
    x: 0,
    y: top,
    toJSON: () => ({}),
  }) as DOMRect;

describe('resolveLocateScrollTop', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  const mountTurn = () => {
    const container = document.createElement('div');
    container.className = 'ai-message-container';
    const turn = document.createElement('div');
    turn.className = 'ai-message-turn';
    const sticky = document.createElement('div');
    sticky.className = 'message-group is-sticky';
    const answer = document.createElement('div');
    answer.className = 'message-group';
    turn.append(sticky, answer);
    container.append(turn);
    document.body.append(container);
    Object.defineProperty(sticky, 'offsetHeight', { value: 40 });
    return { container, sticky, answer };
  };

  it('定位回答时扣掉同一轮吸附提问的高度', () => {
    const { container, answer } = mountTurn();
    container.scrollTop = 100;
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(rect(80));
    vi.spyOn(answer, 'getBoundingClientRect').mockReturnValue(rect(80));

    expect(resolveLocateScrollTop(container, answer)).toBe(60);
  });

  it('定位吸附提问本身时不扣高度', () => {
    const { container, sticky } = mountTurn();
    container.scrollTop = 100;
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(rect(80));
    vi.spyOn(sticky, 'getBoundingClientRect').mockReturnValue(rect(80));

    expect(resolveLocateScrollTop(container, sticky)).toBe(100);
  });

  it('计算结果小于 0 时停在顶部', () => {
    const { container, answer } = mountTurn();
    container.scrollTop = 0;
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(rect(20));
    vi.spyOn(answer, 'getBoundingClientRect').mockReturnValue(rect(0));

    expect(resolveLocateScrollTop(container, answer)).toBe(0);
  });
});

describe('scrollLocateTarget', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('目标在消息列表内时只滚动该容器', () => {
    const container = document.createElement('div');
    container.className = 'ai-message-container';
    const target = document.createElement('div');
    container.append(target);
    document.body.append(container);
    const scrollTo = vi.fn();
    container.scrollTo = scrollTo;

    scrollLocateTarget(target);

    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  });

  it('找不到消息列表时退回 scrollIntoView', () => {
    const target = document.createElement('div');
    document.body.append(target);
    const scrollIntoView = vi.fn();
    target.scrollIntoView = scrollIntoView;

    scrollLocateTarget(target);

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' });
  });
});
