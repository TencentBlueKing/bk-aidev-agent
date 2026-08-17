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
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { formatMessageTime } from './format-message-time';

describe('formatMessageTime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // 固定「现在」为 2026-08-17 15:30（本地时区）
    vi.setSystemTime(new Date(2026, 7, 17, 15, 30));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('无值或非法时间应返回空字符串', () => {
    expect(formatMessageTime()).toBe('');
    expect(formatMessageTime('')).toBe('');
    expect(formatMessageTime('not-a-date')).toBe('');
  });

  it('今天的消息只显示时分，时分补零', () => {
    expect(formatMessageTime(new Date(2026, 7, 17, 9, 5).toISOString())).toBe('09:05');
  });

  it('昨天的消息带「昨天」前缀', () => {
    expect(formatMessageTime(new Date(2026, 7, 16, 12, 0).toISOString())).toBe('昨天 12:00');
  });

  it('跨日按日历日分档，不因毫秒差不足一天而误判为今天', () => {
    vi.setSystemTime(new Date(2026, 7, 17, 0, 30));
    expect(formatMessageTime(new Date(2026, 7, 16, 23, 59).toISOString())).toBe('昨天 23:59');
  });

  it('今年内超出两天的消息显示月日，月日不补零', () => {
    expect(formatMessageTime(new Date(2026, 2, 12, 12, 0).toISOString())).toBe('3-12 12:00');
  });

  it('非今年的消息显示完整年月日', () => {
    expect(formatMessageTime(new Date(2025, 2, 12, 12, 0).toISOString())).toBe('2025-3-12 12:00');
  });

  it('应接受毫秒时间戳', () => {
    expect(formatMessageTime(new Date(2026, 7, 17, 12, 0).getTime())).toBe('12:00');
  });
});

describe('formatMessageTime 时区配置', () => {
  // 固定为绝对瞬间，使断言不受运行机器时区影响
  // 该瞬间在 上海=08-17 15:30、UTC=08-17 07:30、纽约=08-17 03:30
  const NOW = '2026-08-17T07:30:00.000Z';

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('同一瞬间应按各自配置的时区展示时分', () => {
    const createdAt = '2026-08-17T04:00:00.000Z';
    expect(formatMessageTime(createdAt, 'Asia/Shanghai')).toBe('12:00');
    expect(formatMessageTime(createdAt, 'UTC')).toBe('04:00');
    expect(formatMessageTime(createdAt, 'America/New_York')).toBe('00:00');
  });

  it('今天/昨天的分档应按配置时区判断，而非浏览器时区', () => {
    // 该瞬间在上海已是 08-17 凌晨（今天），在 UTC 与纽约仍是 08-16（昨天）
    const createdAt = '2026-08-16T20:00:00.000Z';
    expect(formatMessageTime(createdAt, 'Asia/Shanghai')).toBe('04:00');
    expect(formatMessageTime(createdAt, 'UTC')).toBe('昨天 20:00');
    expect(formatMessageTime(createdAt, 'America/New_York')).toBe('昨天 16:00');
  });

  it('今年内更早与非今年两档同样按配置时区计算', () => {
    expect(formatMessageTime('2026-03-12T04:00:00.000Z', 'Asia/Shanghai')).toBe('3-12 12:00');
    expect(formatMessageTime('2024-03-12T04:00:00.000Z', 'Asia/Shanghai')).toBe('2024-3-12 12:00');
  });

  it('跨年边界应按配置时区归属年份', () => {
    // 该瞬间在上海是 2026-01-01 07:00（今年），在 UTC 是 2025-12-31 23:00（非今年）
    vi.setSystemTime(new Date('2026-06-01T00:00:00.000Z'));
    const createdAt = '2025-12-31T23:00:00.000Z';
    expect(formatMessageTime(createdAt, 'Asia/Shanghai')).toBe('1-1 07:00');
    expect(formatMessageTime(createdAt, 'UTC')).toBe('2025-12-31 23:00');
  });

  it('非法时区名应回退到浏览器时区而不是渲染失败', () => {
    const createdAt = '2026-08-17T04:00:00.000Z';
    expect(formatMessageTime(createdAt, 'Not/AZone')).toBe(formatMessageTime(createdAt));
  });
});
