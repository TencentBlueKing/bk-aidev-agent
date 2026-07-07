import assert from 'node:assert/strict';
import { test } from 'node:test';

import { computeNextVersion, resolveTag } from './bump-version.mjs';

test('resolveTag: 从版本号解析', () => {
  assert.equal(resolveTag('2.1.0-alpha.1'), 'alpha');
  assert.equal(resolveTag('2.1.0-beta.4'), 'beta');
  assert.equal(resolveTag('2.1.0-rc.1'), 'rc');
  assert.equal(resolveTag('2.1.0'), 'latest');
});

test('resolveTag: 覆盖优先于版本号解析', () => {
  assert.equal(resolveTag('2.1.0-beta.4', 'feat-hitl'), 'feat-hitl');
  assert.equal(resolveTag('2.1.0', 'next'), 'next');
});

test('computeNextVersion: 显式版本原样返回', () => {
  assert.equal(computeNextVersion('2.1.0-beta.4', '3.0.0'), '3.0.0');
});

test('computeNextVersion: 预发布号自增', () => {
  assert.equal(computeNextVersion('2.1.0-beta.4'), '2.1.0-beta.5');
  assert.equal(computeNextVersion('0.0.2-alpha.9'), '0.0.2-alpha.10');
  assert.equal(computeNextVersion('1.2.3-rc.0'), '1.2.3-rc.1');
});

test('computeNextVersion: 正式版留空则报错', () => {
  assert.throws(() => computeNextVersion('2.1.0'), /正式版必须显式指定版本号/);
});
