const STICKY_GROUP_SELECTOR = ':scope > .message-group.is-sticky';

/**
 * 产物「定位」滚到回答时，同一轮吸附中的提问会盖住回答开头。
 * 目标不在吸附提问内部时，滚动位置留出提问高度。
 */
export const resolveLocateScrollTop = (container: HTMLElement, target: HTMLElement): number => {
  const sticky = target.closest('.ai-message-turn')?.querySelector(STICKY_GROUP_SELECTOR);
  const stickyHeight = sticky instanceof HTMLElement && !sticky.contains(target) ? sticky.offsetHeight : 0;
  const top =
    container.scrollTop + target.getBoundingClientRect().top - container.getBoundingClientRect().top - stickyHeight;
  return Math.max(0, top);
};

/** 在消息滚动容器内定位。容器不在消息列表里时退回 scrollIntoView。 */
export const scrollLocateTarget = (target: HTMLElement) => {
  const container = target.closest('.ai-message-container');
  if (!(container instanceof HTMLElement)) {
    target.scrollIntoView({ behavior: 'smooth' });
    return;
  }
  container.scrollTo({ top: resolveLocateScrollTop(container, target), behavior: 'smooth' });
};
