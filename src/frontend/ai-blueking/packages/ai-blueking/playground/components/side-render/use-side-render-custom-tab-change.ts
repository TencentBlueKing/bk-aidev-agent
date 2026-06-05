import { shallowRef } from 'vue';

import type { OnCustomTabChange } from '@blueking/ai-blueking';

export interface SideRenderCustomFetchMeta {
  fetchedBy: 'onCustomTabChange';
  requestUrl: string;
  fetchedAt: string;
}

function normalizeApiBaseUrl(baseUrl: string): string {
  return baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
}

function unwrapResponseBody(payload: unknown): Record<string, unknown> {
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    return { raw: payload };
  }
  const record = payload as Record<string, unknown>;
  if (record.data !== undefined && typeof record.data === 'object' && record.data !== null && !Array.isArray(record.data)) {
    return record.data as Record<string, unknown>;
  }
  return record;
}

/**
 * Playground 场景 2：业务方通过 onCustomTabChange 自行拉取节点详情。
 * 演示环境仍请求 flow_agent/.../task_node_info/（与默认路径相同），便于在无独立 Mock 时联调；
 * 侧栏会标注请求 URL，便于在 Network 面板对照。
 */
export function useSideRenderCustomTabChange(apiBaseUrl: string) {
  const lastRequestUrl = shallowRef<string | null>(null);
  const lastFetchedAt = shallowRef<string | null>(null);
  const lastError = shallowRef<string | null>(null);

  const onCustomTabChange: OnCustomTabChange = async tab => {
    lastError.value = null;
    const tabProps = tab.data?.props ?? {};
    const taskId = tabProps.task_id;
    const nodeId = tabProps.node_id;

    if (taskId == null || nodeId == null || nodeId === '') {
      return {};
    }

    const base = normalizeApiBaseUrl(apiBaseUrl);
    const requestUrl = `${base}flow_agent/${taskId}/task_node_info/${nodeId}/`;
    lastRequestUrl.value = requestUrl;

    try {
      const response = await fetch(requestUrl, { credentials: 'include' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload: unknown = await response.json();
      const data = unwrapResponseBody(payload);
      const fetchedAt = new Date().toISOString();
      lastFetchedAt.value = fetchedAt;

      const meta: SideRenderCustomFetchMeta = {
        fetchedBy: 'onCustomTabChange',
        requestUrl,
        fetchedAt,
      };

      return {
        ...data,
        _demoMeta: meta,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      lastError.value = message;
      throw error;
    }
  };

  return {
    onCustomTabChange,
    lastRequestUrl,
    lastFetchedAt,
    lastError,
  };
}
