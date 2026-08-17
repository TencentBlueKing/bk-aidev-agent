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
import { t } from '../../../lang/lang';

const MS_PER_DAY = 86_400_000;

/** 取时区下的日历字段，month / day 不补零，与设计稿的 `3-12` 写法一致 */
type ZonedParts = {
  day: number;
  hour: number;
  minute: number;
  month: number;
  year: number;
};

const ZONED_FORMAT_OPTIONS: Intl.DateTimeFormatOptions = {
  day: 'numeric',
  hour: '2-digit',
  // h23 保证 0 点返回 00 而非 24
  hourCycle: 'h23',
  minute: '2-digit',
  month: 'numeric',
  year: 'numeric',
};

// 同一时区的 formatter 复用，避免长会话里为每条消息重复构造 Intl 实例
const formatterCache = new Map<string, Intl.DateTimeFormat>();

/**
 * 取目标时区的 formatter
 * @param timezone IANA 时区名；不传时 Intl 使用浏览器时区，非法时区名回退到浏览器时区而不是让渲染失败
 */
const getZonedFormatter = (timezone?: string): Intl.DateTimeFormat => {
  const cacheKey = timezone ?? '';
  const cached = formatterCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  let formatter: Intl.DateTimeFormat;
  try {
    formatter = new Intl.DateTimeFormat('en-US', { ...ZONED_FORMAT_OPTIONS, timeZone: timezone });
  } catch {
    formatter = new Intl.DateTimeFormat('en-US', ZONED_FORMAT_OPTIONS);
  }
  formatterCache.set(cacheKey, formatter);
  return formatter;
};

const getZonedParts = (formatter: Intl.DateTimeFormat, timestamp: number): ZonedParts => {
  const parts = formatter.formatToParts(timestamp);
  const pick = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find(part => part.type === type)?.value);
  return {
    day: pick('day'),
    hour: pick('hour'),
    minute: pick('minute'),
    month: pick('month'),
    year: pick('year'),
  };
};

/** 把时区下的日历日折算成可相减的数值，仅用于比较相差天数 */
const toDayIndex = (parts: ZonedParts) => Date.UTC(parts.year, parts.month - 1, parts.day);

const padZero = (value: number) => String(value).padStart(2, '0');

/**
 * 格式化消息时间，四档规则来自设计稿标注
 * 今天 `12:00`；昨天 `昨天 12:00`；今年内更早 `3-12 12:00`；非今年 `2026-3-12 12:00`
 * @param createdAt 消息创建时间，ISO 字符串或毫秒时间戳
 * @param timezone IANA 时区名；不传则按浏览器时区展示
 * @returns 无值或非法时间时返回空字符串，由调用方决定是否渲染
 */
export const formatMessageTime = (createdAt?: number | string, timezone?: string): string => {
  if (createdAt === undefined || createdAt === null || createdAt === '') {
    return '';
  }
  const timestamp = new Date(createdAt).getTime();
  if (Number.isNaN(timestamp)) {
    return '';
  }
  const formatter = getZonedFormatter(timezone);
  const target = getZonedParts(formatter, timestamp);
  const now = getZonedParts(formatter, Date.now());

  const clock = `${padZero(target.hour)}:${padZero(target.minute)}`;
  // 分档与展示都取同一时区的日历日：既避免「昨天 23:59」与「今天 00:01」因毫秒差不足一天被判成同一天，
  // 也避免按浏览器时区判断「今天/昨天」、却按配置时区显示时分导致的错位
  const dayDiff = Math.round((toDayIndex(now) - toDayIndex(target)) / MS_PER_DAY);
  if (dayDiff === 0) {
    return clock;
  }
  if (dayDiff === 1) {
    return `${t('昨天')} ${clock}`;
  }
  const monthDay = `${target.month}-${target.day} ${clock}`;
  return target.year === now.year ? monthDay : `${target.year}-${monthDay}`;
};
