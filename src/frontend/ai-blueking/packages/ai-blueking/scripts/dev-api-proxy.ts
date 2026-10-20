/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import type { ProxyOptions } from 'vite';

/** 浏览器只打这个同域前缀，由开发服务转发到 API_PROXY_TARGET */
export const DEV_API_PREFIX = '/dev-api';

/**
 * 本地页面和 bkapps 不同源，浏览器直连会被 CORS 拦截。
 * 只在 dev server 做反向代理，组件实际请求地址仍由 VITE_API_URL 决定。
 */
export const createDevApiProxy = (proxyTarget: string): Record<string, ProxyOptions> | undefined => {
  if (!proxyTarget) {
    console.warn('[ai-blueking dev] 未配置 API_PROXY_TARGET，/dev-api 不会转发到后端');
    return undefined;
  }

  const targetUrl = new URL(proxyTarget);
  const upstreamPath = targetUrl.pathname.replace(/\/$/, '');

  return {
    [DEV_API_PREFIX]: {
      target: targetUrl.origin,
      changeOrigin: true,
      rewrite: path => {
        const suffix = path.replace(new RegExp(`^${DEV_API_PREFIX}`), '') || '/';
        const normalizedSuffix = suffix.startsWith('/') ? suffix : `/${suffix}`;
        return `${upstreamPath}${normalizedSuffix}`;
      },
    },
  };
};
