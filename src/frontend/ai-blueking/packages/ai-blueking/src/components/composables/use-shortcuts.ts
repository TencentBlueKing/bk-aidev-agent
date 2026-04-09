/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, watch } from 'vue';
import type { ComputedRef, Ref } from 'vue';

import type { ShortcutManager } from '../../manager/business/shortcut-manager';
import type { IShortcut } from '../../manager/business/types';
import type { IChatHelper } from '../../types';
import type { ChatBotProps } from '../types';
import type { ChatBotEmitFn } from './use-chatbot-init';
import type { ISupportUpload, IUserMessage } from '@blueking/chat-helper';
import type { Shortcut, ShortcutComponent } from '@blueking/chat-x';

export type DoSendMessageFn = (
  message: IUserMessage['content'],
  options?: { property?: Record<string, unknown> },
) => Promise<void>;

export interface UseShortcutsParams {
  chatHelper: Ref<IChatHelper | null>;
  doSendMessage: DoSendMessageFn;
  emit: ChatBotEmitFn;
  props: ChatBotProps;
  selectedShortcut: Ref<null | (Shortcut & { supportUpload?: ISupportUpload })>;
  shortcutManager: Ref<null | ShortcutManager>;
}

export interface UseShortcutsReturn {
  effectiveShortcuts: ComputedRef<IShortcut[]>;
  buildShortcutProperty: (shortcut: Shortcut, formModel: Record<string, unknown>) => Record<string, unknown>;
  getShortcutFromMessage: (message: any) => IShortcut | null;
  handleCloseShortcut: () => void;
  handleSelectShortcut: (shortcut: Shortcut, text?: string) => void;
  handleShortcutSubmit: (formModel: Record<string, unknown>) => Promise<void>;
  selectShortcutWithText: (shortcut: IShortcut | Shortcut, text?: string) => void;
  /**
   * 直接发送快捷指令（跳过表单，等价于旧版 handleShortcutClick(_, true)）
   * 从 shortcut.components 的 default 值构建 formModel，直接发送消息
   * @param shortcut 快捷指令对象
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  sendShortcutDirectly: (shortcut: IShortcut | Shortcut, selectedText?: string) => Promise<void>;
}

export function useShortcuts(params: UseShortcutsParams): UseShortcutsReturn {
  const { props, emit, shortcutManager, doSendMessage, selectedShortcut } = params;

  const effectiveShortcuts = computed((): IShortcut[] => shortcutManager.value?.effectiveShortcuts.value ?? []);

  /**
   * 选择快捷指令并填充选中文本
   */
  const selectShortcutWithText = (shortcut: IShortcut | Shortcut, text?: string) => {
    const shortcutData = shortcut as IShortcut & Shortcut;

    let fillBackKey: string | undefined;

    if (shortcutData.enable_fill_back && shortcutData.fill_back_component_key) {
      fillBackKey = shortcutData.fill_back_component_key;
    } else {
      const fillBackComponent = shortcutData.components?.find(c => c.fillBack);
      fillBackKey = fillBackComponent?.key;
    }

    if (fillBackKey && text) {
      const newComponents = shortcutData.components?.map(component => {
        if (component.key === fillBackKey) {
          return { ...component, default: text };
        }
        return { ...component, default: component.default ?? undefined };
      }) as ShortcutComponent[];

      selectedShortcut.value = {
        ...shortcutData,
        components: newComponents,
        formModel: {
          ...shortcutData.formModel,
          [fillBackKey]: text,
        },
      };
    } else {
      selectedShortcut.value = {
        ...shortcutData,
        formModel: {
          ...shortcutData.formModel,
        },
      };
    }
  };

  /**
   * 根据快捷指令和表单数据构建 property
   */
  const buildShortcutProperty = (shortcut: Shortcut, formModel: Record<string, unknown>) => {
    const components = shortcut.components || [];

    return {
      extra: {
        cite: {
          type: 'structured',
          title: shortcut.alias || shortcut.name,
          data: components.map(component => ({
            key: component.name || component.key,
            value: String(formModel[component.key] ?? ''),
          })),
        },
        command: shortcut.id,
        context: components.map(component => ({
          [component.key]: formModel[component.key],
          context_type: component.type,
          __label: component.name || component.key,
          __key: component.key,
          __value: formModel[component.key],
        })),
      },
    };
  };

  /**
   * 从消息中获取快捷指令信息
   */
  const getShortcutFromMessage = (message: any): IShortcut | null => {
    const extra = (message as { property?: { extra?: { command?: string; shortcut?: IShortcut } } }).property?.extra;

    if (extra?.shortcut) {
      return extra.shortcut as IShortcut;
    }

    if (extra?.command) {
      return effectiveShortcuts.value.find((s: IShortcut) => s.id === extra.command) ?? null;
    }

    return null;
  };

  const handleSelectShortcut = (shortcut: Shortcut, text?: string) => {
    selectShortcutWithText(shortcut, text);
    emit('shortcut-click', {
      shortcut: shortcut as unknown as IShortcut,
      source: 'main',
    });
  };

  const handleCloseShortcut = () => {
    selectedShortcut.value = null;
  };

  /**
   * 处理快捷方式提交（乐观更新：先关闭面板，再发送消息）
   */
  const handleShortcutSubmit = async (formModel: Record<string, unknown>) => {
    if (!selectedShortcut.value) {
      console.error('[ChatBot] No selected shortcut');
      return;
    }

    const property = buildShortcutProperty(selectedShortcut.value, formModel);
    const message = selectedShortcut.value.name;

    // 乐观更新：保存当前状态用于失败回滚，立即关闭面板
    const previousShortcut = selectedShortcut.value;
    handleCloseShortcut();

    try {
      await doSendMessage(message, { property });
    } catch (error) {
      // 发送失败：恢复快捷指令面板状态
      selectedShortcut.value = previousShortcut;
      console.error('[ChatBot] Failed to submit shortcut:', error);
      emit('error', error as Error);
    }
  };

  /**
   * 直接发送快捷指令（跳过表单，等价于旧版 handleShortcutClick(_, true)）
   * 从 shortcut.components 的 default 值构建 formModel，直接发送消息
   */
  const sendShortcutDirectly = async (shortcut: IShortcut | Shortcut, selectedText?: string) => {
    const shortcutData = shortcut as IShortcut & Shortcut;

    // 1. 从 components 的 default 值构建 formModel
    const formModel: Record<string, unknown> = { ...shortcutData.formModel };
    const components = shortcutData.components || [];

    for (const comp of components) {
      if (!(comp.key in formModel)) {
        formModel[comp.key] = comp.default ?? '';
      }
    }

    // 2. 如果有 selectedText，填充到 fillBack 字段
    let fillBackKey: string | undefined;
    if (shortcutData.enable_fill_back && shortcutData.fill_back_component_key) {
      fillBackKey = shortcutData.fill_back_component_key;
    } else {
      const fillBackComponent = components.find(c => c.fillBack);
      fillBackKey = fillBackComponent?.key;
    }

    if (fillBackKey && selectedText) {
      formModel[fillBackKey] = selectedText;
    }

    // 3. 构建 property 并发送
    const property = buildShortcutProperty(shortcutData, formModel);
    const message = shortcutData.name;

    try {
      await doSendMessage(message, { property });
    } catch (error) {
      console.error('[ChatBot] Failed to send shortcut directly:', error);
      emit('error', error as Error);
    }
  };

  // 监听 props.shortcuts 变化，更新 ShortcutManager
  watch(
    () => props.shortcuts,
    newShortcuts => {
      shortcutManager.value?.setShortcuts(newShortcuts || []);
    },
    { immediate: true },
  );

  // 监听 agent info 变化，更新 ShortcutManager 的 agentShortcuts
  watch(
    () => params.chatHelper.value?.agent.info.value?.conversationSettings?.commands,
    commands => {
      if (commands) {
        shortcutManager.value?.setAgentShortcuts(commands as IShortcut[]);
      }
    },
    { immediate: true },
  );

  return {
    effectiveShortcuts,
    selectShortcutWithText,
    buildShortcutProperty,
    getShortcutFromMessage,
    handleSelectShortcut,
    handleCloseShortcut,
    handleShortcutSubmit,
    sendShortcutDirectly,
  };
}
