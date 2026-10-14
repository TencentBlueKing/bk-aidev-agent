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

import {
  formatProcessElapsed,
  resolveLatestCreatedAt,
  resolveProcessElapsed,
  toTimestamp,
} from './resolve-process-elapsed';

const START = Date.parse('2026-01-01T00:00:00.000Z');

describe('resolve-process-elapsed', () => {
  it('应该解析时间戳和 ISO 字符串，并忽略非法值', () => {
    expect(toTimestamp(START)).toBe(START);
    expect(toTimestamp('2026-01-01T00:00:00.000Z')).toBe(START);
    expect(toTimestamp('')).toBeUndefined();
    expect(toTimestamp('not-a-date')).toBeUndefined();
    expect(toTimestamp(undefined)).toBeUndefined();
  });

  it('应该取组内最晚的 createdAt，并跳过非法和缺失值', () => {
    expect(
      resolveLatestCreatedAt([{ createdAt: START + 5_000 }, { createdAt: 'not-a-date' }, { createdAt: START }, {}]),
    ).toBe(START + 5_000);
    expect(resolveLatestCreatedAt([{}, { createdAt: '' }])).toBeUndefined();
  });

  it('应该用终点减起点', () => {
    expect(resolveProcessElapsed(START, START + 122_000)).toBe(122_000);
  });

  it('缺少起点或终点时不应该计算耗时', () => {
    expect(resolveProcessElapsed(undefined, START)).toBeUndefined();
    expect(resolveProcessElapsed(START, undefined)).toBeUndefined();
  });

  it('耗时最小单位为秒，向下取整，不足 1 秒显示 <1s，为 0 时返回空串', () => {
    expect(formatProcessElapsed(0)).toBe('');
    expect(formatProcessElapsed(350)).toBe('<1s');
    expect(formatProcessElapsed(999)).toBe('<1s');
    expect(formatProcessElapsed(1_000)).toBe('1s');
    expect(formatProcessElapsed(5_000)).toBe('5s');
    expect(formatProcessElapsed(122_000)).toBe('2m2s');
    expect(formatProcessElapsed(122_350)).toBe('2m2s');
  });
});
