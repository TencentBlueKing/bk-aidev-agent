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

/** 模型能力标签，如「图生文」「深度思考」「快速思考」（由组件依据 property 派生，走内置 i18n） */
export interface IModelCapability {
  /** 标签文案 */
  text: string;
  /** 语义主题，决定标签配色，缺省为 default */
  theme?: ModelCapabilityTheme;
}

/** 模型选项（贴合后端模型接口结构） */
import type { Component } from 'vue';

export interface IModelOption {
  /** 基础模型标识，如 deepseek */
  base_model?: string;
  /** 模型描述，作为选项 hover 的 title 提示 */
  description?: string;
  /** 是否禁用（前端扩展字段，后端无此字段时默认不禁用） */
  disabled?: boolean;
  /** 模型图标：URL 字符串或 Vue 组件 */
  icon?: Component | string;
  /** 模型主键 id */
  id: number;
  /** 模型编码 */
  llm_code: string;
  /** 模型展示名，同时作为选中值（v-model:selectedModel） */
  llm_name: string;
  /** 模型类型，如 chat.completion */
  llm_type: string;
  /** 最大 token 数 */
  max_token_size: number;
  /** 模型能力属性，用于派生能力标签 */
  property: IModelProperty;
  /** 空间维度鉴权模式，如 APPLY */
  space_auth_mode: string;
  /** 标签名列表 */
  tag_names?: string[];
  /** 用户维度鉴权模式，如 PUBLIC */
  user_auth_mode: string;
}

/** 模型属性（后端 property 字段），描述模型支持的能力开关与运行参数 */
export interface IModelProperty {
  /** 智能体类型，如 openai */
  agent_type?: string;
  /** 是否为默认模型 */
  default?: boolean;
  /** 是否自建部署 */
  is_self_host?: boolean;
  /** 模型最大上下文长度 */
  max_model_len?: number;
  /** 是否支持摘要 */
  support_summary?: boolean;
  /** 是否支持深度思考 */
  support_thinking?: boolean;
  /** 是否支持快速思考 */
  support_thinking_quick?: boolean;
  /** 是否支持工具调用 */
  support_tools?: boolean;
  /** 是否支持图生文（视觉） */
  support_vision?: boolean;
  /** 是否支持上下文窗口 */
  support_window?: boolean;
}

/** 模型能力标签的语义主题，决定标签配色（与设计稿语义色一一对应） */
export type ModelCapabilityTheme = 'default' | 'primary' | 'success' | 'warning';
