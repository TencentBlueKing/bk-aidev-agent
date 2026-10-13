import assert from 'node:assert/strict';
import { test } from 'node:test';

import { findStepRange } from './code-steps';
import { describeArg, describeCall } from './describe-call';
import { extractCustomHeaders, installFetchRecorder, parseBody, splitUrl, type FetchRequestInfo } from './fetch-recorder';
import { MAX_RECORDS_PER_RECIPE, createDemoRecorder, formatClock } from './recorder';

const SOURCE = [
  "import type { X } from 'x';",
  '',
  '// ① 第一步',
  'export function a() {',
  '  return 1;',
  '}',
  '',
  '// ② 第二步',
  'export function b() {}',
].join('\n');

test('findStepRange：从标记行到空行前', () => {
  assert.deepEqual(findStepRange(SOURCE, '①'), [2, 5]);
});

test('findStepRange：文件末尾无空行时止于最后一行', () => {
  assert.deepEqual(findStepRange(SOURCE, '②'), [7, 8]);
});

test('findStepRange：支持模板中的 HTML 注释标记', () => {
  const sfc = ['<template>', '  <!-- ② 分发 -->', '  <A v-if="x" />', '  <B v-else />', '</template>', '', '<script setup>'].join('\n');
  assert.deepEqual(findStepRange(sfc, '②'), [1, 4]);
});

test('findStepRange：标记不存在返回 null', () => {
  assert.equal(findStepRange(SOURCE, '③'), null);
});

test('describeCall：去掉尾部 undefined，保留中间 undefined', () => {
  assert.equal(describeCall('show', []), 'show()');
  assert.equal(describeCall('show', [undefined, { isTemporary: true }]), 'show(undefined, { isTemporary: true })');
  assert.equal(describeCall('show', ['code', undefined]), 'show("code")');
});

test('describeArg：长字符串截断，快捷指令显示名称与预填状态', () => {
  assert.equal(describeArg('一二三四五六七八九十一二三四五六七八九十一二三四五六'), '"一二三四五六七八九十一二三四五六七八九十一二三四…"');
  assert.equal(describeArg({ name: 'SQL 报错诊断', components: [{ default: null }] }), 'cmd「SQL 报错诊断」');
  assert.equal(describeArg({ name: 'SQL 报错诊断', components: [{ default: 'SELECT 1' }] }), 'cmd「SQL 报错诊断」 /* 已预填 */');
});

test('recorder：按配方隔离、超限丢弃最早、clear 精确清理', () => {
  const recorder = createDemoRecorder(() => new Date(2026, 9, 8, 9, 5, 7, 42));
  recorder.addEvent('a', 'call', 'show()');
  recorder.addEvent('b', 'event', '@show');
  assert.equal(recorder.get('a').events.length, 1);
  assert.equal(recorder.get('a').events[0].time, '09:05:07.042');

  for (let i = 0; i < MAX_RECORDS_PER_RECIPE + 5; i += 1) recorder.addEvent('a', 'call', `n${i}`);
  assert.equal(recorder.get('a').events.length, MAX_RECORDS_PER_RECIPE);
  assert.equal(recorder.get('a').events.at(-1)?.text, `n${MAX_RECORDS_PER_RECIPE + 4}`);

  const id = recorder.addRequest('b', { method: 'GET', path: 'session/', query: null, headers: {}, injectedKeys: [], body: null, sse: false, status: null });
  recorder.updateRequest('b', id, { status: 200, sse: true });
  assert.equal(recorder.get('b').requests[0].status, 200);

  recorder.clear('a');
  assert.equal(recorder.get('a').events.length, 0);
  assert.equal(recorder.get('b').events.length, 1);
  recorder.clear();
  assert.equal(recorder.get('b').requests.length, 0);
});

test('formatClock 补零', () => {
  assert.equal(formatClock(new Date(2026, 0, 1, 1, 2, 3, 4)), '01:02:03.004');
});

test('extractCustomHeaders：三种输入形态并忽略标准头', () => {
  const expected = { set_ai_message: 'true' };
  assert.deepEqual(extractCustomHeaders({ 'Content-Type': 'application/json', set_ai_message: 'true', 'x-mock-client': 'c' }), expected);
  assert.deepEqual(extractCustomHeaders([['accept', '*/*'], ['set_ai_message', 'true']]), expected);
  assert.deepEqual(extractCustomHeaders(new Headers({ Accept: '*/*', set_ai_message: 'true' })), expected);
  assert.deepEqual(extractCustomHeaders(undefined), {});
});

test('parseBody：JSON 字符串解析为对象', () => {
  assert.deepEqual(parseBody('{"a":1}'), { a: 1 });
  assert.equal(parseBody('plain'), 'plain');
  assert.equal(parseBody(null), null);
});

test('splitUrl：只接受 base 下的地址', () => {
  const base = 'http://docs.local/mock-agui/api/';
  assert.deepEqual(splitUrl('/mock-agui/api/session/?page=1', base), { path: 'session/', query: { page: '1' } });
  assert.equal(splitUrl('/other/session/', base), null);
  assert.equal(splitUrl('http://evil.local/mock-agui/api/session/', base), null);
});

test('installFetchRecorder：记录 base 下的请求、识别 SSE，并可卸载', async () => {
  const calls: string[] = [];
  const original: typeof fetch = async input => {
    calls.push(String(input));
    const sse = String(input).includes('chat_completion');
    return new Response('ok', { status: 200, headers: { 'content-type': sse ? 'text/event-stream' : 'application/json' } });
  };
  const target = { fetch: original };
  const seen: FetchRequestInfo[] = [];
  const responses: { status: number; sse: boolean }[] = [];
  const uninstall = installFetchRecorder(
    {
      getBase: () => 'http://docs.local/mock-agui/api/',
      onRequest: info => {
        seen.push(info);
        return seen.length;
      },
      onResponse: (_h, info) => responses.push(info),
    },
    target,
  );

  await target.fetch('http://docs.local/mock-agui/api/chat_completion/', {
    method: 'post',
    headers: { set_ai_message: 'true', 'x-demo-instance': 'embedded:a' },
    body: '{"session_code":"s"}',
  });
  await target.fetch('http://docs.local/elsewhere/');

  assert.equal(calls.length, 2);
  assert.equal(seen.length, 1);
  assert.deepEqual(seen[0], {
    instance: 'embedded:a',
    method: 'POST',
    path: 'chat_completion/',
    query: null,
    headers: { set_ai_message: 'true' },
    body: { session_code: 's' },
  });
  assert.deepEqual(responses, [{ status: 200, sse: true }]);

  uninstall();
  assert.equal(target.fetch, original);
});
