/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { RenderMode } from '@blueking/chat-x';

import { t } from '../lang';

import type { DropdownMenuConfig, IRequestOptions, IShortcut } from '../types';

/**
 * AIBlueking 组件 Props 默认值
 * 使用函数形式返回引用类型，避免默认值共享问题
 */
export const defaultProps = {
  // 基础配置
  url: '',
  title: '',
  extCls: '',

  // 功能开关
  hideNimbus: false,
  hideHeader: false,
  enablePopup: true,
  draggable: true,
  enableChatSession: true,
  enableModelSelect: true,

  // 渲染模式
  renderMode: RenderMode.Chat as RenderMode,

  // 容器配置
  defaultWidth: 400,
  defaultHeight: undefined,
  defaultTop: 0,
  defaultLeft: undefined,
  maxWidth: 1000 as number | string,
  miniPadding: 0,

  // Nimbus 配置
  nimbusSize: 'normal' as const,
  defaultMinimize: false,

  // Popup 配置
  shortcuts: (): IShortcut[] => [],
  shortcutLimit: 3,
  shortcutFilter: undefined,
  hideDefaultTrigger: false,

  // 其他配置
  requestOptions: (): IRequestOptions => ({}),
  teleportTo: 'body',
  placeholder: undefined as string | undefined,
  helloText: t('你好，我是小鲸'),
  useAgentName: false,
  disabledInput: false,
  showHistoryIcon: true,
  showNewChatIcon: true,
  showCompressionIcon: true,
  showMoreIcon: true,
  initialSessionCode: '',
  autoSwitchToInitialSession: false,
  alwaysCreateNewSession: false,
  loadRecentSessionOnMount: true,
  prompts: (): string[] => [],
  dropdownMenuConfig: (): DropdownMenuConfig => ({
    showRename: true,
    showAutoGenerate: true,
    showShare: true,
  }),
  defaultChatInputPosition: undefined as 'bottom' | undefined,
  errorToast: true,
  ignoreErrors: (): Array<RegExp | string> => [],
};
