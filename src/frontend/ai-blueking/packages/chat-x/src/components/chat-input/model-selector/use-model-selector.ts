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

import { type ComputedRef, type Ref, computed, shallowRef } from 'vue';

import type { IModelOption } from './types';

/**
 * 模型选择的纯数据逻辑（与 UI 解耦，可独立单测）：
 * 仅负责「按关键字过滤」与「解析当前选中模型」，不持有任何展示/交互态。
 */
export const useModelSelector = (params: {
  /** 模型列表 */
  models: ComputedRef<IModelOption[]> | Ref<IModelOption[]>;
  /** 当前选中模型 id */
  selectedId: Ref<string | undefined>;
}) => {
  /** 搜索关键字（仅按模型名做包含匹配） */
  const keyword = shallowRef('');

  /** 按关键字过滤后的模型列表 */
  const filteredModels = computed<IModelOption[]>(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) {
      return params.models.value;
    }
    return params.models.value.filter(model => model.name.toLowerCase().includes(kw));
  });

  /** 当前选中的模型对象 */
  const selectedModel = computed<IModelOption | undefined>(() =>
    params.models.value.find(model => model.id === params.selectedId.value),
  );

  /** 重置搜索关键字 */
  const resetKeyword = () => {
    keyword.value = '';
  };

  return {
    keyword,
    filteredModels,
    selectedModel,
    resetKeyword,
  };
};
