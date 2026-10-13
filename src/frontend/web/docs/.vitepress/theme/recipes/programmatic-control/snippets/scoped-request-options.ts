import { shallowRef } from 'vue';

export interface ScopedOptions {
  headers?: () => Record<string, string>;
  data?: () => Record<string, unknown>;
}

/**
 * 稳定的 requestOptions：初始化时传给 AIBlueking 一次，之后每次请求都会调用这些函数。
 * 借助 runWith 可以只给「某一次」发送注入额外的 Header / body，结束后自动清除。
 */
export function createScopedRequestOptions() {
  const active = shallowRef<ScopedOptions | undefined>();

  const requestOptions = {
    headers: (): Record<string, string> => active.value?.headers?.() ?? {},
    data: (): Record<string, unknown> => ({ ...(active.value?.data?.() ?? {}) }),
  };

  async function runWith(opts: ScopedOptions, fn: () => Promise<void>): Promise<void> {
    active.value = opts;
    try {
      await fn();
    } finally {
      active.value = undefined;
    }
  }

  return { requestOptions, runWith, getActive: () => active.value };
}

/** 页面级单例：<AIBlueking :request-options="scoped.requestOptions" />，发送时用 scoped.runWith */
export const scoped = createScopedRequestOptions();
