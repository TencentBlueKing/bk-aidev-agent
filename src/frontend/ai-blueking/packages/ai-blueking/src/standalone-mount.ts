/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { ChatBot } from './components';
import type { ChatBotExpose, ChatBotProps } from './components/types';
import type { AIBluekingExpose, AIBluekingProps } from './types';
import AIBlueking from './ai-blueking.vue';

export type {
  StandaloneEventHandlers,
  StandaloneMountHandle,
  StandaloneMountOptions,
} from './standalone-mount-core';

export {
  buildStandaloneListeners,
  mountStandaloneComponent,
  resolveMountContainer,
} from './standalone-mount-core';

import {
  mountStandaloneComponent,
  type StandaloneMountHandle,
  type StandaloneMountOptions,
} from './standalone-mount-core';

/**
 * 在非 Vue 宿主挂载完整小鲸（AIBlueking）
 */
export function mountAIBlueking(
  container: string | Element,
  options?: StandaloneMountOptions<AIBluekingProps>,
): StandaloneMountHandle<AIBluekingExpose, AIBluekingProps> {
  return mountStandaloneComponent<AIBluekingProps, AIBluekingExpose>(container, AIBlueking, options);
}

/**
 * 在非 Vue 宿主挂载 ChatBot
 */
export function mountChatBot(
  container: string | Element,
  options?: StandaloneMountOptions<ChatBotProps>,
): StandaloneMountHandle<ChatBotExpose, ChatBotProps> {
  return mountStandaloneComponent<ChatBotProps, ChatBotExpose>(container, ChatBot, options);
}
