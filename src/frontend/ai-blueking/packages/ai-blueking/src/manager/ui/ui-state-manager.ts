/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { ref, reactive } from 'vue';
import type { Ref } from 'vue';

/**
 * UI 状态管理器
 *
 * 职责：
 * - 管理小鲸组件特有的 UI 状态
 * - 消息选择、编辑模式等
 * - 不依赖 AG-UI SDK
 */
export class UIStateManager {
  // 消息选择状态
  private _selectedMessageIds: Ref<Set<string>>;
  private _isSelectionMode: Ref<boolean>;

  // 编辑状态
  private _editingSessionCode: Ref<string | null>;

  // 加载状态映射
  private _loadingStates: Record<string, boolean>;

  constructor() {
    // 初始化状态
    this._selectedMessageIds = ref(new Set<string>());
    this._isSelectionMode = ref(false);
    this._editingSessionCode = ref(null);
    this._loadingStates = reactive({});
  }

  /**
   * 是否为选择模式
   */
  get isSelectionMode() {
    return this._isSelectionMode;
  }

  /**
   * 正在编辑的会话编码
   */
  get editingSessionCode() {
    return this._editingSessionCode;
  }

  /**
   * 切换选择模式
   */
  toggleSelectionMode(): void {
    this._isSelectionMode.value = !this._isSelectionMode.value;

    // 退出选择模式时清空选择
    if (!this._isSelectionMode.value) {
      this.clearSelection();
    }
  }

  /**
   * 启用选择模式
   */
  enableSelectionMode(): void {
    this._isSelectionMode.value = true;
  }

  /**
   * 禁用选择模式
   */
  disableSelectionMode(): void {
    this._isSelectionMode.value = false;
    this.clearSelection();
  }

  /**
   * 选中/取消选中消息
   * @param messageId 消息 ID
   */
  toggleMessageSelection(messageId: string): void {
    if (this._selectedMessageIds.value.has(messageId)) {
      this._selectedMessageIds.value.delete(messageId);
    } else {
      this._selectedMessageIds.value.add(messageId);
    }

    // 触发响应式更新
    this._selectedMessageIds.value = new Set(this._selectedMessageIds.value);
  }

  /**
   * 选中消息
   * @param messageId 消息 ID
   */
  selectMessage(messageId: string): void {
    this._selectedMessageIds.value.add(messageId);
    this._selectedMessageIds.value = new Set(this._selectedMessageIds.value);
  }

  /**
   * 取消选中消息
   * @param messageId 消息 ID
   */
  deselectMessage(messageId: string): void {
    this._selectedMessageIds.value.delete(messageId);
    this._selectedMessageIds.value = new Set(this._selectedMessageIds.value);
  }

  /**
   * 检查消息是否被选中
   * @param messageId 消息 ID
   */
  isMessageSelected(messageId: string): boolean {
    return this._selectedMessageIds.value.has(messageId);
  }

  /**
   * 清空选择
   */
  clearSelection(): void {
    this._selectedMessageIds.value.clear();
    this._selectedMessageIds.value = new Set(this._selectedMessageIds.value);
  }

  /**
   * 全选消息
   * @param messageIds 所有消息 ID
   */
  selectAllMessages(messageIds: string[]): void {
    this._selectedMessageIds.value = new Set(messageIds);
  }

  /**
   * 获取选中的消息 ID 列表
   */
  get selectedMessages(): string[] {
    return Array.from(this._selectedMessageIds.value);
  }

  /**
   * 获取选中消息数量
   */
  get selectedCount(): number {
    return this._selectedMessageIds.value.size;
  }

  /**
   * 检查是否有选中的消息
   */
  get hasSelection(): boolean {
    return this._selectedMessageIds.value.size > 0;
  }

  /**
   * 开始编辑会话
   * @param sessionCode 会话编码
   */
  startEditingSession(sessionCode: string): void {
    this._editingSessionCode.value = sessionCode;
  }

  /**
   * 停止编辑会话
   */
  stopEditingSession(): void {
    this._editingSessionCode.value = null;
  }

  /**
   * 检查是否正在编辑会话
   * @param sessionCode 会话编码（可选）
   */
  isEditingSession(sessionCode?: string): boolean {
    if (sessionCode) {
      return this._editingSessionCode.value === sessionCode;
    }
    return this._editingSessionCode.value !== null;
  }

  /**
   * 设置加载状态
   * @param key 状态键
   * @param loading 加载状态
   */
  setLoading(key: string, loading: boolean): void {
    this._loadingStates[key] = loading;
  }

  /**
   * 获取加载状态
   * @param key 状态键
   */
  isLoading(key: string): boolean {
    return this._loadingStates[key] ?? false;
  }

  /**
   * 清空所有加载状态
   */
  clearLoadingStates(): void {
    Object.keys(this._loadingStates).forEach(key => {
      this._loadingStates[key] = false;
    });
  }

  /**
   * 重置所有状态
   */
  reset(): void {
    this.clearSelection();
    this.disableSelectionMode();
    this.stopEditingSession();
    this.clearLoadingStates();
  }
}
