/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, ref } from 'vue';
import type { ComputedRef, Ref } from 'vue';

import type { IEventEmitter, IShortcut, ShortcutFilterFn } from './types';

/**
 * 快捷方式管理器
 *
 * 职责：
 * - 管理快捷方式列表（开发者传入 + Agent 接口返回）
 * - 统一管理快捷指令优先级
 * - 处理快捷方式点击逻辑
 * - 处理快捷方式过滤
 */
export class ShortcutManager {
  /** Agent info 接口返回的快捷方式 */
  private _agentShortcuts: Ref<IShortcut[]>;
  /** 有效的快捷方式（按优先级计算） */
  private _effectiveShortcuts: ComputedRef<IShortcut[]>;
  /** 开发者通过 props 传入的快捷方式 */
  private _propsShortcuts: Ref<IShortcut[]>;
  private eventEmitter: IEventEmitter | null;

  /**
   * 发射事件（内部方法）
   */
  private emit(event: string, data: unknown): void {
    this.eventEmitter?.emit(event, data);
  }

  constructor(eventEmitter: IEventEmitter | null = null, propsShortcuts: IShortcut[] = []) {
    this._propsShortcuts = ref(propsShortcuts);
    this._agentShortcuts = ref([]);
    this.eventEmitter = eventEmitter;

    // 计算有效的快捷方式（优先级逻辑）
    this._effectiveShortcuts = computed(() => {
      // 优先级1：开发者显式传入的 shortcuts
      if (this._propsShortcuts.value.length > 0) {
        return this._propsShortcuts.value;
      }
      // 优先级2：Agent info 接口返回的 commands
      if (this._agentShortcuts.value.length > 0) {
        return this._agentShortcuts.value;
      }
      // 优先级3：空数组
      return [];
    });
  }

  /**
   * 获取有效快捷方式数量
   */
  get count(): number {
    return this._effectiveShortcuts.value.length;
  }

  /**
   * 获取有效的快捷方式列表（按优先级计算）
   * 优先级：
   * 1. 开发者通过 props 传入的 shortcuts（如果非空）
   * 2. Agent info 接口返回的 commands（如果存在）
   * 3. 空数组
   */
  get effectiveShortcuts(): ComputedRef<IShortcut[]> {
    return this._effectiveShortcuts;
  }

  /**
   * 检查是否有有效快捷方式
   */
  get hasShortcuts(): boolean {
    return this._effectiveShortcuts.value.length > 0;
  }

  /**
   * 获取快捷方式列表（兼容旧 API，等同于 effectiveShortcuts）
   * @deprecated 建议使用 effectiveShortcuts
   */
  get shortcuts(): ComputedRef<IShortcut[]> {
    return this._effectiveShortcuts;
  }

  /**
   * 添加快捷方式（添加到 props 快捷方式列表）
   * @param shortcut 快捷方式
   */
  addShortcut(shortcut: IShortcut): void {
    this._propsShortcuts.value.push(shortcut);
  }

  /**
   * 清空所有快捷方式
   */
  clear(): void {
    this._propsShortcuts.value = [];
    this._agentShortcuts.value = [];
  }

  /**
   * 根据文本长度限制过滤快捷方式
   * @param selectedText 选中的文本
   * @param maxLength 最大文本长度
   * @returns 过滤后的快捷方式列表
   */
  filterByTextLength(selectedText: string, maxLength: number): IShortcut[] {
    if (!selectedText || selectedText.length > maxLength) {
      return [];
    }
    return this._effectiveShortcuts.value;
  }

  /**
   * 过滤快捷方式
   * @param selectedText 选中的文本
   * @param filter 过滤函数（可选）
   * @returns 过滤后的快捷方式列表
   */
  filterShortcuts(selectedText: string, filter?: ShortcutFilterFn): IShortcut[] {
    // 如果没有提供过滤函数，返回所有有效快捷方式
    if (!filter) {
      return this._effectiveShortcuts.value;
    }

    // 使用提供的过滤函数
    return this._effectiveShortcuts.value.filter(s => filter(s, selectedText));
  }

  /**
   * 根据 ID 获取快捷方式（从有效快捷方式列表中查找）
   * @param shortcutId 快捷方式 ID
   */
  getShortcutById(shortcutId: string): IShortcut | undefined {
    return this._effectiveShortcuts.value.find(s => s.id === shortcutId);
  }

  /**
   * 处理快捷方式点击
   * @param shortcut 快捷方式
   * @param selectedText 选中的文本（可选）
   * @param source 来源（popup 或 main）
   */
  handleShortcutClick(shortcut: IShortcut, selectedText?: string, source: 'main' | 'popup' = 'main'): void {
    // 触发事件
    this.emit('shortcut-click', {
      shortcut,
      selectedText,
      source,
    });
  }

  /**
   * 根据数量限制获取快捷方式
   * @param limit 显示数量限制
   * @returns 限制后的快捷方式列表
   */
  limitShortcuts(limit: number): IShortcut[] {
    return this._effectiveShortcuts.value.slice(0, limit);
  }

  /**
   * 移除快捷方式（从 props 快捷方式列表移除）
   * @param shortcutId 快捷方式 ID
   */
  removeShortcut(shortcutId: string): void {
    this._propsShortcuts.value = this._propsShortcuts.value.filter(s => s.id !== shortcutId);
  }

  /**
   * 设置 Agent info 接口返回的快捷方式
   * @param shortcuts Agent 返回的快捷方式数组
   */
  setAgentShortcuts(shortcuts: IShortcut[]): void {
    this._agentShortcuts.value = shortcuts;
  }

  /**
   * 设置开发者传入的快捷方式列表
   * @param shortcuts 快捷方式数组
   */
  setShortcuts(shortcuts: IShortcut[]): void {
    this._propsShortcuts.value = shortcuts;
  }
}
