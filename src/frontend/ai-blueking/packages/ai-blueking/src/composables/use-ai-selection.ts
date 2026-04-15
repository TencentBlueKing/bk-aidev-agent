/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, ref } from 'vue';
import type { Ref } from 'vue';

import type ChatBot from '../components/chat-bot.vue';
import type { ShortcutManager } from '../manager/business/shortcut-manager';
import type { AIBluekingProps, IShortcut } from '../types';
import type { ForwardToManagerFn } from './use-ai-blueking-init';
import type { Shortcut } from '@blueking/chat-x';

export interface UseAiSelectionParams {
  chatBotRef: Ref<InstanceType<typeof ChatBot> | undefined>;
  forwardToManager: ForwardToManagerFn;
  props: Pick<AIBluekingProps, 'shortcutFilter'>;
  shortcutManager: ShortcutManager;
  show: (sessionCode?: string) => Promise<void>;
}

export function useAiSelection(params: UseAiSelectionParams) {
  const { shortcutManager, chatBotRef, forwardToManager, show, props } = params;

  const aiSelectionVisible = ref(false);
  const selectedText = ref('');

  /**
   * 划词弹窗显示的快捷指令（支持过滤）
   */
  const filteredPopupShortcuts = computed(() => {
    const shortcuts = shortcutManager.effectiveShortcuts.value;
    if (typeof props.shortcutFilter === 'function' && selectedText.value) {
      return shortcuts.filter(item => props.shortcutFilter?.(item, selectedText.value)) as Shortcut[];
    }
    return shortcuts as Shortcut[];
  });

  const handleSelectionChange = (text: string) => {
    selectedText.value = text;
  };

  /**
   * 处理划词快捷指令点击
   * 打开面板 → 选择快捷指令 → 设置引用文本
   */
  const handleAiSelectionShortcut = async (shortcut: Shortcut, text: string) => {
    aiSelectionVisible.value = false;
    await show();

    if (chatBotRef.value) {
      if (shortcut.components?.length) {
        chatBotRef.value.selectShortcut(shortcut as unknown as IShortcut, text);
      } else {
        chatBotRef.value.selectShortcut(shortcut as unknown as IShortcut);
        chatBotRef.value.setCiteText(text);
        chatBotRef.value.focusInput();
      }
    }

    forwardToManager('shortcut-click', {
      shortcut: shortcut as unknown as IShortcut,
      source: 'popup',
    });
  };

  return {
    aiSelectionVisible,
    selectedText,
    filteredPopupShortcuts,
    handleSelectionChange,
    handleAiSelectionShortcut,
  };
}
