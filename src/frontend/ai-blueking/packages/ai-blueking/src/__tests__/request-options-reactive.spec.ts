import { computed, ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FetchClient, useFetch } from '@blueking/chat-helper';
import { buildRequestDataFromOptions } from '../utils/build-request-data';

describe('requestData reactive integration', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ code: 0, data: {}, message: 'ok' }),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('merges reactive ref headers on each request', async () => {
    const authToken = ref('token-a');
    const headers = computed(() => ({ Authorization: `Bearer ${authToken.value}` }));

    const { fetchClient } = useFetch({
      requestData: {
        urlPrefix: 'https://api.example.com/',
        headers,
      },
    });

    await fetchClient.get('agent/');
    const firstCall = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(firstCall?.[1]?.headers?.get('Authorization')).toBe('Bearer token-a');

    authToken.value = 'token-b';
    await fetchClient.get('agent/');
    const secondCall = (fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(secondCall?.[1]?.headers?.get('Authorization')).toBe('Bearer token-b');
  });

  it('merges data into GET query params instead of body', async () => {
    const appId = ref('app-1');
    const { fetchClient } = useFetch({
      requestData: {
        urlPrefix: 'https://api.example.com/',
        data: computed(() => ({ app_id: appId.value })),
      },
    });

    await fetchClient.get('sessions/', { page: '1' });
    let call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call?.[0]).toBe('https://api.example.com/sessions/?app_id=app-1&page=1');
    expect(call?.[1]?.body).toBeUndefined();

    appId.value = 'app-2';
    await fetchClient.get('sessions/');
    call = (fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(call?.[0]).toBe('https://api.example.com/sessions/?app_id=app-2');
  });

  it('merges reactive data into POST body', async () => {
    const appId = ref('app-1');
    const data = computed(() => ({ app_id: appId.value }));

    const { fetchClient } = useFetch({
      requestData: {
        urlPrefix: 'https://api.example.com/',
        data,
      },
    });

    await fetchClient.post('sessions/', { name: 'test' });
    let call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(call?.[1]?.body as string)).toEqual({
      app_id: 'app-1',
      name: 'test',
    });

    appId.value = 'app-2';
    await fetchClient.post('sessions/', { name: 'test2' });
    call = (fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(JSON.parse(call?.[1]?.body as string)).toEqual({
      app_id: 'app-2',
      name: 'test2',
    });
  });

  it('skips data merge for non-plain body', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const { fetchClient } = useFetch({
      requestData: {
        urlPrefix: 'https://api.example.com/',
        data: { global: true },
      },
    });

    const blob = new Blob(['x']);
    await fetchClient.post('upload/', blob);
    const call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call?.[1]?.body).toBe(blob);
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});

describe('buildRequestDataFromOptions', () => {
  it('reads latest outer requestOptions on each resolve', () => {
    const outer = ref<{ headers?: Record<string, string> }>({
      headers: { 'X-Tenant': 'a' },
    });

    const requestData = buildRequestDataFromOptions('https://api.example.com/', outer);

    expect(typeof requestData.headers).toBe('function');
    expect((requestData.headers as () => Record<string, string> | undefined)()).toEqual({
      'X-Tenant': 'a',
    });

    outer.value = { headers: { 'X-Tenant': 'b' } };
    expect((requestData.headers as () => Record<string, string> | undefined)()).toEqual({
      'X-Tenant': 'b',
    });
  });

  it('supports replacing entire requestOptions ref', () => {
    const outer = ref({
      headers: { 'X-App': 'v1' },
      data: { app_id: '1' },
    });

    const requestData = buildRequestDataFromOptions('https://api.example.com/', outer);

    outer.value = {
      headers: { 'X-App': 'v2' },
      data: { app_id: '2' },
    };

    expect((requestData.headers as () => Record<string, string> | undefined)()).toEqual({
      'X-App': 'v2',
    });
    expect((requestData.data as () => Record<string, unknown> | undefined)()).toEqual({
      app_id: '2',
    });
  });
});

describe('FetchClient per-request config', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ code: 0, data: {}, message: 'ok' }),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resolves ref headers in IRequestConfig', async () => {
    const client = new FetchClient({ baseURL: 'https://api.example.com/' });
    const traceId = ref('id-1');

    await client.get('test/', undefined, {
      headers: computed(() => ({ 'X-Trace': traceId.value })),
    });

    let call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call?.[1]?.headers?.get('X-Trace')).toBe('id-1');

    traceId.value = 'id-2';
    await client.get('test/', undefined, {
      headers: computed(() => ({ 'X-Trace': traceId.value })),
    });

    call = (fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(call?.[1]?.headers?.get('X-Trace')).toBe('id-2');
  });
});
