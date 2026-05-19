/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { resolveRequestValue } from '@blueking/chat-helper';
import { toValue, type MaybeRefOrGetter } from 'vue';

import type { IRequestOptions } from '../types';
import type {
  IUseChatHelperOptions,
  MaybeRequestValue,
  RequestData,
  RequestHeaders,
} from '@blueking/chat-helper';

/**
 * 将外层 requestOptions（可为 ref/computed/函数）转为 chat-helper 的 requestData。
 * 使用稳定 getter，每次请求时读取最新的 headers/data。
 */
export function buildRequestDataFromOptions(
  urlPrefix: string,
  requestOptions?: MaybeRefOrGetter<IRequestOptions | undefined>,
): IUseChatHelperOptions['requestData'] {
  const resolveHeaders = (): RequestHeaders | undefined => {
    const opts = toValue(requestOptions);
    return resolveRequestValue(opts?.headers);
  };

  const resolveData = (): RequestData | undefined => {
    const opts = toValue(requestOptions);
    return resolveRequestValue(opts?.data);
  };

  return {
    urlPrefix,
    headers: resolveHeaders as MaybeRequestValue<RequestHeaders>,
    data: resolveData as MaybeRequestValue<RequestData>,
  };
}
