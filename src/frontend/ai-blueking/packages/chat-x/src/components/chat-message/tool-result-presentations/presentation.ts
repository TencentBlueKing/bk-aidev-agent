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

export type MetricSeries = {
  name: string;
  points: [number, null | number][];
  unit: string;
};

export type ObservationView = { partial: boolean; schema_version: 1 } & (
  | { rows: LogRow[]; total: null | number; type: 'log_records' }
  | { sampled: boolean; series: MetricSeries[]; total_series: number; type: 'metric_series' }
);

type LogRow = {
  clipped: boolean;
  level: string;
  source: string;
  text: string;
  timestamp: null | number;
};

const record = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;

const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const timestamp = (value: unknown): value is number => number(value) && value > 0 && value <= 8640000000000000;
const count = (value: unknown): value is number => number(value) && Number.isSafeInteger(value) && value >= 0;

export type ObservationCard = { id: string; view: ObservationView };

export function observationMessageId(value: unknown): string {
  const message = record(value);
  const id = message?.messageId ?? message?.id ?? message?.uid;
  return typeof id === 'string' || typeof id === 'number' ? String(id) : '';
}

export function observationViewsByUserMessage(messages: readonly unknown[]): Map<string, ObservationCard[]> {
  const cards = new Map<string, ObservationCard[]>();
  const calls = new Map<string, string>();
  let userMessageId = '';
  for (const item of messages) {
    const message = record(item);
    if (!message) continue;
    if (message.role === 'user') {
      userMessageId = observationMessageId(message);
      continue;
    }
    if (userMessageId && message.role === 'assistant' && Array.isArray(message.toolCalls)) {
      for (const rawCall of message.toolCalls) {
        const call = record(rawCall);
        if (typeof call?.id === 'string' && typeof record(call.function)?.name === 'string') {
          calls.set(call.id, userMessageId);
        }
      }
    }
    if (message.role !== 'tool' || message.status === 'error' || message.error === true) continue;
    const callId = message.toolCallId;
    if (typeof callId !== 'string') continue;
    const owner = calls.get(callId);
    if (!owner) continue;
    calls.delete(callId);
    const view = readObservationView(message.content);
    if (view) {
      const card = { id: callId, view };
      const existing = cards.get(owner);
      if (existing) existing.push(card);
      else cards.set(owner, [card]);
    }
  }
  return cards;
}

export function readObservationView(content: unknown): null | ObservationView {
  if (typeof content !== 'string' || !content.includes('"presentation"')) return null;
  let value: Record<string, unknown> | undefined;
  try {
    value = record(record(JSON.parse(content))?.presentation);
  } catch {
    return null;
  }
  if (value?.schema_version !== 1 || typeof value.partial !== 'boolean') return null;
  if (
    value.type === 'metric_series' &&
    Array.isArray(value.series) &&
    value.series.every(isMetricSeries) &&
    count(value.total_series) &&
    typeof value.sampled === 'boolean'
  ) {
    return value as ObservationView;
  }
  if (
    value.type === 'log_records' &&
    Array.isArray(value.rows) &&
    value.rows.every(isLogRow) &&
    (value.total === null || count(value.total))
  ) {
    return value as ObservationView;
  }
  return null;
}

function isLogRow(value: unknown): value is LogRow {
  const row = record(value);
  return (
    !!row &&
    (row.timestamp === null || timestamp(row.timestamp)) &&
    typeof row.level === 'string' &&
    typeof row.source === 'string' &&
    typeof row.text === 'string' &&
    typeof row.clipped === 'boolean'
  );
}

function isMetricSeries(value: unknown): value is MetricSeries {
  const series = record(value);
  return (
    !!series &&
    typeof series.name === 'string' &&
    typeof series.unit === 'string' &&
    Array.isArray(series.points) &&
    series.points.every(
      point =>
        Array.isArray(point) && point.length === 2 && timestamp(point[0]) && (point[1] === null || number(point[1])),
    )
  );
}
