/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { Ref } from 'vue';

import { useHistoryPanel } from '../../../composables/use-history-panel';
import type { SessionBusinessManager } from '../../../manager/business/session-business-manager';

import HistoryDropdown from './index.vue';

export interface UseHistoryDropdownOptions {
  triggerRef: Ref<HTMLElement | null>;
  sessionBusinessManager?: SessionBusinessManager;
  onSessionSwitch?: (code: string) => void;
  onSessionDelete?: (code: string) => void;
  onSessionRename?: (code: string, newName: string) => void;
}

/**
 * 历史会话下拉面板 Composable
 *
 * 基于 useHistoryPanel 封装，专门用于历史会话下拉功能
 *
 * @param options 配置选项
 * @returns 历史面板控制方法
 */
export function useHistoryDropdown(options: UseHistoryDropdownOptions) {
  if (!options.sessionBusinessManager) {
    // 如果没有 sessionBusinessManager，返回空方法
    return {
      handleTriggerClick: () => {},
      show: () => {},
      hide: () => {},
      toggle: () => {},
      destroy: () => {},
      isVisible: () => false,
    };
  }

  return useHistoryPanel({
    triggerRef: options.triggerRef,
    panelComponent: HistoryDropdown,
    panelProps: {
      sessionBusinessManager: options.sessionBusinessManager,
      onSessionSwitch: options.onSessionSwitch,
      onSessionDelete: options.onSessionDelete,
      onSessionRename: options.onSessionRename,
    },
    tippyOptions: {
      placement: 'bottom-end',
      offset: [0, 8],
      appendTo: () =>
        (document.querySelector('.ai-blueking-panel') as HTMLElement) || document.body,
    },
  });
}
