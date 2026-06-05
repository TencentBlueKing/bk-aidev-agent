import { computed, ref } from 'vue';

import type { IRequestOptions } from '@blueking/ai-blueking';

/**
 * Playground 演示用：响应式 requestOptions（headers + data + context）
 * - GET 类接口：data → query
 * - POST 类接口：data → body
 * - context → 消息的 property.extra.context（与 shortcuts 同级）
 */
export function useDemoRequestOptions() {
  const token = ref('token-alpha');
  const appId = ref('playground-app');
  const tenantId = ref('tenant-001');
  const contextEnv = ref('prod');
  const contextRegion = ref('ap-guangzhou');

  const requestOptions = computed<IRequestOptions>(() => ({
    headers: {
      Authorization: `Bearer ${token.value}`,
      'X-Playground': '1',
    },
    data: {
      app_id: appId.value,
      tenant_id: tenantId.value,
    },
    context: {
      env: contextEnv.value,
      region: contextRegion.value,
    },
  }));

  const previewJson = computed(() =>
    JSON.stringify(
      {
        headers: requestOptions.value.headers,
        data: requestOptions.value.data,
        context: requestOptions.value.context,
      },
      null,
      2,
    ),
  );

  const rotateToken = () => {
    token.value = token.value === 'token-alpha' ? 'token-beta' : 'token-alpha';
  };

  const rotateAppId = () => {
    appId.value = appId.value === 'playground-app' ? 'playground-app-v2' : 'playground-app';
  };

  const rotateTenantId = () => {
    tenantId.value = tenantId.value === 'tenant-001' ? 'tenant-002' : 'tenant-001';
  };

  const rotateContextEnv = () => {
    contextEnv.value = contextEnv.value === 'prod' ? 'staging' : 'prod';
  };

  const rotateContextRegion = () => {
    contextRegion.value = contextRegion.value === 'ap-guangzhou' ? 'ap-shanghai' : 'ap-guangzhou';
  };

  return {
    token,
    appId,
    tenantId,
    contextEnv,
    contextRegion,
    requestOptions,
    previewJson,
    rotateToken,
    rotateAppId,
    rotateTenantId,
    rotateContextEnv,
    rotateContextRegion,
  };
}
