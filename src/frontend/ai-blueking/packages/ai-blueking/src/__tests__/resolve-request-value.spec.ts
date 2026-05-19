import { computed, ref } from 'vue';
import { describe, expect, it } from 'vitest';

import { resolveRequestValue } from '@blueking/chat-helper';

describe('resolveRequestValue', () => {
  it('returns plain object as-is', () => {
    const headers = { Authorization: 'Bearer token' };
    expect(resolveRequestValue(headers)).toEqual(headers);
  });

  it('calls zero-arg function and returns result', () => {
    let count = 0;
    const headers = () => {
      count += 1;
      return { 'X-Count': String(count) };
    };
    expect(resolveRequestValue(headers)).toEqual({ 'X-Count': '1' });
    expect(resolveRequestValue(headers)).toEqual({ 'X-Count': '2' });
  });

  it('unwraps ref', () => {
    const token = ref('a');
    const headers = ref({ Authorization: `Bearer ${token.value}` });
    expect(resolveRequestValue(headers)).toEqual({ Authorization: 'Bearer a' });
    token.value = 'b';
    headers.value = { Authorization: `Bearer ${token.value}` };
    expect(resolveRequestValue(headers)).toEqual({ Authorization: 'Bearer b' });
  });

  it('unwraps computed', () => {
    const tenantId = ref('t1');
    const data = computed(() => ({ tenant_id: tenantId.value }));
    expect(resolveRequestValue(data)).toEqual({ tenant_id: 't1' });
    tenantId.value = 't2';
    expect(resolveRequestValue(data)).toEqual({ tenant_id: 't2' });
  });

  it('unwraps function returning ref', () => {
    const headersRef = ref({ 'X-App': 'v1' });
    const getter = () => headersRef;
    expect(resolveRequestValue(getter)).toEqual({ 'X-App': 'v1' });
    headersRef.value = { 'X-App': 'v2' };
    expect(resolveRequestValue(getter)).toEqual({ 'X-App': 'v2' });
  });

  it('returns undefined for undefined input', () => {
    expect(resolveRequestValue(undefined)).toBeUndefined();
  });
});
