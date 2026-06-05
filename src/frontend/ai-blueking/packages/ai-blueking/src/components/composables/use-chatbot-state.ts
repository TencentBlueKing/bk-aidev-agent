/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed } from 'vue';
import type { ComputedRef, Ref } from 'vue';

import { MessageStatus, MessageToolsStatus } from '@blueking/chat-x';

import type { ChatBusinessManager } from '../../manager/business/chat-business-manager';
import type { SessionBusinessManager } from '../../manager/business/session-business-manager';
import type { ShortcutManager } from '../../manager/business/shortcut-manager';
import type { IChatHelper } from '../../types';
import type { ChatBotProps } from '../types';
import type { ISupportUpload } from '@blueking/chat-helper';
import type { IAiSlashMenuItem, ISkillListItem, Message, Shortcut } from '@blueking/chat-x';

export interface UseChatbotStateParams {
  chatBusinessManager: Ref<ChatBusinessManager | null>;
  chatHelper: Ref<IChatHelper | null>;
  isInitialized: Ref<boolean>;
  isStandaloneMode: Ref<boolean>;
  props: ChatBotProps;
  selectedShortcut: Ref<null | (Shortcut & { supportUpload?: ISupportUpload })>;
  sessionBusinessManager: Ref<null | SessionBusinessManager>;
  shortcutManager: Ref<null | ShortcutManager>;
}

export interface UseChatbotStateReturn {
  chatbotStyle: ComputedRef<Record<string, string | undefined>>;
  currentSession: ComputedRef<any>;
  effectivePrompts: ComputedRef<string[]>;
  effectiveResources: ComputedRef<IAiSlashMenuItem[]>;
  effectiveSkills: ComputedRef<ISkillListItem[]>;
  effectiveSupportUpload: ComputedRef<boolean>;
  filteredShortcuts: ComputedRef<Shortcut[]>;
  isGenerating: ComputedRef<boolean>;
  isMessagesLoading: ComputedRef<boolean>;
  isWelcomeState: ComputedRef<boolean>;
  messages: ComputedRef<Message[]>;
  messageStatus: ComputedRef<MessageStatus>;
  messageToolsStatus: ComputedRef<MessageToolsStatus | undefined>;
  openingRemark: ComputedRef<string>;
  // stopLoading: ComputedRef<boolean>;
}

export function useChatbotState(params: UseChatbotStateParams): UseChatbotStateReturn {
  const {
    props,
    chatHelper,
    chatBusinessManager,
    sessionBusinessManager,
    shortcutManager,
    isStandaloneMode,
    isInitialized,
    selectedShortcut,
  } = params;

  const messageStatus = computed(() => {
    if (chatBusinessManager.value?.isStopLoading.value) return MessageStatus.StopLoading;
    const agent = (props.chatHelper || chatHelper.value)?.agent;
    return agent?.isChatting?.value ? MessageStatus.Streaming : MessageStatus.Complete;
  });

  const messageToolsStatus = computed(() => {
    return messageStatus.value === MessageStatus.Streaming ? MessageToolsStatus.Disabled : undefined;
  });

  // TODO: IMessage (chat-helper) 和 Message (chat-x) 类型需要统一
  const messages = computed(() => (chatBusinessManager.value?.messages.value ?? []) as Message[]);
  const isMessagesLoading = computed(() => chatBusinessManager.value?.isMessagesLoading.value ?? false);
  const isGenerating = computed(() => chatBusinessManager.value?.isGenerating.value ?? false);
  // const stopLoading = computed(() => chatBusinessManager.value?.isStopLoading.value ?? false);
  const currentSession = computed(() => sessionBusinessManager.value?.currentSession.value ?? null);

  /**
   * 是否为欢迎状态（新会话，无消息）
   * 独立模式下，初始化完成前不进入欢迎状态，避免页面闪动
   */
  const isWelcomeState = computed(() => {
    if (isStandaloneMode.value && !isInitialized.value) return false;
    return !isMessagesLoading.value && messages.value.length === 0;
  });

  /**
   * 获取欢迎语（markdown 格式）
   */
  const openingRemark = computed(() => {
    return chatHelper.value?.agent.info.value?.conversationSettings?.openingRemark || '';
  });

  /**
   * 资源列表（输入 @ 触发）
   * 优先级：props 传入 > info 接口返回 > 空数组
   */
  const effectiveResources = computed(() => {
    if (props.resources?.length) return props.resources;
    return (chatHelper.value?.agent.info.value?.resources ?? []) as IAiSlashMenuItem[];
  });

  /**
   * 预设提示词列表（输入 \ 触发）
   * 优先级：props 传入 > info 接口返回 > 空数组
   */
  const effectivePrompts = computed(() => {
    if (props.prompts?.length) return props.prompts;
    return chatHelper.value?.agent.info.value?.conversationSettings?.predefinedQuestions ?? [];
  });

  /**
   * 技能列表（输入 / 触发）
   * 优先级：props 传入 > info 接口返回 > 空数组
   */
  const effectiveSkills = computed<ISkillListItem[]>(() => {
    if (props.skills?.length) return props.skills;
    return (chatHelper.value?.agent.info.value?.relatedSkills ?? []).map(skill => ({
      skill_name: skill.skill_name,
      skill_code: skill.skill_code,
      description: skill.description,
      icon: skill.icon,
    }));
  });

  /**
   * 是否支持上传文件（vision 模式）
   * 选中 command 时使用 command 级别的 supportUpload，否则使用 agent 级别的
   */
  const effectiveSupportUpload = computed(() => {
    if (selectedShortcut.value?.supportUpload) {
      return selectedShortcut.value.supportUpload.vision === true;
    }
    return chatHelper.value?.agent.info.value?.promptSetting?.supportUpload?.vision === true;
  });

  const chatbotStyle = computed(() => ({
    height: typeof props.height === 'number' ? `${props.height}px` : props.height,
    maxWidth: typeof props.maxWidth === 'number' ? `${props.maxWidth}px` : props.maxWidth,
  }));

  const filteredShortcuts = computed(() => (shortcutManager.value?.shortcuts.value ?? []) as Shortcut[]);

  return {
    messageStatus,
    messageToolsStatus,
    messages,
    isMessagesLoading,
    isGenerating,
    // stopLoading,
    currentSession,
    isWelcomeState,
    openingRemark,
    effectiveResources,
    effectivePrompts,
    effectiveSkills,
    effectiveSupportUpload,
    chatbotStyle,
    filteredShortcuts,
  };
}
