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
import type { IAgentInfo, IAgentInfoApi, ILlmItem, ILlmItemApi } from '../../agent/type';

/**
 * 将 API 返回的 agent 信息数据转换为前端使用的 agent 信息数据
 * @param data API 返回的 agent 信息数据
 * @returns 前端使用的 agent 信息数据
 */
export const transferAgentInfoApi2AgentInfo = (data: IAgentInfoApi): IAgentInfo => ({
  conversationSettings: {
    openingRemark: data?.conversation_settings?.opening_remark,
    predefinedQuestions: data?.conversation_settings?.predefined_questions,
    commands: data?.conversation_settings?.commands?.map(command => ({
      id: command.id,
      name: command.name,
      alias: command.alias,
      icon: command.icon,
      components: command.components.map(component => ({
        type: component.type,
        name: component.name,
        key: component.key,
        placeholder: component.placeholder,
        default: component.default,
        required: component.required,
        fillBack: component.fill_back,
        fillRegx: component.fill_regx,
        rows: component.rows,
        min: component.min,
        max: component.max,
        options: component.options,
      })),
      content: command.content,
      agentId: command.agent_id,
      status: command.status,
      supportUpload: command.support_upload,
    })),
    enableChatSession: data?.conversation_settings?.enable_chat_session,
  },
  promptSetting: data?.prompt_setting
    ? {
        content: data.prompt_setting.content,
        supportUpload: data.prompt_setting.support_upload,
      }
    : undefined,
  agentName: data?.agent_name,
  relatedSkills: data?.related_skills?.map(skill => ({
    id: skill.id,
    skill_name: skill.skill_name,
    skill_code: skill.skill_code,
    description: skill.description,
    icon: skill.icon,
  })),
  chatGroup: data?.chat_group
    ? {
        enabled: data.chat_group.enabled,
        staff: data.chat_group.staff,
        username: data.chat_group.username,
      }
    : undefined,
  saasUrl: data?.saas_url,
  resources: data?.resources,
});

/**
 * 将 llms/ 接口单项规范化为前端 ILlmItem（补齐缺省字段，避免 UI 崩溃）
 */
export const transferLlmApi2LlmItem = (data: ILlmItemApi): ILlmItem => ({
  id: data.id ?? 0,
  llm_code: data.llm_code,
  llm_name: data.llm_name,
  llm_type: data.llm_type ?? 'chat.completion',
  icon: data.icon ?? '',
  description: data.description ?? '',
  base_model: data.base_model,
  max_token_size: data.max_token_size ?? 0,
  property: data.property ?? {},
  space_auth_mode: data.space_auth_mode ?? '',
  user_auth_mode: data.user_auth_mode ?? '',
  tag_names: data.tag_names,
});

/**
 * 将 llms/ 列表响应规范化为 ILlmItem[]
 */
export const transferLlmListApi2LlmItems = (data: ILlmItemApi[] | null | undefined): ILlmItem[] => {
  if (!Array.isArray(data)) {
    return [];
  }
  return data.map(transferLlmApi2LlmItem);
};
