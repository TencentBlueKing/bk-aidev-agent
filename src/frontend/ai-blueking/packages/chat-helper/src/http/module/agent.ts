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
import { transferAgentInfoApi2AgentInfo, transferLlmListApi2LlmItems } from '../transform/agent';

import type { IAgentInfoApi, ILlmItem, ILlmItemApi, ILlmListQuery } from '../../agent/type';
import type { FetchClient, IRequestConfig } from '../fetch';

/**
 * agent 相关 http 接口
 * @param fetchClient - 请求客户端
 * @returns agent 相关 http 接口
 */
export const useAgent = (fetchClient: FetchClient) => {
  // 获取 agent 信息
  const getAgentInfo = (config?: IRequestConfig) =>
    fetchClient.get<IAgentInfoApi>('agent/info/', undefined, config).then(transferAgentInfoApi2AgentInfo);

  /**
   * 获取当前空间可用模型列表（公开 + 空间授权 + 用户权限交集）
   * @param params 查询参数；未传 llm_type 时默认 chat.completion
   */
  const getLlms = (params?: ILlmListQuery, config?: IRequestConfig): Promise<ILlmItem[]> => {
    const query: Record<string, unknown> = {
      llm_type: params?.llm_type ?? 'chat.completion',
    };
    if (params?.fuzzy) {
      query.fuzzy = params.fuzzy;
    }
    if (params?.supports) {
      query.supports = params.supports;
    }
    return fetchClient.get<ILlmItemApi[]>('llms/', query, config).then(transferLlmListApi2LlmItems);
  };

  return {
    getAgentInfo,
    getLlms,
  };
};
