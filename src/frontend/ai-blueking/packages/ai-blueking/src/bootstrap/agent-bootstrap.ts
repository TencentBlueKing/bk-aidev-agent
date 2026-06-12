/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { IChatHelper } from '../types';
import { normalizeUrl } from '../utils';

/** 预热 SaaS 域 Cookie，失败静默忽略 */
export function pingSaasUrl(saasUrl: string): void {
  const normalizedSaasUrl = normalizeUrl(saasUrl);

  fetch(normalizedSaasUrl, {
    method: 'GET',
    credentials: 'include',
  }).catch(() => {
    // ping 请求，忽略错误
  });
}

/** 统一的 Agent 数据引导：并行拉取 Agent 信息 + 会话列表，并执行通用副作用 */
export async function runAgentBootstrap(chatHelper: IChatHelper): Promise<void> {
  await Promise.all([chatHelper.agent.getAgentInfo(), chatHelper.session.getSessions()]);

  const saasUrl = chatHelper.agent.info.value?.saasUrl;
  if (saasUrl) {
    pingSaasUrl(saasUrl);
  }
}
