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
import { describe, expect, it } from 'vitest';

import { getReasoningOptions, resolveReasoningEffort, resolveReasoningSuffix } from './reasoning-effort';

import type { IModelOption, IModelReasoning } from './types';

const createModel = (reasoning?: IModelReasoning | null): IModelOption => ({
  id: 1,
  llm_code: 'qwen',
  llm_name: 'qwen',
  llm_type: 'chat.completion',
  max_token_size: 4096,
  property: { reasoning },
  space_auth_mode: 'PUBLIC',
  user_auth_mode: 'PUBLIC',
});

const reasoning: IModelReasoning = {
  default_effort: 'xhigh',
  mandatory: false,
  supported_efforts: [
    { desc: '不思考，直接回答', key: 'none', value: '关闭' },
    { desc: '简单思考，响应较快', key: 'low', value: '低' },
    { desc: '更深入的思考，适合复杂问题', key: 'xhigh', value: '超高' },
  ],
};

describe('reasoning-effort', () => {
  it('不支持思考深度（null / 未传）时返回空档位、无生效档、不回显', () => {
    [createModel(null), createModel(undefined), undefined].forEach(model => {
      expect(getReasoningOptions(model)).toEqual([]);
      expect(resolveReasoningEffort(model, 'low')).toBeUndefined();
      expect(resolveReasoningSuffix(model, 'low')).toBe('');
    });
  });

  it('getReasoningOptions 应按接口返回顺序给出档位', () => {
    expect(getReasoningOptions(createModel(reasoning)).map(option => option.key)).toEqual(['none', 'low', 'xhigh']);
  });

  it('档位在支持范围内时用该档位', () => {
    expect(resolveReasoningEffort(createModel(reasoning), 'low')?.value).toBe('低');
  });

  it('未传或不在支持范围内时回落到 default_effort', () => {
    const model = createModel(reasoning);
    expect(resolveReasoningEffort(model)?.key).toBe('xhigh');
    expect(resolveReasoningEffort(model, null)?.key).toBe('xhigh');
    expect(resolveReasoningEffort(model, 'max')?.key).toBe('xhigh');
  });

  it('default_effort 也不可用时返回 undefined', () => {
    const model = createModel({ ...reasoning, default_effort: undefined });
    expect(resolveReasoningEffort(model, 'max')).toBeUndefined();
    expect(resolveReasoningSuffix(model, 'max')).toBe('');
  });

  it('回显文字使用接口下发的展示名，「关闭」时固定回显「关闭思考」', () => {
    const model = createModel(reasoning);
    expect(resolveReasoningSuffix(model, 'low')).toBe('低');
    expect(resolveReasoningSuffix(model)).toBe('超高');
    expect(resolveReasoningSuffix(model, 'none')).toBe('关闭思考');
  });
});
