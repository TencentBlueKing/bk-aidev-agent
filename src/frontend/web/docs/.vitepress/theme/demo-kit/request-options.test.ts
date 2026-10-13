import assert from 'node:assert/strict';
import { test } from 'node:test';
import { computed, ref } from 'vue';

import { mergeRequestOptions, type ResolvedRequestOptions } from './request-options';

const base: ResolvedRequestOptions = {
  headers: () => ({ 'x-mock-client': 'c1', 'X-Tenant': 'base' }),
  data: () => ({ from: 'base' }),
};

test('值形态：配方字段覆盖同名字段，保留运行时字段', () => {
  const merged = mergeRequestOptions(base, { headers: { 'X-Tenant': 't1' }, data: { tenant_id: 't1' } });
  assert.deepEqual(merged.headers(), { 'x-mock-client': 'c1', 'X-Tenant': 't1' });
  assert.deepEqual(merged.data(), { from: 'base', tenant_id: 't1' });
});

test('函数形态：每次调用都取最新值', () => {
  let token = 'a';
  const merged = mergeRequestOptions(base, { headers: () => ({ Authorization: `Bearer ${token}` }) });
  assert.equal(merged.headers().Authorization, 'Bearer a');
  token = 'b';
  assert.equal(merged.headers().Authorization, 'Bearer b');
});

test('ref / computed 形态：整体替换后自动生效', () => {
  const tenant = ref('t1');
  const options = computed(() => ({ headers: { 'X-Tenant': tenant.value }, context: { host: '10.0.0.12' } }));
  const merged = mergeRequestOptions(base, options);
  assert.equal(merged.headers()['X-Tenant'], 't1');
  tenant.value = 't2';
  assert.equal(merged.headers()['X-Tenant'], 't2');
  assert.deepEqual(merged.context, { host: '10.0.0.12' }, 'context 以值形态读取');
  assert.equal(typeof Object.getOwnPropertyDescriptor(merged, 'context')?.get, 'function');
});

test('extra 为空时等同于运行时的 requestOptions', () => {
  const merged = mergeRequestOptions(base, undefined);
  assert.deepEqual(merged.headers(), base.headers());
  assert.deepEqual(merged.data(), base.data());
  assert.equal(merged.context, undefined);
});
