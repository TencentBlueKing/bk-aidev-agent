import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import MessageProcessHeader from './message-process-header.vue';

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const START = Date.parse('2026-01-01T00:00:00.000Z');

describe('MessageProcessHeader', () => {
  const textOf = (wrapper: ReturnType<typeof mount>) => wrapper.find('.ai-message-process-header-text').text();

  it('传入起止时间时应该展示耗时', () => {
    const wrapper = mount(MessageProcessHeader, {
      props: {
        collapsible: true,
        endAt: START + 122_000,
        label: '已完成',
        startAt: START,
      },
    });

    expect(textOf(wrapper)).toBe('已完成，耗时：2m2s');
    wrapper.unmount();
  });

  it('未传起止时间时只展示状态', () => {
    const wrapper = mount(MessageProcessHeader, {
      props: {
        label: '处理中',
      },
    });

    expect(textOf(wrapper)).toBe('处理中');
    wrapper.unmount();
  });

  it('loading 时文案应该带闪动样式，否则不带', async () => {
    const wrapper = mount(MessageProcessHeader, {
      props: {
        label: '处理中',
        loading: true,
      },
    });

    expect(wrapper.find('.ai-message-process-header-text').classes()).toContain('is-loading');

    await wrapper.setProps({ label: '已完成', loading: false });
    expect(wrapper.find('.ai-message-process-header-text').classes()).not.toContain('is-loading');
    wrapper.unmount();
  });

  it('不可折叠时不应该显示箭头，点击不抛出事件', async () => {
    const wrapper = mount(MessageProcessHeader, {
      props: {
        label: '已完成',
      },
    });

    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(false);
    expect(wrapper.find('.ai-message-process-header').classes()).not.toContain('is-collapsible');

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.emitted('toggle')).toBeUndefined();
    wrapper.unmount();
  });

  it('可折叠时应该显示箭头，点击抛出事件，展开后箭头旋转', async () => {
    const wrapper = mount(MessageProcessHeader, {
      props: {
        collapsible: true,
        endAt: START,
        expanded: false,
        label: '已完成',
        startAt: START,
      },
    });

    expect(wrapper.find('.ai-chevron-right-icon').exists()).toBe(true);
    expect(wrapper.find('.ai-message-process-header').classes()).toContain('is-collapsible');

    await wrapper.find('.ai-message-process-header').trigger('click');
    expect(wrapper.emitted('toggle')).toHaveLength(1);

    await wrapper.setProps({ expanded: true });
    expect(wrapper.find('.ai-chevron-right-icon.is-expanded').exists()).toBe(true);
    wrapper.unmount();
  });
});
