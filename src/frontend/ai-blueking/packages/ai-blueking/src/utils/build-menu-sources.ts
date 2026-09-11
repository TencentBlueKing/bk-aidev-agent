/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { IHostResourceItem, IHostSkillItem } from '../types';
import type { IInputMenuItem } from '@blueking/chat-x';

const MENU_TYPE_WHITELIST = ['skill', 'mcp', 'tool', 'knowledgebase', 'doc'] as const;

type MenuResourceType = (typeof MENU_TYPE_WHITELIST)[number];

const isMenuResourceType = (type: string): type is MenuResourceType =>
  (MENU_TYPE_WHITELIST as readonly string[]).includes(type);

/**
 * 各类型的标识选择即协议：
 * - skill / tool / mcp：code（skill 为 skill_code）
 * - knowledgebase / doc：数值 id 的字符串，id 为 null 时回退 code
 */
const resolveResourceId = (resource: IHostResourceItem): string => {
  if (resource.type === 'knowledgebase' || resource.type === 'doc') {
    return resource.id !== null && resource.id !== undefined ? String(resource.id) : (resource.code ?? '');
  }
  return resource.code ?? (resource.id !== null && resource.id !== undefined ? String(resource.id) : '');
};

const mapSkill = (skill: IHostSkillItem): IInputMenuItem | undefined => {
  const id = skill.skill_code ?? '';
  if (!id) return undefined;
  return {
    type: 'skill',
    id,
    name: skill.skill_name,
    description: skill.description,
    icon: skill.icon,
  };
};

const mapResource = (resource: IHostResourceItem): IInputMenuItem | undefined => {
  if (!isMenuResourceType(resource.type) || resource.type === 'skill') return undefined;
  const id = resolveResourceId(resource);
  if (!id) return undefined;
  return {
    type: resource.type,
    id,
    name: resource.name,
    icon: resource.icon as IInputMenuItem['icon'],
  };
};

const mapPrompt = (text: string, index: number): IInputMenuItem => ({
  type: 'prompt',
  id: `prompt-${index}`,
  name: text,
  content: text,
});

export interface BuildMenuSourcesInput {
  prompts?: string[];
  resources?: IHostResourceItem[];
  skills?: IHostSkillItem[];
}

export const buildMenuSources = ({
  skills = [],
  resources = [],
  prompts = [],
}: BuildMenuSourcesInput = {}): IInputMenuItem[] => {
  const skillItems = skills.map(mapSkill).filter((item): item is IInputMenuItem => !!item);
  const resourceItems = resources.map(mapResource).filter((item): item is IInputMenuItem => !!item);
  const promptItems = prompts.map(mapPrompt);
  return [...skillItems, ...resourceItems, ...promptItems];
};
