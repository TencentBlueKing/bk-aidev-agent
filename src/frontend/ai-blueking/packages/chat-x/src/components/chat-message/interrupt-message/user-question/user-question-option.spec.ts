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

import UserQuestionOption from './user-question-option.vue';

import type { NormalizedUserQuestionOption } from './use-user-question';

const normalOption: NormalizedUserQuestionOption = {
  label: 'A',
  description: '方案1：基础冒泡排序',
  isOthers: false,
  letter: 'A',
};

const othersOption: NormalizedUserQuestionOption = {
  label: 'others',
  description: '',
  isOthers: true,
  letter: 'B',
};

describe('UserQuestionOption', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('普通选项渲染字母徽标与描述文本', () => {
    wrapper = mount(UserQuestionOption, {
      props: { option: normalOption, selected: false },
    });

    expect(wrapper.find('.ai-user-question-option__badge').text()).toBe('A');
    expect(wrapper.find('.ai-user-question-option__text').text()).toBe('方案1：基础冒泡排序');
    expect(wrapper.find('.ai-user-question-option__input').exists()).toBe(false);
  });

  it('选中态附加 selected 修饰类', () => {
    wrapper = mount(UserQuestionOption, {
      props: { option: normalOption, selected: true },
    });

    expect(wrapper.classes()).toContain('ai-user-question-option--selected');
  });

  it('点击选项 emit select', async () => {
    wrapper = mount(UserQuestionOption, {
      props: { option: normalOption, selected: false },
    });

    await wrapper.trigger('click');
    expect(wrapper.emitted('select')).toHaveLength(1);
  });

  it('Others 选项渲染输入框，输入时同步 emit update:othersText 与 select', async () => {
    wrapper = mount(UserQuestionOption, {
      props: { option: othersOption, othersText: '', selected: false },
    });

    const input = wrapper.find('.ai-user-question-option__input');
    expect(input.exists()).toBe(true);

    await input.setValue('自定义内容');
    expect(wrapper.emitted('update:othersText')?.[0]).toEqual(['自定义内容']);
    expect(wrapper.emitted('select')).toHaveLength(1);
  });

  it('Others 输入回车 emit confirm', async () => {
    wrapper = mount(UserQuestionOption, {
      props: { option: othersOption, othersText: 'x', selected: true },
    });

    await wrapper.find('.ai-user-question-option__input').trigger('keydown.enter');
    expect(wrapper.emitted('confirm')).toHaveLength(1);
  });

  it('Others 已选中时聚焦输入框不重复 emit select，避免多选反选', async () => {
    wrapper = mount(UserQuestionOption, {
      props: { option: othersOption, othersText: 'x', selected: true },
    });

    await wrapper.find('.ai-user-question-option__input').trigger('focus');

    expect(wrapper.emitted('select')).toBeUndefined();
  });
});
