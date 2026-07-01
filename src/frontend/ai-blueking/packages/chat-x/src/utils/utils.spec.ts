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

import { formatDuration, formatElapsedTime } from './utils';

describe('formatDuration', () => {
  it('数字与单位之间、各段之间均不留空格', () => {
    expect(formatDuration(90500)).toBe('1m30s500ms');
    expect(formatDuration(30000)).toBe('30s');
    expect(formatDuration(60000)).toBe('1m');
  });

  it('不足 1 秒时应展示毫秒', () => {
    expect(formatDuration(0)).toBe('0ms');
    expect(formatDuration(500)).toBe('500ms');
  });
});

describe('formatElapsedTime', () => {
  it('不足 1 秒时应返回 <1s', () => {
    expect(formatElapsedTime(0)).toBe('<1s');
    expect(formatElapsedTime(0.5)).toBe('<1s');
  });

  it('应拼接天、时、分、秒中非零部分', () => {
    expect(formatElapsedTime(45)).toBe('45s');
    expect(formatElapsedTime(90)).toBe('1m30s');
    expect(formatElapsedTime(3661)).toBe('1h1m1s');
    expect(formatElapsedTime(90061)).toBe('1d1h1m1s');
  });

  it('整分钟/整小时等中间为零的项应省略', () => {
    expect(formatElapsedTime(60)).toBe('1m');
    expect(formatElapsedTime(3600)).toBe('1h');
    expect(formatElapsedTime(86400)).toBe('1d');
  });
});
