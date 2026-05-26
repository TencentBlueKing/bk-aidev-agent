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

import { FetchClient } from './fetch';
import { resolveRequestValue } from './resolve-request-value';

import type { IRequestConfig } from './fetch';
import type { IUseChatHelperOptions } from '../../type';

export { FetchClient } from './fetch';
export type * from './fetch';
export type { MaybeRequestValue, RequestData, RequestHeaders } from './resolve-request-value';
export { resolveRequestValue } from './resolve-request-value';

/** 使用请求体的 HTTP 方法 */
const BODY_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/** 无请求体、通过 query 传参的 HTTP 方法 */
const QUERY_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

/** 排除 FormData / Blob / ArrayBuffer 等，只对普通对象展开合并 */
function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

/**
 * 注册全局默认请求配置拦截器，将 `requestData.headers/data` 自动合并到每次请求。
 * - `headers` 注入所有请求
 * - `data` 对 POST/PUT/PATCH/DELETE 合并进 body；对 GET/HEAD/OPTIONS 合并进 query（params）
 * - 优先级最低（单次 IRequestConfig > 用户拦截器 > 本拦截器）。
 */
function registerRequestDataInterceptor(client: FetchClient, opts: IUseChatHelperOptions): void {
  const { headers: extraHeadersFn, data: extraDataFn } = opts.requestData;
  if (!extraHeadersFn && !extraDataFn) return;

  client.interceptors.request.use((config: IRequestConfig): IRequestConfig => {
    let result = config;
    const method = (config.method ?? 'GET').toUpperCase();

    if (extraHeadersFn) {
      const extra = resolveRequestValue(extraHeadersFn);
      if (extra && Object.keys(extra).length > 0) {
        const existing = resolveRequestValue(config.headers) ?? {};
        result = { ...result, headers: { ...existing, ...extra } };
      }
    }

    if (extraDataFn) {
      const extra = resolveRequestValue(extraDataFn);
      if (extra && Object.keys(extra).length > 0) {
        if (BODY_METHODS.has(method)) {
          const existing = resolveRequestValue(config.data);
          if (existing == null) {
            // body 为空（如 clearSession POST undefined）：直接用 extra 作为 body
            result = { ...result, data: extra };
          } else if (isPlainObject(existing)) {
            // body 是普通对象：浅合并，extra 字段优先级更低（existing 已有同名字段时保留）
            result = { ...result, data: { ...extra, ...(existing as Record<string, unknown>) } };
          } else {
            // body 是 FormData / Blob / string 等：跳过注入，避免破坏原始 body
            console.warn(
              '[chat-helper] requestData.data 无法注入：当前请求体不是普通对象（FormData/Blob/string 等），已跳过合并。',
              { method, existingType: typeof existing },
            );
          }
        } else if (QUERY_METHODS.has(method)) {
          const existingParams = config.params ?? {};
          // query 浅合并，extra 优先级更低（单次请求的 params 同名字段优先）
          result = { ...result, params: { ...extra, ...existingParams } };
        }
      }
    }

    return result;
  });
}

export const useFetch = (options: IUseChatHelperOptions) => {
  const fetchClient = new FetchClient({
    baseURL: options.requestData.urlPrefix,
  });

  // 先注册默认拦截器（优先级低），再注册用户拦截器（优先级高）
  registerRequestDataInterceptor(fetchClient, options);

  if (options.interceptors?.request) {
    fetchClient.interceptors.request.use(options.interceptors.request);
  }
  if (options.interceptors?.response) {
    fetchClient.interceptors.response.use(options.interceptors.response);
  }

  // 重置 fetchClient 配置
  const reset = (newOptions: IUseChatHelperOptions) => {
    fetchClient.defaults.baseURL = newOptions.requestData.urlPrefix;

    // 清空并重新注册所有拦截器
    fetchClient.interceptors.request.clear();
    fetchClient.interceptors.response.clear();

    registerRequestDataInterceptor(fetchClient, newOptions);

    if (newOptions.interceptors?.request) {
      fetchClient.interceptors.request.use(newOptions.interceptors.request);
    }
    if (newOptions.interceptors?.response) {
      fetchClient.interceptors.response.use(newOptions.interceptors.response);
    }
  };

  return {
    fetchClient,
    reset,
  };
};
