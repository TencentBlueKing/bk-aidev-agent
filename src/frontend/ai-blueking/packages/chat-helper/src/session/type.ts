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

import type { IMessage } from '../message';

export interface ISession<ITool = unknown, IAnchorPathResources = unknown> {
  anchorPathResources?: IAnchorPathResources;
  comment?: string;
  createdAt?: string;
  isTemporary?: boolean;
  labels?: string[];
  model?: string;
  rate?: number;
  sessionCode: string;
  /** 会话消息数量，用于判断会话是否有内容 */
  sessionContentCount?: number;
  sessionName: string;
  tools?: ITool[];
  updatedAt?: string;
  roleInfo?: {
    collectionId: number;
    collectionName: string;
    content: IMessage[];
    variables: {
      name: string;
      value: IMessage[] | string;
    }[];
  };
  sessionProperty?: {
    isAutoCalcPrompt?: boolean;
    isAutoClear?: boolean;
  };
}

export interface ISessionApi<IToolApi = unknown, IAnchorPathResourcesApi = unknown> {
  anchor_path_resources?: IAnchorPathResourcesApi;
  comment?: string;
  created_at?: string;
  is_temporary?: boolean;
  labels?: string[];
  model?: string;
  rate?: number;
  session_code: string;
  /** 会话消息数量 */
  session_content_count?: number;
  session_name: string;
  tools?: IToolApi[];
  updated_at?: string;
  role_info?: {
    collection_id: number;
    collection_name: string;
    content: IMessage[];
    variables: {
      name: string;
      value: IMessage[] | string;
    }[];
  };
  session_property?: {
    is_auto_clac_prompt?: boolean;
    is_auto_clear?: boolean;
  };
}

export interface ISessionFeedback {
  comment: string;
  labels: string[];
  rate: number;
  sessionCode: string;
  sessionContentIds: number[];
}

export interface ISessionFeedbackApi {
  comment: string;
  lables: string[];
  rate: number;
  session_code: string;
  session_content_ids: number[];
}
