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

import type { MaybeRequestValue, RequestHeaders } from './resolve-request-value';
import { resolveRequestValue } from './resolve-request-value';

export type { MaybeRequestValue, RequestData, RequestHeaders } from './resolve-request-value';

// API 标准响应格式
export interface ApiResponse<T = unknown> {
  code: number | string;
  data: T;
  message: string;
}

/** 单次请求配置，优先级高于 `requestData` 全局默认值 */
export interface IRequestConfig {
  baseURL?: string;
  controller?: AbortController;
  credentials?: 'include' | 'omit' | 'same-origin';
  /** 请求体；支持对象/函数/ref 延迟求值（在 `prepareRequest` 中解析） */
  data?: MaybeRequestValue<unknown>;
  /** 请求头；支持对象/函数/ref 延迟求值，便于动态注入（如 token） */
  headers?: MaybeRequestValue<RequestHeaders>;
  method?: string;
  mode?: 'cors' | 'no-cors' | 'same-origin';
  params?: Record<string, unknown>;
  responseType?: 'arrayBuffer' | 'blob' | 'formData' | 'json' | 'stream' | 'text';
  timeout?: number;
  url?: string;
  transformRequest?: (data: unknown, headers?: Record<string, string>) => unknown;
  transformResponse?: (data: unknown) => unknown;
  validateStatus?: (status: number) => boolean;
}

export interface IRequestError extends Error {
  code?: string;
  config: IRequestConfig;
  isAxiosError: boolean;
  response?: IResponse;
}

export interface IResponse<T = unknown> {
  config: IRequestConfig;
  data: T;
  headers: Headers;
  status: number;
  statusText: string;
}

export interface ISSEConfig extends ISSEProtocol, Omit<IRequestConfig, 'responseType'> {}

export interface ISSEProtocol {
  onDone?: () => void;
  onError?: (error: Error) => void;
  onMessage?: (event: unknown) => void;
  onStart?: () => void;
}

/** 全局错误处理器类型 */
export type GlobalErrorHandler = (error: IRequestError) => void;

/** 错误处理器配置 */
export interface ErrorHandlerOptions {
  /** 忽略的 URL 模式（字符串包含匹配或正则） */
  ignoreErrors?: Array<string | RegExp>;
}

interface IInterceptor<T> {
  fulfilled?: (value: T) => T;
  rejected?: (error: unknown) => unknown;
}

class InterceptorManager<T> {
  private handlers: (IInterceptor<T> | null)[] = [];

  clear(): void {
    this.handlers = [];
  }

  eject(id: number): void {
    if (this.handlers[id]) {
      this.handlers[id] = null;
    }
  }

  forEach(fn: (interceptor: IInterceptor<T>) => void): void {
    this.handlers.forEach(handler => {
      if (handler !== null) {
        fn(handler);
      }
    });
  }

  use(fulfilled?: (value: T) => T, rejected?: (error: unknown) => unknown): number {
    this.handlers.push({ fulfilled, rejected });
    return this.handlers.length - 1;
  }
}

export class FetchClient {
  defaults: IRequestConfig;

  interceptors: {
    request: InterceptorManager<IRequestConfig>;
    response: InterceptorManager<IResponse>;
  };

  /** 全局错误处理器 */
  private globalErrorHandler?: GlobalErrorHandler;
  /** 忽略的错误 URL 模式 */
  private ignoreErrorPatterns: Array<string | RegExp> = [];

  constructor(config: IRequestConfig = {}) {
    this.defaults = mergeConfig(
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: 30000,
        responseType: 'json',
        credentials: 'include',
        mode: 'cors',
        validateStatus: status => status >= 200 && status < 300,
      },
      config,
    );

    this.interceptors = {
      request: new InterceptorManager<IRequestConfig>(),
      response: new InterceptorManager<IResponse>(),
    };
  }

  /**
   * 注册全局错误处理器
   * 所有 HTTP 错误（request 和 streamRequest）都会经过此处理器
   */
  onError(handler: GlobalErrorHandler, options?: ErrorHandlerOptions): void {
    this.globalErrorHandler = handler;
    if (options?.ignoreErrors) {
      this.ignoreErrorPatterns = options.ignoreErrors;
    }
  }

  /** 判断是否应忽略该错误 */
  private shouldIgnoreError(error: IRequestError): boolean {
    // 同时匹配相对路径和完整 URL
    const url = error.config?.url || '';
    const baseURL = error.config?.baseURL || '';
    const fullURL = baseURL && !url.startsWith('http') ? baseURL + url : url;

    return this.ignoreErrorPatterns.some(pattern => {
      if (typeof pattern === 'string') {
        // 字符串模式：同时检查相对路径和完整 URL
        return url.includes(pattern) || fullURL.includes(pattern);
      }
      // 正则模式：同时检查相对路径和完整 URL
      return pattern.test(url) || pattern.test(fullURL);
    });
  }

  /** 统一错误分发 */
  private dispatchError(error: IRequestError): void {
    if (this.globalErrorHandler && !this.shouldIgnoreError(error)) {
      this.globalErrorHandler(error);
    }
  }

  applyResponseErrorInterceptors(error: unknown): unknown {
    let rejectedError: unknown = error;
    this.interceptors.response.forEach(interceptor => {
      if (interceptor.rejected) {
        rejectedError = interceptor.rejected(rejectedError);
      }
    });
    return rejectedError;
  }

  create(config?: IRequestConfig): FetchClient {
    return new FetchClient(mergeConfig(this.defaults, config || {}));
  }

  delete<T = unknown>(url: string, params?: Record<string, unknown>, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'DELETE', params });
  }

  get<T = unknown>(url: string, params?: Record<string, unknown>, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'GET', params });
  }

  head<T = unknown>(url: string, params?: Record<string, unknown>, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'HEAD', params });
  }

  options<T = unknown>(url: string, params?: Record<string, unknown>, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'OPTIONS', params });
  }

  patch<T = unknown>(url: string, data?: unknown, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'PATCH', data });
  }

  post<T = unknown>(url: string, data?: unknown, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'POST', data });
  }

  prepareRequest(config: IRequestConfig, isStream = false) {
    const mergedConfig = mergeConfig(this.defaults, config);
    let requestConfig = mergedConfig;

    this.interceptors.request.forEach(interceptor => {
      if (interceptor.fulfilled) {
        try {
          requestConfig = interceptor.fulfilled(requestConfig);
        } catch (error) {
          if (interceptor.rejected) {
            throw interceptor.rejected(error);
          }
          throw error;
        }
      }
    });

    let url = requestConfig.url || '';
    if (requestConfig.baseURL && !url.startsWith('http')) {
      url = requestConfig.baseURL + url;
    }
    url = buildURL(url, requestConfig.params);

    let body: BodyInit | null | undefined = getValue(requestConfig.data) as BodyInit | null | undefined;
    const headers = new Headers(getValue(requestConfig.headers));

    if (isStream && !headers.has('Accept')) {
      headers.set('Accept', 'text/event-stream');
    }

    if (body !== undefined && body !== null) {
      if (requestConfig.transformRequest) {
        body = requestConfig.transformRequest(body, getValue(requestConfig.headers)) as BodyInit | null | undefined;
      } else if (
        headers.get('Content-Type')?.includes('application/json') &&
        typeof body === 'object' &&
        !(body instanceof FormData) &&
        !(body instanceof Blob) &&
        !(body instanceof ArrayBuffer)
      ) {
        body = JSON.stringify(body);
      }
    }

    const controller = requestConfig.controller ?? new AbortController();
    const fetchConfig = {
      method: requestConfig.method,
      credentials: requestConfig.credentials,
      mode: requestConfig.mode,
      headers,
      body,
      signal: controller.signal,
    };

    return {
      url,
      requestConfig,
      fetchConfig,
      controller,
    };
  }

  put<T = unknown>(url: string, data?: unknown, config?: IRequestConfig): Promise<T> {
    return this.request<T>({ ...config, url, method: 'PUT', data });
  }

  async request<T = unknown>(config: IRequestConfig): Promise<T> {
    const { url, fetchConfig, requestConfig, controller } = this.prepareRequest(config);

    const timeoutId =
      requestConfig.timeout && requestConfig.timeout > 0
        ? setTimeout(() => controller.abort(), requestConfig.timeout)
        : undefined;

    try {
      const fetchResponse = await fetch(url, fetchConfig);

      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      let data: unknown;
      const responseType = requestConfig.responseType || 'json';

      try {
        switch (responseType) {
          case 'json':
            data = await fetchResponse.json();
            break;
          case 'text':
            data = await fetchResponse.text();
            break;
          case 'blob':
            data = await fetchResponse.blob();
            break;
          case 'arrayBuffer':
            data = await fetchResponse.arrayBuffer();
            break;
          case 'formData':
            data = await fetchResponse.formData();
            break;
          default:
            data = await fetchResponse.json();
        }
      } catch (_error) {
        data = null;
      }

      if (requestConfig.transformResponse) {
        data = requestConfig.transformResponse(data);
      }

      const response: IResponse<ApiResponse<T>> = {
        data: data as ApiResponse<T>,
        status: fetchResponse.status,
        statusText: fetchResponse.statusText,
        headers: fetchResponse.headers,
        config: requestConfig,
      };

      const validateStatus = requestConfig.validateStatus || this.defaults.validateStatus!;
      if (!validateStatus(fetchResponse.status)) {
        const message =
          (response.data as { error?: { message: string } })?.error?.message ||
          `Request failed with status code ${fetchResponse.status}`;
        throw createError(message, requestConfig, `ERR_BAD_RESPONSE`, response);
      }

      let finalResponse: IResponse<ApiResponse<T>> = response;
      this.interceptors.response.forEach(interceptor => {
        if (interceptor.fulfilled) {
          try {
            finalResponse = interceptor.fulfilled(finalResponse) as IResponse<ApiResponse<T>>;
          } catch (error) {
            if (interceptor.rejected) {
              throw interceptor.rejected(error);
            }
            throw error;
          }
        }
      });

      if (finalResponse instanceof Promise) {
        finalResponse = await finalResponse;
      }

      // 检查业务状态码（区别于 HTTP 状态码）
      const apiResponse = finalResponse.data as ApiResponse<T>;
      if (![0, 'success'].includes(apiResponse.code)) {
        throw createError(apiResponse.message, requestConfig, apiResponse.code, finalResponse);
      }

      return apiResponse.data;
    } catch (error: unknown) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      // 用户手动取消请求
      if (error instanceof Error && error.name === 'AbortError') {
        console.warn('User canceled request', error.message);
        return;
      }

      const requestError =
        (error as IRequestError).isAxiosError === true
          ? (error as IRequestError)
          : createError((error as Error).message, requestConfig, (error as IRequestError).code, undefined);

      this.dispatchError(requestError);
      throw this.applyResponseErrorInterceptors(requestError);
    }
  }

  stream(url: string, config?: ISSEConfig) {
    return this.streamRequest({ ...config, url });
  }

  async streamRequest(config: ISSEConfig) {
    // 错误去重：标记是否已调用过全局错误处理器
    let errorDispatched = false;

    // 包装 onError 回调，统一调用全局错误处理器
    const originalOnError = config.onError;
    const wrappedOnError = (error: Error) => {
      if (!errorDispatched) {
        // 将 requestConfig 附加到错误对象，以便 shouldIgnoreError 能匹配 URL
        const errorWithConfig = error as IRequestError;
        if (!errorWithConfig.config) {
          errorWithConfig.config = requestConfig;
        }
        this.dispatchError(errorWithConfig);
        errorDispatched = true;
      }
      originalOnError?.(error);
    };

    const wrappedConfig = { ...config, onError: wrappedOnError };
    const { url, fetchConfig, requestConfig } = this.prepareRequest(wrappedConfig, true);

    try {
      const fetchResponse = await fetch(url, fetchConfig);

      const validateStatus = requestConfig.validateStatus || this.defaults.validateStatus!;
      if (!validateStatus(fetchResponse.status)) {
        let message = `Request failed with status code ${fetchResponse.status}`;
        try {
          const errorData = await fetchResponse.json();
          if (errorData?.error?.message) {
            message = errorData.error.message;
          }
        } catch (_error) {
          message = `Request failed with status code ${fetchResponse.status}`;
        }
        const error = createError(message, requestConfig, `ERR_BAD_RESPONSE`, undefined);
        wrappedOnError(error);
        return;
      }

      wrappedConfig.onStart?.();

      const reader = fetchResponse.body?.pipeThrough(new window.TextDecoderStream()).getReader();
      if (!reader) {
        const error = new Error('IResponse body is not readable');
        wrappedOnError(error);
        return;
      }

      // 缓存跨行分片数据
      let temp = '';

      const isJson = (str: string): boolean => {
        try {
          JSON.parse(str);
          return true;
        } catch (_error) {
          return false;
        }
      };

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          wrappedConfig.onDone?.();
          break;
        }

        const values = (temp + value.toString()).split('\n');
        values.forEach(value => {
          const item = value.replace('data:', '').trim();
          if (isJson(item)) {
            const json = JSON.parse(item);
            wrappedConfig.onMessage?.(json);
            temp = '';
          } else if (item) {
            temp = item;
          }
        });
      }
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          wrappedConfig.onDone?.();
          return;
        }
        wrappedOnError(error);
      }
      throw error;
    }
  }
}

function buildURL(url: string, params?: Record<string, unknown>): string {
  if (!params) return url;

  const searchParams = new URLSearchParams();
  Object.keys(params).forEach(key => {
    const value = params[key];
    if (value !== null && value !== undefined) {
      if (Array.isArray(value)) {
        value.forEach(v => searchParams.append(key, String(v)));
      } else {
        searchParams.append(key, String(value));
      }
    }
  });

  const queryString = searchParams.toString();
  if (queryString) {
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}${queryString}`;
  }

  return url;
}

function createError(
  message: string,
  config: IRequestConfig,
  code?: number | string,
  response?: IResponse,
): IRequestError {
  const error = new Error(message) as IRequestError;
  error.config = config;
  error.code = String(code);
  error.response = response;
  error.isAxiosError = true;
  return error;
}

function getValue<T>(value: MaybeRequestValue<T> | undefined): T | undefined {
  return resolveRequestValue(value);
}

/** 排除 AbortController、Headers 等类实例，只对普通对象深度合并 */
function isPlainObject(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function mergeConfig(config1: IRequestConfig, config2: IRequestConfig): IRequestConfig {
  const output: Record<string, unknown> = { ...config1 };

  for (const key in config2) {
    const value2 = config2[key as keyof IRequestConfig];
    if (isPlainObject(value2)) {
      const value1 = config1[key as keyof IRequestConfig];
      output[key] = mergeConfig((value1 as IRequestConfig) || {}, value2 as IRequestConfig);
    } else {
      output[key] = value2;
    }
  }

  return output as IRequestConfig;
}

const fetchClient = new FetchClient();

export default fetchClient;
