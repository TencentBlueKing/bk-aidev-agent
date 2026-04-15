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
import type { Component } from 'vue';
export type CustomBkFlowTab = CustomTab<CustomBkFlowTabData>;

export type CustomBkFlowTabData = CustomTabData<{
  data?: Partial<NodeDetailData>;
  loading?: boolean;
  node_id?: string;
  node_name?: string;
  task_id?: number;
  task_name?: string;
}>;

export type CustomTab<T extends CustomTabData<Record<string, unknown>>> = {
  data?: T;
  icon?: string;
  label: string; // 显示标签
  name: string; // 唯一标识
};

export type CustomTabData<T extends Record<string, unknown>> = {
  component?: Component; // 自定义 Tab 渲染组件
  props?: T; // 自定义 Tab 渲染组件的 props
};

export interface NodeDetailData {
  inputs: Record<string, unknown>;
  node_id: string;
  task_id: number;
  basic_info: {
    auto_retry: {
      enable: boolean;
      interval: number;
      times: number;
    };
    error_ignorable: boolean;
    node_name: string;
    optional: boolean;
    retryable: boolean;
    skippable: boolean;
    stage_name: string;
    template_name: string;
    timeout_config: {
      action: string;
      enable: boolean;
      seconds: number;
    };
  };
  outputs: Array<{
    key: string;
    preset: boolean;
    value: unknown;
  }>;
  plugin_output: Array<{
    key: string;
    name: string;
    schema: {
      description: string;
      enum: unknown[];
      properties?: Record<string, unknown>;
      type: string;
    };
    type: string;
  }>;
}
