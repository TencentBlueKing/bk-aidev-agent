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

import { computed, defineComponent, h, nextTick, ref } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import { useModelSelector } from './use-model-selector';

import type { IModelOption, IModelProperty } from './types';

// 构造贴合后端结构的模型选项，补齐必填字段，便于用例聚焦 llm_name 逻辑
const createModel = (id: number, llmName: string, property: IModelProperty = {}): IModelOption => ({
  id,
  llm_code: llmName,
  llm_name: llmName,
  llm_type: 'chat.completion',
  max_token_size: 4096,
  property,
  space_auth_mode: 'PUBLIC',
  user_auth_mode: 'PUBLIC',
});

const models: IModelOption[] = [createModel(1, 'GPT-4'), createModel(2, 'Claude 3'), createModel(3, 'DeepSeek')];

describe('useModelSelector', () => {
  it('关键字为空时应返回完整模型列表', async () => {
    let result: ReturnType<typeof useModelSelector> | undefined;
    const selectedModel = ref<string | undefined>('GPT-4');

    const Host = defineComponent({
      setup() {
        result = useModelSelector({
          models: computed(() => models),
          selectedModel,
        });
        return () => h('div');
      },
    });

    const wrapper = mount(Host);
    await nextTick();

    expect(result?.filteredModels.value).toEqual(models);
    wrapper.unmount();
  });

  it('应按模型名过滤列表（不区分大小写）', async () => {
    let result: ReturnType<typeof useModelSelector> | undefined;
    const selectedModel = ref<string | undefined>();

    const Host = defineComponent({
      setup() {
        result = useModelSelector({
          models: computed(() => models),
          selectedModel,
        });
        return () => h('div');
      },
    });

    const wrapper = mount(Host);
    await nextTick();

    result?.keyword.value = 'claude';
    await nextTick();
    expect(result?.filteredModels.value).toEqual([models[1]]);

    wrapper.unmount();
  });

  it('应根据 selectedModel 解析当前选中模型', async () => {
    let result: ReturnType<typeof useModelSelector> | undefined;
    const selectedModel = ref<string | undefined>('DeepSeek');

    const Host = defineComponent({
      setup() {
        result = useModelSelector({
          models: computed(() => models),
          selectedModel,
        });
        return () => h('div');
      },
    });

    const wrapper = mount(Host);
    await nextTick();

    expect(result?.currentModel.value).toEqual(models[2]);
    wrapper.unmount();
  });

  it('resetKeyword 应清空搜索关键字', async () => {
    let result: ReturnType<typeof useModelSelector> | undefined;
    const selectedModel = ref<string | undefined>();

    const Host = defineComponent({
      setup() {
        result = useModelSelector({
          models: computed(() => models),
          selectedModel,
        });
        return () => h('div');
      },
    });

    const wrapper = mount(Host);
    await nextTick();

    result?.keyword.value = 'gpt';
    await nextTick();
    result?.resetKeyword();
    await nextTick();

    expect(result?.keyword.value).toBe('');
    expect(result?.filteredModels.value).toEqual(models);
    wrapper.unmount();
  });
});
