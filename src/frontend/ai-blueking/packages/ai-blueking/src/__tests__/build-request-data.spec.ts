import { describe, it, expect } from 'vitest';
import { computed, ref } from 'vue';

import { resolveContextEntries, resolveRequestOptionsContext, mergePropertyContext } from '../utils/build-request-data';

describe('resolveContextEntries', () => {
  it('should return empty array for undefined', () => {
    expect(resolveContextEntries(undefined)).toEqual([]);
  });

  it('should convert Record<string, unknown> to structured array', () => {
    const result = resolveContextEntries({ app_id: 'test', env: 'prod' });

    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      app_id: 'test',
      context_type: 'input',
      __label: 'app_id',
      __key: 'app_id',
      __value: 'test',
    });
    expect(result[1]).toMatchObject({
      env: 'prod',
      context_type: 'input',
      __label: 'env',
      __key: 'env',
      __value: 'prod',
    });
  });

  it('should auto-convert simple KV items in array format', () => {
    const result = resolveContextEntries([{ app_id: 'test' }, { env: 'prod' }]);

    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      app_id: 'test',
      context_type: 'input',
      __label: 'app_id',
      __key: 'app_id',
      __value: 'test',
    });
    expect(result[1]).toMatchObject({
      env: 'prod',
      context_type: 'input',
      __label: 'env',
      __key: 'env',
      __value: 'prod',
    });
  });

  it('should pass through structured items with __key', () => {
    const structured = {
      input: 'hello',
      context_type: 'textarea',
      __label: 'Input Field',
      __key: 'input',
      __value: 'hello',
    };
    const result = resolveContextEntries([structured]);

    expect(result).toHaveLength(1);
    expect(result[0]).toBe(structured);
  });

  it('should handle mixed array with simple KV and structured items', () => {
    const structured = {
      input: 'hello',
      context_type: 'textarea',
      __label: 'Input Field',
      __key: 'input',
      __value: 'hello',
    };
    const result = resolveContextEntries([{ env: 'prod' }, structured]);

    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      env: 'prod',
      context_type: 'input',
      __label: 'env',
      __key: 'env',
      __value: 'prod',
    });
    expect(result[1]).toBe(structured);
  });

  it('should handle empty Record', () => {
    expect(resolveContextEntries({})).toEqual([]);
  });

  it('should handle empty array', () => {
    expect(resolveContextEntries([])).toEqual([]);
  });

  it('should preserve extra metadata on simple KV items', () => {
    const result = resolveContextEntries([{ app_id: 'test', context_type: 'select', __label: 'App' }]);

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      app_id: 'test',
      context_type: 'select',
      __label: 'App',
      __key: 'app_id',
      __value: 'test',
    });
  });
});

describe('mergePropertyContext', () => {
  it('should return original property when contextEntries is empty', () => {
    const property = { extra: { command: 'cmd-1', context: [{ __key: 'a' }] } };
    expect(mergePropertyContext(property, [])).toBe(property);
  });

  it('should return empty object when property is undefined and contextEntries is empty', () => {
    expect(mergePropertyContext(undefined, [])).toEqual({});
  });

  it('should create extra.context when property has no extra', () => {
    const entries = [{ env: 'prod', context_type: 'input', __label: 'env', __key: 'env', __value: 'prod' }];
    const result = mergePropertyContext({}, entries);

    expect(result.extra.context).toEqual(entries);
  });

  it('should append context entries to existing property', () => {
    const existing = [{ input: 'hello', context_type: 'textarea', __label: 'Input', __key: 'input', __value: 'hello' }];
    const newEntries = [{ env: 'prod', context_type: 'input', __label: 'env', __key: 'env', __value: 'prod' }];
    const property = { extra: { command: 'cmd-1', context: existing } };

    const result = mergePropertyContext(property, newEntries);

    expect(result.extra.context).toHaveLength(2);
    expect(result.extra.context[0]).toBe(existing[0]);
    expect(result.extra.context[1]).toBe(newEntries[0]);
  });

  it('should override existing entries with same __key', () => {
    const existing = [
      { input: 'old', context_type: 'textarea', __label: 'Input', __key: 'input', __value: 'old' },
      { lang: 'python', context_type: 'select', __label: 'Lang', __key: 'lang', __value: 'python' },
    ];
    const newEntries = [{ input: 'new', context_type: 'textarea', __label: 'Input', __key: 'input', __value: 'new' }];
    const property = { extra: { context: existing } };

    const result = mergePropertyContext(property, newEntries);

    expect(result.extra.context).toHaveLength(2);
    expect(result.extra.context[0]).toMatchObject({ __key: 'lang', lang: 'python' });
    expect(result.extra.context[1]).toMatchObject({ __key: 'input', input: 'new' });
  });

  it('should preserve other extra fields', () => {
    const property = { extra: { command: 'cmd-1', cite: { type: 'structured' } } };
    const entries = [{ env: 'prod', context_type: 'input', __label: 'env', __key: 'env', __value: 'prod' }];

    const result = mergePropertyContext(property, entries);

    expect(result.extra.command).toBe('cmd-1');
    expect(result.extra.cite).toEqual({ type: 'structured' });
    expect(result.extra.context).toEqual(entries);
  });
});

describe('resolveRequestOptionsContext', () => {
  it('should return empty array when requestOptions is undefined', () => {
    expect(resolveRequestOptionsContext(undefined)).toEqual([]);
  });

  it('should return empty array when requestOptions has no context', () => {
    expect(resolveRequestOptionsContext({ headers: { 'X-Test': '1' } })).toEqual([]);
  });

  it('should resolve context from plain object requestOptions', () => {
    const result = resolveRequestOptionsContext({ context: { env: 'prod' } });

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ env: 'prod', __key: 'env' });
  });

  it('should resolve context from computed ref', () => {
    const opts = computed(() => ({
      context: { env: 'prod', region: 'ap-guangzhou' },
    }));
    const result = resolveRequestOptionsContext(opts);

    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({ __key: 'env' });
    expect(result[1]).toMatchObject({ __key: 'region' });
  });

  it('should resolve context from ref', () => {
    const opts = ref({ context: { env: 'staging' } });
    const result = resolveRequestOptionsContext(opts);

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ env: 'staging', __key: 'env' });
  });

  it('should resolve context from function', () => {
    const result = resolveRequestOptionsContext(() => ({ context: { env: 'prod' } }));

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ env: 'prod', __key: 'env' });
  });

  it('should reflect dynamic changes in computed', () => {
    const envValue = ref('prod');
    const opts = computed(() => ({
      context: { env: envValue.value },
    }));

    const result1 = resolveRequestOptionsContext(opts);
    expect(result1[0]).toMatchObject({ env: 'prod' });

    envValue.value = 'staging';
    const result2 = resolveRequestOptionsContext(opts);
    expect(result2[0]).toMatchObject({ env: 'staging' });
  });
});
