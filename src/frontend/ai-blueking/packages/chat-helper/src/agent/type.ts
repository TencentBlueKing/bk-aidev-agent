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

import type { IMessage } from '../message/type';

export interface ISupportUpload {
  vision: boolean;
}

export interface IAgentCommand {
  agentId: number;
  alias?: string;
  components: IAgentCommandComponent[];
  content: null | string;
  icon?: string;
  id: string;
  name: string;
  status: string;
  supportUpload?: ISupportUpload;
}

export interface IAgentCommandApi {
  agent_id: number;
  alias?: string;
  components: IAgentCommandComponentApi[];
  content: null | string;
  icon: string;
  id: string;
  name: string;
  selectedText?: null | string;
  status: string;
  support_upload?: ISupportUpload;
}

export interface IAgentCommandComponent {
  default?: null | string;
  fillBack?: boolean;
  fillRegx?: null | string;
  hide?: boolean;
  key: string;
  max?: null | number;
  min?: null | number;
  name: string;
  options?: unknown;
  placeholder?: null | string;
  required?: boolean;
  rows?: null | number;
  selectedText?: null | string;
  showSendButton?: boolean;
  type: string;
}

export interface IAgentCommandComponentApi {
  default: null | string;
  fill_back: boolean;
  fill_regx: null | string;
  key: string;
  max: null | number;
  min: null | number;
  name: string;
  options: unknown;
  placeholder: null | string;
  required: boolean;
  rows: null | number;
  type: string;
}

export interface IAgentInfo {
  agentName?: string;
  relatedSkills?: IRelatedSkill[];
  resources?: IAgentResourceItem[];
  saasUrl?: string;
  chatGroup?: {
    enabled: boolean;
    staff: string[];
    username: string;
  };
  conversationSettings?: {
    commands?: IAgentCommand[];
    enableChatSession?: boolean;
    openingRemark?: string;
    predefinedQuestions?: string[];
  };
  promptSetting?: {
    content?: IMessage[];
    supportUpload?: ISupportUpload;
  };
}

export interface IAgentInfoApi {
  agent_name: string;
  related_skills?: IRelatedSkillApi[];
  resources?: IAgentResourceItem[];
  saas_url?: string;
  chat_group?: {
    enabled: boolean;
    staff: string[];
    username: string;
  };
  conversation_settings?: {
    commands?: IAgentCommandApi[];
    enable_chat_session?: boolean;
    opening_remark?: string;
    predefined_questions?: string[];
  };
  prompt_setting?: {
    content?: IMessage[];
    support_upload?: ISupportUpload;
  };
}

export interface IAgentResourceItem {
  code: string;
  icon: null | string;
  id: null | number;
  name: string;
  type: string;
}

export interface IRelatedSkill {
  description: string;
  icon: string;
  id: number;
  skill_code: string;
  skill_name: string;
}

export interface IRelatedSkillApi {
  description: string;
  icon: string;
  id: number;
  skill_code: string;
  skill_name: string;
}

/** @deprecated 后端已改为扁平列表 IAgentResourceItem[]，不再使用分组结构 */
export interface IAgentResources {
  command?: IAgentResourceItem[];
  knowledgebase?: IAgentResourceItem[];
  mcp?: IAgentResourceItem[];
  tool?: IAgentResourceItem[];
}

/** 模型能力属性（后端 property 字段） */
export interface ILlmProperty {
  agent_type?: string;
  default?: boolean;
  is_self_host?: boolean;
  max_model_len?: number;
  support_summary?: boolean;
  support_thinking?: boolean;
  support_thinking_quick?: boolean;
  support_tools?: boolean;
  support_vision?: boolean;
  support_window?: boolean;
}

/** 可用模型列表查询参数 */
export interface ILlmListQuery {
  /** 模糊搜索关键词，按 llm_name / description / base_model 匹配 */
  fuzzy?: string;
  /** 模型类型，不传时默认 chat.completion */
  llm_type?: string;
  /** 按模型支持的功能过滤，逗号分隔，如 tool_call,vision */
  supports?: string;
}

/**
 * 可用模型项（对齐 plugin_api/llms/ 与 chat-x IModelOption）
 * 字段以 snake_case 与后端保持一致，便于直接透传给 ModelSelector
 */
export interface ILlmItem {
  /** 基础模型标识，如 hunyuan */
  base_model?: string;
  /** 模型描述 */
  description?: string;
  /** 是否禁用（前端扩展字段） */
  disabled?: boolean;
  /** 模型图标地址 */
  icon?: string;
  /** 模型主键 id */
  id: number;
  /** 模型编码（chat_completion 热切换传此值） */
  llm_code: string;
  /** 模型展示名（ModelSelector v-model 选中值） */
  llm_name: string;
  /** 模型类型，如 chat.completion */
  llm_type: string;
  /** 最大 token 数 */
  max_token_size: number;
  /** 模型能力属性 */
  property: ILlmProperty;
  /** 空间维度鉴权模式 */
  space_auth_mode: string;
  /** 标签名列表 */
  tag_names?: string[];
  /** 用户维度鉴权模式 */
  user_auth_mode: string;
}

/** 后端 llms/ 原始响应项（字段可能缺省） */
export interface ILlmItemApi {
  base_model?: string;
  description?: string;
  icon?: string;
  id?: number;
  llm_code: string;
  llm_name: string;
  llm_type?: string;
  max_token_size?: number;
  property?: ILlmProperty | null;
  space_auth_mode?: string;
  tag_names?: string[];
  user_auth_mode?: string;
}
