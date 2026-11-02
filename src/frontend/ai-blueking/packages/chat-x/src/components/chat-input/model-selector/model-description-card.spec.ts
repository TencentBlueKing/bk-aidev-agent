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
import { afterEach, describe, expect, it } from 'vitest';

import ModelDescriptionCard from './model-description-card.vue';
import ReasoningEffortSlider from './reasoning-effort-slider.vue';

import type { IModelOption } from './types';

const createModel = (extra: Partial<IModelOption> = {}): IModelOption => ({
  id: 1,
  llm_code: 'Hy3 hunyuan',
  llm_name: 'Hy3 hunyuan',
  llm_type: 'chat.completion',
  max_token_size: 4096,
  property: {},
  space_auth_mode: 'PUBLIC',
  user_auth_mode: 'PUBLIC',
  ...extra,
});

const reasoningProperty = {
  reasoning: {
    default_effort: 'xhigh' as const,
    mandatory: true,
    supported_efforts: [
      { desc: '简单思考，响应较快', key: 'low' as const, value: '低' },
      { desc: '更深入的思考，适合复杂问题', key: 'xhigh' as const, value: '超高' },
    ],
  },
};

describe('ModelDescriptionCard', () => {
  let wrapper: undefined | VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
    wrapper = undefined;
  });

  it('应展示模型名与去空白后的描述；不支持思考深度时不展示思考深度行', () => {
    wrapper = mount(ModelDescriptionCard, {
      props: { model: createModel({ description: '  混元模型  ' }) },
    });
    expect(wrapper.find('.ai-model-description-card-name').text()).toBe('Hy3 hunyuan');
    expect(wrapper.find('.ai-model-description-card-desc').text()).toBe('混元模型');
    expect(wrapper.find('.ai-model-description-card-reasoning').exists()).toBe(false);
  });

  it('无描述时显示「--」占位', () => {
    wrapper = mount(ModelDescriptionCard, {
      props: { model: createModel({ description: '   ', property: reasoningProperty }) },
    });
    expect(wrapper.find('.ai-model-description-card-desc').text()).toBe('--');
  });

  it('支持思考深度时渲染滑块，透传档位与禁用态，并转发 change / dragging', async () => {
    wrapper = mount(ModelDescriptionCard, {
      props: { effort: 'low', model: createModel({ disabled: true, property: reasoningProperty }) },
    });
    expect(wrapper.find('.ai-model-description-card-reasoning-label').text()).toBe('思考深度');

    const slider = wrapper.findComponent(ReasoningEffortSlider);
    expect(slider.props()).toMatchObject({
      disabled: true,
      effort: 'low',
      options: reasoningProperty.reasoning.supported_efforts,
    });

    slider.vm.$emit('change', 'xhigh');
    slider.vm.$emit('dragging', true);
    expect(wrapper.emitted('change')).toEqual([['xhigh']]);
    expect(wrapper.emitted('dragging')).toEqual([[true]]);
  });
});
