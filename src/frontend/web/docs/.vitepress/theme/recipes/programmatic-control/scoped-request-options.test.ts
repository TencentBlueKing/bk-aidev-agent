import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createScopedRequestOptions } from './snippets/scoped-request-options';

test('runWith 期间注入，结束后清除', async () => {
  const scoped = createScopedRequestOptions();
  let during: Record<string, string> = {};
  await scoped.runWith({ headers: () => ({ set_ai_message: 'true' }), data: () => ({ data: 'x' }) }, async () => {
    during = scoped.requestOptions.headers();
    assert.deepEqual(scoped.requestOptions.data(), { data: 'x' });
    assert.ok(scoped.getActive());
  });
  assert.deepEqual(during, { set_ai_message: 'true' });
  assert.deepEqual(scoped.requestOptions.headers(), {});
  assert.deepEqual(scoped.requestOptions.data(), {});
  assert.equal(scoped.getActive(), undefined);
});

test('fn 抛错时同样清除，并继续抛出', async () => {
  const scoped = createScopedRequestOptions();
  await assert.rejects(
    scoped.runWith({ headers: () => ({ a: '1' }) }, async () => {
      throw new Error('boom');
    }),
    /boom/,
  );
  assert.deepEqual(scoped.requestOptions.headers(), {});
});
