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

// API 标准响应格式
export interface ApiResponse<T = unknown> {
  code: number | string;
  data: T;
  message: string;
}

// 请求配置接口
export interface IRequestConfig {
  baseURL?: string;
  controller?: AbortController;
  credentials?: 'include' | 'omit' | 'same-origin';
  data?: (() => unknown) | unknown;
  headers?: (() => Record<string, string>) | Record<string, string>;
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

// 错误接口
export interface IRequestError extends Error {
  code?: string;
  config: IRequestConfig;
  isAxiosError: boolean;
  response?: IResponse;
}

// 响应接口
export interface IResponse<T = unknown> {
  config: IRequestConfig;
  data: T;
  headers: Headers;
  status: number;
  statusText: string;
}

// SSE 配置接口
export interface ISSEConfig extends ISSEProtocol, Omit<IRequestConfig, 'responseType'> {}

export interface ISSEProtocol {
  onDone?: () => void;
  onError?: (error: Error) => void;
  onMessage?: (event: unknown) => void;
  onStart?: () => void;
}

// 拦截器接口
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

  // 应用响应拦截器的错误处理
  applyResponseErrorInterceptors(error: unknown): unknown {
    let rejectedError: unknown = error;
    this.interceptors.response.forEach(interceptor => {
      if (interceptor.rejected) {
        rejectedError = interceptor.rejected(rejectedError);
      }
    });
    return rejectedError;
  }

  // 创建新实例
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

  // 准备请求：合并配置、应用拦截器、构建 URL 和请求体
  prepareRequest(config: IRequestConfig, isStream = false) {
    // 合并配置
    const mergedConfig = mergeConfig(this.defaults, config);

    // 总的请求配置
    let requestConfig = mergedConfig;

    // 应用请求拦截器
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

    // 构建完整 URL
    let url = requestConfig.url || '';
    if (requestConfig.baseURL && !url.startsWith('http')) {
      url = requestConfig.baseURL + url;
    }
    url = buildURL(url, requestConfig.params);

    // 处理请求体
    let body: BodyInit | null | undefined = getValue(requestConfig.data) as BodyInit | null | undefined;
    const headers = new Headers(getValue(requestConfig.headers));

    // 流式请求设置 Accept 头
    if (isStream && !headers.has('Accept')) {
      headers.set('Accept', 'text/event-stream');
    }

    // 处理请求体
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

    // 创建 AbortController
    const controller = requestConfig.controller ? requestConfig.controller : new AbortController();

    // 请求配置
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
    // 准备请求
    const { url, fetchConfig, requestConfig, controller } = this.prepareRequest(config);

    // 创建超时控制
    const timeoutId =
      requestConfig.timeout && requestConfig.timeout > 0
        ? setTimeout(() => controller.abort(), requestConfig.timeout)
        : undefined;

    try {
      // 发送请求
      const fetchResponse = await fetch(url, fetchConfig);

      // 清除超时定时器
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      // 解析响应数据
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

      // 应用响应转换
      if (requestConfig.transformResponse) {
        data = requestConfig.transformResponse(data);
      }

      // 构建响应对象
      const response: IResponse<ApiResponse<T>> = {
        data: data as ApiResponse<T>,
        status: fetchResponse.status,
        statusText: fetchResponse.statusText,
        headers: fetchResponse.headers,
        config: requestConfig,
      };

      // 验证状态码
      const validateStatus = requestConfig.validateStatus || this.defaults.validateStatus!;
      if (!validateStatus(fetchResponse.status)) {
        const message =
          (response.data as { error?: { message: string } })?.error?.message ||
          `Request failed with status code ${fetchResponse.status}`;
        throw createError(message, requestConfig, `ERR_BAD_RESPONSE`, response);
      }

      // 应用响应拦截器
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

      // 等待所有异步拦截器完成
      if (finalResponse instanceof Promise) {
        finalResponse = await finalResponse;
      }

      // 检查业务逻辑状态码
      const apiResponse = finalResponse.data as ApiResponse<T>;
      if (![0, 'success'].includes(apiResponse.code)) {
        throw createError(apiResponse.message, requestConfig, apiResponse.code, finalResponse);
      }

      return apiResponse.data;
    } catch (error: unknown) {
      // 清除超时定时器
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      // 处理中断错误
      if (error instanceof Error && error.name === 'AbortError') {
        const requestError = createError('Request timeout', requestConfig, 'ECONNABORTED', undefined);
        throw this.applyResponseErrorInterceptors(requestError);
      }

      // 处理其他错误
      const requestError =
        (error as IRequestError).isAxiosError === true
          ? (error as IRequestError)
          : createError((error as Error).message, requestConfig, (error as IRequestError).code, undefined);

      throw this.applyResponseErrorInterceptors(requestError);
    }
  }

  // SSE 流式请求便捷方法
  stream(url: string, config?: ISSEConfig) {
    return this.streamRequest({ ...config, url });
  }

  // SSE 流式请求
  async streamRequest(config: ISSEConfig) {
    // 准备请求（标记为流式请求）
    const { url, fetchConfig, requestConfig } = this.prepareRequest(config, true);

    try {
      // 发送请求
      const fetchResponse = await fetch(url, fetchConfig);

      // 验证状态码
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
        config.onError?.(error);
        return;
      }

      // 触发 onStart 回调
      config.onStart?.();

      // 获取 reader
      const reader = fetchResponse.body?.pipeThrough(new window.TextDecoderStream()).getReader();
      if (!reader) {
        const error = new Error('IResponse body is not readable');
        config.onError?.(error);
        return;
      }

      // 临时存储数据
      let temp = '';

      // 判断是否为 JSON 字符串
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

        // 接口完成
        if (done) {
          config.onDone?.();
          break;
        }

        const values = (temp + value.toString()).split('\n');
        values.forEach(value => {
          const item = value.replace('data:', '').trim();
          if (isJson(item)) {
            const json = JSON.parse(item);
            config.onMessage?.(json);
            temp = '';
          } else if (item) {
            temp = item;
          }
        });
      }
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          config.onDone?.();
        } else {
          config.onError?.(error);
        }
      }
      throw error;
    }
  }
}

// 构建完整 URL
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

// 创建错误对象
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

// 获取值
function getValue<T>(value: (() => T) | T): T {
  return typeof value === 'function' ? (value as () => T)() : value;
}

// 判断是否是普通对象（排除类实例如 AbortController、Headers 等）
function isPlainObject(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

// 合并配置
function mergeConfig(config1: IRequestConfig, config2: IRequestConfig): IRequestConfig {
  const output: Record<string, unknown> = { ...config1 };

  for (const key in config2) {
    const value2 = config2[key as keyof IRequestConfig];
    // 只对普通对象进行深度合并，类实例（如 AbortController）直接赋值
    if (isPlainObject(value2)) {
      const value1 = config1[key as keyof IRequestConfig];
      output[key] = mergeConfig((value1 as IRequestConfig) || {}, value2 as IRequestConfig);
    } else {
      output[key] = value2;
    }
  }

  return output as IRequestConfig;
}

// 创建默认实例
const fetchClient = new FetchClient();

// 导出默认实例
export default fetchClient;
