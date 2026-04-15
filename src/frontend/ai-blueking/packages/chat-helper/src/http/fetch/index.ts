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

import type { IUseChatHelperOptions } from '../../type';

export type * from './fetch';

export const useFetch = (options: IUseChatHelperOptions) => {
  const fetchClient = new FetchClient({
    baseURL: options.requestData.urlPrefix,
  });

  // 用户定义拦截器
  if (options.interceptors?.request) {
    fetchClient.interceptors.request.use(options.interceptors.request);
  }
  if (options.interceptors?.response) {
    fetchClient.interceptors.response.use(options.interceptors.response);
  }

  // 重置 fetchClient 配置
  const reset = (newOptions: IUseChatHelperOptions) => {
    // 更新 baseURL
    fetchClient.defaults.baseURL = newOptions.requestData.urlPrefix;

    // 清空并重新注册拦截器
    fetchClient.interceptors.request.clear();
    fetchClient.interceptors.response.clear();

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
