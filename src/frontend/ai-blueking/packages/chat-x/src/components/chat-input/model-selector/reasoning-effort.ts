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

import type { IModelOption, IReasoningEffortOption, ReasoningEffort } from './types';

/** 模型支持的思考深度档位（按接口返回顺序）；不支持时为空数组 */
export const getReasoningOptions = (model?: IModelOption): IReasoningEffortOption[] =>
  model?.property?.reasoning?.supported_efforts ?? [];

/**
 * 解析模型实际生效的档位：
 * effort 在 supported_efforts 内时用它，否则回落到模型 default_effort（如切换模型后残留了旧档位）。
 */
export const resolveReasoningEffort = (
  model?: IModelOption,
  effort?: null | ReasoningEffort,
): IReasoningEffortOption | undefined => {
  const options = getReasoningOptions(model);
  return (
    options.find(option => option.key === effort) ??
    options.find(option => option.key === model?.property?.reasoning?.default_effort)
  );
};

/** 模型名后回显的档位文字；不支持思考深度或档位为「关闭」（none）时不回显 */
export const resolveReasoningSuffix = (model?: IModelOption, effort?: null | ReasoningEffort): string => {
  const option = resolveReasoningEffort(model, effort);
  return option && option.key !== 'none' ? option.value : '';
};
