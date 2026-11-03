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

import { MODEL_DESCRIPTION_TIP_DELAY_MS, MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS } from './create-model-description-tippy';
import ModelDescriptionCard from './model-description-card.vue';
import ModelSelectorPanel from './model-selector-panel.vue';

import type { IModelOption, IModelReasoning } from './types';
import type { Props } from 'tippy.js';

const { tippyMock, tipState } = vi.hoisted(() => {
  const tipState = { alive: 0, content: undefined as HTMLElement | undefined, shown: 0 };
  const tippyMock = vi.fn(() => {
    tipState.alive += 1;
    return {
      destroy: () => {
        tipState.alive -= 1;
      },
      setContent: (content: HTMLElement) => {
        tipState.content = content;
      },
      show: () => {
        tipState.shown += 1;
      },
    };
  });
  return { tippyMock, tipState };
});

vi.mock('tippy.js', () => ({
  default: tippyMock,
}));

vi.mock('tippy.js/dist/tippy.css', () => ({}));

const createModel = (id: number, llmName: string, extra: Partial<IModelOption> = {}): IModelOption => ({
  id,
  llm_code: llmName,
  llm_name: llmName,
  llm_type: 'chat.completion',
  max_token_size: 4096,
  property: {},
  space_auth_mode: 'PUBLIC',
  user_auth_mode: 'PUBLIC',
  ...extra,
});

const reasoning: IModelReasoning = {
  default_effort: 'medium',
  mandatory: false,
  supported_efforts: [
    { desc: '不思考，直接回答', key: 'none', value: '关闭' },
    { desc: '简单思考，响应较快', key: 'low', value: '低' },
    { desc: '兼顾思考深度与响应速度', key: 'medium', value: '中' },
  ],
};

const described = createModel(1, 'GPT-4', { description: ' 通用模型 ' });
const plain = createModel(2, 'Claude 3');
const blank = createModel(3, 'DeepSeek', { description: '   ' });
const disabled = createModel(4, 'Disabled', { description: '不可用原因', disabled: true });
const reasoningOnly = createModel(5, 'Hy3', { property: { reasoning } });

describe('ModelSelectorPanel 描述卡片', () => {
  let wrapper: undefined | VueWrapper<InstanceType<typeof ModelSelectorPanel>>;

  const mountPanel = (
    models: IModelOption[] = [described, plain, blank, disabled, reasoningOnly],
    extraProps: Record<string, unknown> = {},
  ) => {
    wrapper = mount(ModelSelectorPanel, {
      attachTo: document.body,
      props: { models, ...extraProps },
    });
  };

  const optionAt = (index: number) => wrapper?.findAll('.ai-model-selector-panel-option')[index];

  const hover = async (index: number) => {
    await optionAt(index).trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
    await nextTick();
  };

  beforeEach(() => {
    tipState.alive = 0;
    tipState.content = undefined;
    tipState.shown = 0;
    tippyMock.mockClear();
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'requestAnimationFrame', 'cancelAnimationFrame'] });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = undefined;
    vi.useRealTimers();
  });

  it('无描述且不支持思考深度时名称保留原生 title，且不创建卡片', async () => {
    mountPanel();
    const plainOption = optionAt(1);
    const blankOption = optionAt(2);

    expect(plainOption.attributes('title')).toBeUndefined();
    expect(plainOption.find('.ai-model-selector-panel-option-name').attributes('title')).toBe('Claude 3');
    expect(blankOption.find('.ai-model-selector-panel-option-name').attributes('title')).toBe('DeepSeek');

    await hover(1);
    await hover(2);
    expect(tippyMock).not.toHaveBeenCalled();
  });

  it('有描述时延迟展示卡片，名称不再挂原生 title', async () => {
    mountPanel();
    const option = optionAt(0);
    const rect = new DOMRect(10, 20, 30, 40);
    vi.spyOn(option.element, 'getBoundingClientRect').mockReturnValue(rect);

    expect(option.find('.ai-model-selector-panel-option-name').attributes('title')).toBeUndefined();

    await option.trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS - 1);
    expect(tippyMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    await nextTick();
    expect(tippyMock).toHaveBeenCalledTimes(1);
    expect(tipState.alive).toBe(1);
    expect(tipState.shown).toBe(1);
    expect(tipState.content?.querySelector('.ai-model-description-card-name')?.textContent?.trim()).toBe('GPT-4');
    expect(tipState.content?.querySelector('.ai-model-description-card-desc')?.textContent?.trim()).toBe('通用模型');
    // 不支持思考深度时卡片不展示思考深度行
    expect(tipState.content?.querySelector('.ai-model-description-card-reasoning')).toBeNull();

    const options = tippyMock.mock.calls[0][1] as Props;
    expect(options.theme).toBe('ai-chat-box-light light ai-model-description');
    expect(options.interactive).toBe(true);
    expect(options.getReferenceClientRect?.()).toEqual(rect);
    expect(options.onShow?.({} as never)).toBeUndefined();
    vi.spyOn(option.element, 'isConnected', 'get').mockReturnValue(false);
    expect(options.onShow?.({} as never)).toBe(false);
  });

  it('无描述但支持思考深度时也展示卡片：描述占位「--」并带思考深度行', async () => {
    mountPanel();
    expect(optionAt(4).find('.ai-model-selector-panel-option-name').attributes('title')).toBeUndefined();

    await hover(4);
    expect(tipState.content?.querySelector('.ai-model-description-card-desc')?.textContent?.trim()).toBe('--');
    expect(tipState.content?.querySelector('.ai-model-description-card-reasoning')).not.toBeNull();
  });

  it('未到延迟就离开时不应创建卡片', async () => {
    mountPanel();
    await optionAt(0).trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS - 1);
    await optionAt(0).trigger('mouseleave');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
    expect(tippyMock).not.toHaveBeenCalled();
  });

  it('离开选项后延迟关闭；期间移入卡片或回到原选项时保持展示', async () => {
    mountPanel();
    await hover(0);
    const tip = wrapper?.find('.ai-model-selector-panel-tip');

    await optionAt(0).trigger('mouseleave');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS - 1);
    await tip.trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS);
    expect(tipState.alive).toBe(1);

    await tip.trigger('mouseleave');
    await optionAt(0).trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS);
    expect(tipState.alive).toBe(1);
    expect(tippyMock).toHaveBeenCalledTimes(1);

    await tip.trigger('mouseleave');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS);
    expect(tipState.alive).toBe(0);
  });

  it('拖动滑块期间移出卡片不关闭，松手且鼠标不在卡片上时再关闭', async () => {
    mountPanel();
    await hover(4);
    const card = wrapper?.findComponent(ModelDescriptionCard);
    const tip = wrapper?.find('.ai-model-selector-panel-tip');

    card.vm.$emit('dragging', true);
    await tip.trigger('mouseleave');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS);
    expect(tipState.alive).toBe(1);

    card.vm.$emit('dragging', false);
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_HIDE_DELAY_MS);
    expect(tipState.alive).toBe(0);
  });

  it('切到另一个选项、滚动或卸载时应立即销毁当前这一个卡片', async () => {
    mountPanel();
    await hover(0);
    expect(tipState.alive).toBe(1);

    await hover(3);
    expect(tipState.alive).toBe(1);
    expect(tipState.content?.querySelector('.ai-model-description-card-desc')?.textContent?.trim()).toBe('不可用原因');

    await wrapper?.find('.ai-model-selector-panel-list').trigger('scroll');
    expect(tipState.alive).toBe(0);

    await hover(0);
    wrapper?.unmount();
    wrapper = undefined;
    expect(tipState.alive).toBe(0);
    expect(tippyMock).toHaveBeenCalledTimes(3);
  });

  it('列表替换或主动关闭时应取消尚未展示的卡片', async () => {
    mountPanel();
    await optionAt(0).trigger('mouseenter');
    await wrapper?.setProps({ models: [described] });
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
    expect(tippyMock).not.toHaveBeenCalled();

    await optionAt(0).trigger('mouseenter');
    wrapper?.vm.hideDescriptionTip();
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
    expect(tippyMock).not.toHaveBeenCalled();
  });

  it('上下键移动高亮时立刻展示当前项的描述卡片，无卡片的项则收起', async () => {
    mountPanel();
    Object.defineProperty(wrapper?.element, 'offsetParent', {
      configurable: true,
      get: () => document.body,
    });
    const cardName = () => tipState.content?.querySelector('.ai-model-description-card-name')?.textContent?.trim();
    const press = async (key: string) => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key }));
      await nextTick();
      await nextTick();
      await vi.advanceTimersByTimeAsync(16);
      await nextTick();
    };

    expect(tippyMock).not.toHaveBeenCalled();

    // 从第一项向上循环到最后一项 Hy3（有思考深度）
    await press('ArrowUp');
    expect(cardName()).toBe('Hy3');
    expect(tipState.content?.querySelector('.ai-model-description-card-reasoning')).not.toBeNull();
    expect(optionAt(4).classes()).toContain('is-active');

    await press('ArrowDown');
    expect(cardName()).toBe('GPT-4');
    expect(tipState.alive).toBe(1);

    // 下一项没有描述也不支持思考深度
    await press('ArrowDown');
    expect(tipState.alive).toBe(0);
    expect(optionAt(1).classes()).toContain('is-active');
  });

  it('键盘切换引起的滚动先派发时，描述卡片在滚动之后仍然展示', async () => {
    mountPanel();
    Object.defineProperty(wrapper?.element, 'offsetParent', {
      configurable: true,
      get: () => document.body,
    });
    const cardName = () => tipState.content?.querySelector('.ai-model-description-card-name')?.textContent?.trim();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
    await nextTick();
    await nextTick();
    expect(tippyMock).not.toHaveBeenCalled();

    await wrapper?.find('.ai-model-selector-panel-list').trigger('scroll');
    expect(tipState.alive).toBe(0);

    await vi.advanceTimersByTimeAsync(16);
    await nextTick();
    expect(cardName()).toBe('Hy3');
    expect(tipState.alive).toBe(1);
  });

  it('isTipTarget 只对卡片内的节点返回 true', async () => {
    mountPanel();
    await hover(4);
    const slider = tipState.content?.querySelector('.ai-reasoning-effort-slider-thumb') ?? null;

    expect(wrapper?.vm.isTipTarget(slider)).toBe(true);
    expect(wrapper?.vm.isTipTarget(optionAt(0).element)).toBe(false);
    expect(wrapper?.vm.isTipTarget(null)).toBe(false);
  });

  it('应复用外层 tippyOptions 的 appendTo、placement 和 zIndex', async () => {
    const host = document.createElement('div');
    document.body.appendChild(host);
    mountPanel([described], {
      tippyOptions: {
        appendTo: host,
        placement: 'bottom-start',
        zIndex: 20,
      },
    });

    await hover(0);

    const options = tippyMock.mock.calls[0][1] as Props;
    expect(options.appendTo).toBe(host);
    expect(options.placement).toBe('bottom-start');
    expect(options.zIndex).toBe(20);
    expect(options.getReferenceClientRect?.contextElement).toBe(host);
    expect(options.trigger).toBe('manual');
    host.remove();
  });
});

describe('ModelSelectorPanel 思考深度', () => {
  let wrapper: undefined | VueWrapper<InstanceType<typeof ModelSelectorPanel>>;
  const other = createModel(6, 'Other', { property: { reasoning } });

  const effortTextOf = (index: number) =>
    wrapper?.findAll('.ai-model-selector-panel-option')[index].find('.ai-model-selector-panel-option-effort');

  beforeEach(() => {
    tippyMock.mockClear();
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = undefined;
    vi.useRealTimers();
  });

  it('当前模型按传入档位回显，其余模型按 default_effort 回显，不支持时不回显', () => {
    wrapper = mount(ModelSelectorPanel, {
      attachTo: document.body,
      props: { models: [reasoningOnly, other, plain], reasoningEffort: 'low', selectedName: 'Hy3' },
    });

    expect(effortTextOf(0).text()).toBe('低');
    expect(effortTextOf(1).text()).toBe('中');
    expect(effortTextOf(2).exists()).toBe(false);
  });

  it('档位为「关闭」时模型名后不回显', () => {
    wrapper = mount(ModelSelectorPanel, {
      attachTo: document.body,
      props: { models: [reasoningOnly], reasoningEffort: 'none', selectedName: 'Hy3' },
    });

    expect(effortTextOf(0).exists()).toBe(false);
  });

  it('卡片内调档时应抛出 reasoningEffortChange（携带卡片对应的模型）', async () => {
    wrapper = mount(ModelSelectorPanel, {
      attachTo: document.body,
      props: { models: [reasoningOnly, other], reasoningEffort: 'low', selectedName: 'Hy3' },
    });
    await wrapper.findAll('.ai-model-selector-panel-option')[1].trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
    await nextTick();

    const card = wrapper.findComponent(ModelDescriptionCard);
    // 非当前模型的卡片按 default_effort 展示
    expect(card.props('effort')).toBe('medium');
    card.vm.$emit('change', 'none');
    expect(wrapper.emitted('reasoningEffortChange')?.[0]).toEqual([other, 'none']);
  });
});
