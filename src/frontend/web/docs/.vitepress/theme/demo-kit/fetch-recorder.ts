/** 不展示的标准 / 演示内部请求头 */
export const IGNORED_HEADERS: ReadonlySet<string> = new Set([
  'accept',
  'cache-control',
  'content-type',
  'x-csrftoken',
  'x-requested-with',
  'x-mock-client',
  'x-demo-instance',
]);

/** Mock 模式下宿主为每个实例加上的请求头，用于把请求精确归到对应配方 */
export const DEMO_INSTANCE_HEADER = 'x-demo-instance';

export function readHeader(init: HeadersInit | undefined, name: string): string | undefined {
  if (!init) return undefined;
  const lower = name.toLowerCase();
  if (typeof Headers !== 'undefined' && init instanceof Headers) return init.get(name) ?? undefined;
  const pairs = Array.isArray(init) ? init : Object.entries(init);
  const hit = pairs.find(([k]) => String(k).toLowerCase() === lower);
  return hit ? String(hit[1]) : undefined;
}

export function extractCustomHeaders(init: HeadersInit | undefined): Record<string, string> {
  if (!init) return {};
  let pairs: [string, string][];
  if (typeof Headers !== 'undefined' && init instanceof Headers) {
    pairs = [...init.entries()];
  } else if (Array.isArray(init)) {
    pairs = init.map(([k, v]) => [String(k), String(v)]);
  } else {
    pairs = Object.entries(init).map(([k, v]) => [k, String(v)]);
  }
  const result: Record<string, string> = {};
  for (const [key, value] of pairs) {
    if (!IGNORED_HEADERS.has(key.toLowerCase())) result[key] = value;
  }
  return result;
}

export function parseBody(body: BodyInit | null | undefined): unknown {
  if (body === null || body === undefined) return null;
  if (typeof body === 'string') {
    try {
      return JSON.parse(body);
    } catch {
      return body;
    }
  }
  if (typeof FormData !== 'undefined' && body instanceof FormData) return '[FormData]';
  return `[${Object.prototype.toString.call(body).slice(8, -1)}]`;
}

/** base 为绝对 URL 前缀；不在 base 下返回 null */
export function splitUrl(url: string, base: string): { path: string; query: Record<string, string> | null } | null {
  let target: URL;
  let prefix: URL;
  try {
    prefix = new URL(base);
    target = new URL(url, prefix);
  } catch {
    return null;
  }
  const prefixHref = `${prefix.origin}${prefix.pathname.endsWith('/') ? prefix.pathname : `${prefix.pathname}/`}`;
  const targetHref = `${target.origin}${target.pathname}`;
  if (!targetHref.startsWith(prefixHref)) return null;
  const query = target.search ? Object.fromEntries(target.searchParams.entries()) : null;
  return { path: targetHref.slice(prefixHref.length), query };
}

export interface FetchRequestInfo {
  /** x-demo-instance 头的值（无则 undefined） */
  instance?: string;
  method: string;
  path: string;
  query: Record<string, string> | null;
  headers: Record<string, string>;
  body: unknown;
}

export interface FetchRecordHooks {
  /** 当前后端的绝对 URL 前缀 */
  getBase(): string;
  onRequest(info: FetchRequestInfo): number | undefined;
  onResponse(handle: number, info: { status: number; sse: boolean }): void;
}

interface FetchTarget {
  fetch: typeof fetch;
}

function resolveUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/**
 * 包装 target.fetch 以记录发往当前后端的请求；返回卸载函数（仅当 fetch 仍是本包装时才恢复）。
 */
export function installFetchRecorder(hooks: FetchRecordHooks, target: FetchTarget = globalThis): () => void {
  const original = target.fetch;
  const wrapped: typeof fetch = async (input, init) => {
    const url = resolveUrl(input);
    const located = splitUrl(url, hooks.getBase());
    let handle: number | undefined;
    if (located) {
      handle = hooks.onRequest({
        instance: readHeader(init?.headers, DEMO_INSTANCE_HEADER),
        method: (init?.method || (typeof input === 'object' && 'method' in input ? input.method : 'GET')).toUpperCase(),
        path: located.path,
        query: located.query,
        headers: extractCustomHeaders(init?.headers),
        body: parseBody(init?.body),
      });
    }
    const response = await original.call(target, input, init);
    if (handle !== undefined) {
      hooks.onResponse(handle, {
        status: response.status,
        sse: (response.headers.get('content-type') || '').includes('text/event-stream'),
      });
    }
    return response;
  };
  target.fetch = wrapped;
  return () => {
    if (target.fetch === wrapped) target.fetch = original;
  };
}
