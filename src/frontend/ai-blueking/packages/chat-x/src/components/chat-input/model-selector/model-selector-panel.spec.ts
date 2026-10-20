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
import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MODEL_DESCRIPTION_TIP_DELAY_MS } from './create-model-description-tippy';
import ModelSelectorPanel from './model-selector-panel.vue';

import type { IModelOption } from './types';
import type { Props } from 'tippy.js';

const { tippyMock, tipState } = vi.hoisted(() => {
  const tipState = { alive: 0, content: '', shown: 0 };
  const tippyMock = vi.fn(() => {
    tipState.alive += 1;
    return {
      destroy: () => {
        tipState.alive -= 1;
      },
      setContent: (content: string) => {
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

const described = createModel(1, 'GPT-4', { description: ' 通用模型 ' });
const plain = createModel(2, 'Claude 3');
const blank = createModel(3, 'DeepSeek', { description: '   ' });
const disabled = createModel(4, 'Disabled', { description: '不可用原因', disabled: true });

describe('ModelSelectorPanel 描述 tip', () => {
  let wrapper: undefined | VueWrapper<InstanceType<typeof ModelSelectorPanel>>;

  const mountPanel = (
    models: IModelOption[] = [described, plain, blank, disabled],
    tippyOptions?: { appendTo?: HTMLElement; placement?: 'bottom-start'; zIndex?: number },
  ) => {
    wrapper = mount(ModelSelectorPanel, {
      attachTo: document.body,
      props: { models, tippyOptions },
    });
  };

  const optionAt = (index: number) => wrapper?.findAll('.ai-model-selector-panel-option')[index];

  const hover = async (index: number) => {
    await optionAt(index).trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
  };

  beforeEach(() => {
    tipState.alive = 0;
    tipState.content = '';
    tipState.shown = 0;
    tippyMock.mockClear();
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = undefined;
    vi.useRealTimers();
  });

  it('无描述时名称保留原生 title，且不创建 tip', async () => {
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

  it('有描述时延迟展示 tip，名称不再挂原生 title', async () => {
    mountPanel();
    const option = optionAt(0);
    const rect = new DOMRect(10, 20, 30, 40);
    vi.spyOn(option.element, 'getBoundingClientRect').mockReturnValue(rect);

    expect(option.attributes('title')).toBeUndefined();
    expect(option.find('.ai-model-selector-panel-option-name').attributes('title')).toBeUndefined();

    await option.trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS - 1);
    expect(tippyMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(tippyMock).toHaveBeenCalledTimes(1);
    expect(tipState.alive).toBe(1);
    expect(tipState.content).toBe('通用模型');
    expect(tipState.shown).toBe(1);

    const options = tippyMock.mock.calls[0][1] as Props;
    expect(options.theme).toBe('ai-chat-box');
    expect(options.getReferenceClientRect?.()).toEqual(rect);
    expect(options.onShow?.({} as never)).toBeUndefined();
    vi.spyOn(option.element, 'isConnected', 'get').mockReturnValue(false);
    expect(options.onShow?.({} as never)).toBe(false);
  });

  it('未到延迟就离开时不应创建 tip', async () => {
    mountPanel();
    await optionAt(0).trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS - 1);
    await optionAt(0).trigger('mouseleave');
    await vi.advanceTimersByTimeAsync(MODEL_DESCRIPTION_TIP_DELAY_MS);
    expect(tippyMock).not.toHaveBeenCalled();
  });

  it('离开、滚动或卸载后应销毁当前这一个 tip', async () => {
    mountPanel();
    await hover(0);
    expect(tipState.alive).toBe(1);

    await optionAt(0).trigger('mouseleave');
    expect(tipState.alive).toBe(0);

    await hover(3);
    expect(tipState.content).toBe('不可用原因');
    expect(tipState.alive).toBe(1);

    await wrapper?.find('.ai-model-selector-panel-list').trigger('scroll');
    expect(tipState.alive).toBe(0);

    await hover(0);
    wrapper?.unmount();
    wrapper = undefined;
    expect(tipState.alive).toBe(0);
    expect(tippyMock).toHaveBeenCalledTimes(3);
  });

  it('列表替换或主动关闭时应取消尚未展示的 tip', async () => {
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

  it('应复用外层 tippyOptions 的 appendTo、placement 和 zIndex', async () => {
    const host = document.createElement('div');
    document.body.appendChild(host);
    mountPanel([described], {
      appendTo: host,
      placement: 'bottom-start',
      zIndex: 20,
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
