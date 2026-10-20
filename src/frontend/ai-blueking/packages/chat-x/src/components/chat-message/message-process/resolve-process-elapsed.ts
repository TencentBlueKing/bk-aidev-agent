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
import { formatDuration } from '../../../utils/utils';

/** 与消息时间字段一致：毫秒时间戳或可解析的时间字符串 */
export const toTimestamp = (value?: number | string): number | undefined => {
  if (value === undefined || value === '') {
    return undefined;
  }
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? undefined : timestamp;
};

/** 组内最晚的 createdAt，作为耗时终点；非法或缺失的时间跳过 */
export const resolveLatestCreatedAt = (messages: readonly { createdAt?: number | string }[]) => {
  let latest: number | undefined;
  for (const message of messages) {
    const timestamp = toTimestamp(message.createdAt);
    if (timestamp !== undefined && (latest === undefined || timestamp > latest)) {
      latest = timestamp;
    }
  }
  return latest;
};

/** 终态才计算。缺少任一端点时不返回耗时，避免用当前时间补 */
export const resolveProcessElapsed = (startAt?: number, endAt?: number): number | undefined => {
  if (startAt === undefined || endAt === undefined) {
    return undefined;
  }
  return Math.max(0, endAt - startAt);
};

/** 最小单位为秒，如 2m2s；不足 1 秒显示 <1s；为 0 时返回空串，由状态栏隐藏耗时 */
export const formatProcessElapsed = (durationMs: number) => {
  if (durationMs <= 0) {
    return '';
  }
  if (durationMs < 1000) {
    return '<1s';
  }
  return formatDuration(Math.floor(durationMs / 1000) * 1000);
};
