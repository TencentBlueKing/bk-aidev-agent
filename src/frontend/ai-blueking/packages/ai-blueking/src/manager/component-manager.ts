/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { type Ref, computed, ref } from 'vue';

import type { EventCallback, InternalEvent, InternalEventData } from './event-types';
import type {
  ComponentManagerConfig,
  ComponentManagerState,
  ContainerController,
  IShortcut,
  NimbusController,
  PanelController,
  PositionAndSize,
} from './types';

/**
 * 组件管理器
 *
 * 负责协调各子组件之间的通信和状态管理，遵循单一职责原则。
 *
 * 职责：
 * 1. UI 状态管理 - 面板、Nimbus、拖拽、压缩等状态
 * 2. 统一事件系统 - 提供 on/off/emit/once 方法，管理所有内部事件
 * 3. 组件协调 - 协调各子组件之间的交互
 *
 * 事件系统：
 * - 使用内置的 listeners Map 管理所有事件
 * - 支持一次性事件监听 (once)
 * - 通过 useEventBridge 自动桥接到 Vue emit
 */
export class ComponentManager {
  // ==================== UI 状态 ====================
  private _isCompressed: Ref<boolean>;
  private _isDraggingOrResizing: Ref<boolean>;
  private _nimbusMinimized: Ref<boolean>;
  private _panelVisible: Ref<boolean>;
  private _positionAndSize: Ref<PositionAndSize>;

  // 清理函数
  private cleanupFunctions: Array<() => void>;

  private config: ComponentManagerConfig;

  // 容器引用（用于执行实际的压缩/尺寸/侧面板操作）
  private containerRef: null | {
    collapseSidePanel?: () => void;
    expandForSidePanel?: (extraWidth: number) => void;
    isCompressed?: { value: boolean };
    isSidePanelExpanded?: Ref<boolean>;
    positionAndSize?: { value: PositionAndSize };
    toggleCompression: () => void;
    updatePosition?: (x: number, y: number) => void;
    updatePositionAndSize?: (x: number, y: number, w: number, h: number) => void;
    updateSize?: (w: number, h: number) => void;
  } = null;
  // 调试模式
  private debugMode: boolean;
  // ==================== 事件系统 ====================
  // 统一的事件监听器
  private listeners: Map<InternalEvent, Set<EventCallback<any>>>;

  // 一次性事件监听器
  private onceListeners: Map<InternalEvent, Set<EventCallback<any>>>;

  // ==================== 状态访问器 ====================

  constructor(config: ComponentManagerConfig = {}) {
    this.config = config;
    this.listeners = new Map();
    this.onceListeners = new Map();
    this.debugMode = config.debug ?? false;
    this.cleanupFunctions = [];

    // 初始化状态
    this._panelVisible = ref(config.initialPanelVisible ?? false);
    this._nimbusMinimized = ref(config.initialNimbusMinimized ?? false);
    this._isDraggingOrResizing = ref(false);
    this._isCompressed = ref(false);
    this._positionAndSize = ref({
      x: 0,
      y: 0,
      width: 400,
      height: window.innerHeight,
    });
  }

  /**
   * 获取容器控制器
   */
  get container(): ContainerController {
    return {
      updatePosition: this.updatePosition.bind(this),
      updateSize: this.updateSize.bind(this),
      updatePositionAndSize: this.updatePositionAndSize.bind(this),
      toggleCompression: this.toggleCompression.bind(this),
      expandForSidePanel: this.expandForSidePanel.bind(this),
      collapseSidePanel: this.collapseSidePanel.bind(this),
      positionAndSize: computed(() => this.containerRef?.positionAndSize?.value ?? this._positionAndSize.value),
      isCompressed: computed(() => this._isCompressed.value),
      isSidePanelExpanded: computed(() => this.containerRef?.isSidePanelExpanded?.value ?? false),
    };
  }

  /**
   * 是否压缩状态
   */
  get isCompressed(): Ref<boolean> {
    return this._isCompressed;
  }

  /**
   * 是否正在拖拽或调整大小
   */
  get isDraggingOrResizing(): Ref<boolean> {
    return this._isDraggingOrResizing;
  }

  /**
   * 获取 Nimbus 控制器
   */
  get nimbus(): NimbusController {
    return {
      minimize: this.minimizeNimbus.bind(this),
      restore: this.restoreNimbus.bind(this),
      toggle: this.toggleNimbus.bind(this),
      isMinimized: computed(() => this._nimbusMinimized.value),
    };
  }

  /**
   * Nimbus 是否最小化
   */
  get nimbusMinimized(): Ref<boolean> {
    return this._nimbusMinimized;
  }

  // ==================== 面板控制 ====================

  /**
   * 获取面板控制器
   */
  get panel(): PanelController {
    return {
      show: this.showPanel.bind(this),
      hide: this.hidePanel.bind(this),
      toggle: this.togglePanel.bind(this),
      isVisible: computed(() => this._panelVisible.value),
    };
  }

  /**
   * 面板是否可见
   */
  get panelVisible(): Ref<boolean> {
    return this._panelVisible;
  }

  /**
   * 获取组件状态
   */
  get state(): ComponentManagerState {
    return {
      panelVisible: this._panelVisible,
      nimbusMinimized: this._nimbusMinimized,
      isDraggingOrResizing: this._isDraggingOrResizing,
      positionAndSize: this._positionAndSize,
    };
  }

  /**
   * 折叠侧面板并恢复容器到收起布局
   *
   * 代理调用容器的 collapseSidePanel，与 toggleCompression 模式一致。
   */
  collapseSidePanel(): void {
    if (this.containerRef?.collapseSidePanel) {
      this.containerRef.collapseSidePanel();
    }
  }

  // ==================== Nimbus 控制 ====================

  /**
   * 销毁管理器
   */
  destroy(): void {
    // 清理事件监听器
    this.listeners.clear();
    this.onceListeners.clear();

    // 执行清理函数
    this.cleanupFunctions.forEach(fn => fn());
    this.cleanupFunctions = [];

    if (this.debugMode) {
      console.debug('[ComponentManager] Destroyed');
    }
  }

  /**
   * 发射事件
   * @param event 事件名称
   * @param data 事件数据
   */
  emit<T extends InternalEvent>(event: T, data: InternalEventData[T]): void {
    if (this.debugMode) {
      console.debug(`[ComponentManager] Emitting "${event}"`, data);
    }

    // 触发普通监听器
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`[ComponentManager] Error in listener for "${event}":`, error);
        }
      });
    }

    // 触发一次性监听器
    const onceListeners = this.onceListeners.get(event);
    if (onceListeners && onceListeners.size > 0) {
      const callbacks = Array.from(onceListeners);
      this.onceListeners.delete(event);

      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`[ComponentManager] Error in once listener for "${event}":`, error);
        }
      });
    }
  }

  /**
   * 发射内部事件（别名，用于语义清晰）
   * 用于转发子组件事件
   */
  emitInternal<T extends InternalEvent>(event: T, data: InternalEventData[T]): void {
    this.emit(event, data);
  }

  /**
   * 为侧面板展开扩展容器宽度
   *
   * 代理调用容器的 expandForSidePanel，与 toggleCompression 模式一致。
   *
   * @param extraWidth 首次展开时需要增加的宽度（像素）
   */
  expandForSidePanel(extraWidth: number): void {
    if (this.containerRef?.expandForSidePanel) {
      this.containerRef.expandForSidePanel(extraWidth);
    }
  }

  /**
   * 获取配置
   */
  getConfig(): ComponentManagerConfig {
    return this.config;
  }

  // ==================== 容器控制 ====================

  /**
   * 获取所有已注册的事件列表
   */
  getRegisteredEvents(): InternalEvent[] {
    const events = new Set<InternalEvent>();
    this.listeners.forEach((_, event) => events.add(event));
    this.onceListeners.forEach((_, event) => events.add(event));
    return Array.from(events);
  }

  /**
   * 处理拖拽中
   */
  handleDragging(position: PositionAndSize): void {
    this._isDraggingOrResizing.value = true;
    this._positionAndSize.value = position;
    this.emit('dragging', position);
  }

  /**
   * 处理拖拽停止
   */
  handleDragStop(position: PositionAndSize): void {
    this._isDraggingOrResizing.value = false;
    this._positionAndSize.value = position;
    this.emit('drag-stop', position);
  }

  /**
   * 处理 Nimbus 点击
   */
  handleNimbusClick(): void {
    this.emit('nimbus-click', {});
    this.showPanel();
  }

  /**
   * 处理 Popup 点击
   */
  handlePopupClick(): void {
    this.emit('popup-click', {});
    this.showPanel();
  }

  /**
   * 处理 Popup 快捷方式点击
   */
  handlePopupShortcutClick(shortcut: IShortcut): void {
    this.emit('popup-shortcut-click', { shortcut });
    this.emit('shortcut-click', { shortcut, source: 'popup' });
  }

  /**
   * 处理调整大小停止
   */
  handleResizeStop(position: PositionAndSize): void {
    this._isDraggingOrResizing.value = false;
    this._positionAndSize.value = position;
    this.emit('resize-stop', position);
  }

  /**
   * 处理调整大小中
   */
  handleResizing(position: PositionAndSize): void {
    this._isDraggingOrResizing.value = true;
    this._positionAndSize.value = position;
    this.emit('resizing', position);
  }

  /**
   * 处理快捷方式点击
   */
  handleShortcutClick(shortcut: IShortcut, source: 'main' | 'popup'): void {
    this.emit('shortcut-click', { shortcut, source });
  }

  /**
   * 检查是否有指定事件的监听器
   * @param event 事件名称
   */
  hasListeners(event: InternalEvent): boolean {
    return this.listenerCount(event) > 0;
  }

  // ==================== 拖拽事件处理 ====================

  /**
   * 隐藏面板
   */
  hidePanel(): void {
    this._panelVisible.value = false;
    this.emit('panel-hide', {});
  }

  /**
   * 获取指定事件的监听器数量
   * @param event 事件名称
   */
  listenerCount(event: InternalEvent): number {
    const regular = this.listeners.get(event)?.size ?? 0;
    const once = this.onceListeners.get(event)?.size ?? 0;
    return regular + once;
  }

  /**
   * 最小化 Nimbus
   */
  minimizeNimbus(): void {
    this._nimbusMinimized.value = true;
    this.emit('nimbus-minimize', {});
  }

  /**
   * 取消订阅事件
   * @param event 事件名称
   * @param callback 回调函数（可选，如果不提供则移除所有该事件的监听器）
   */
  off<T extends InternalEvent>(event: T, callback?: EventCallback<T>): void {
    if (callback) {
      this.listeners.get(event)?.delete(callback);
      this.onceListeners.get(event)?.delete(callback);

      if (this.debugMode) {
        console.debug(`[ComponentManager] Unsubscribed from "${event}", remaining: ${this.listenerCount(event)}`);
      }
    } else {
      this.listeners.delete(event);
      this.onceListeners.delete(event);

      if (this.debugMode) {
        console.debug(`[ComponentManager] Removed all listeners for "${event}"`);
      }
    }
  }

  // ==================== Popup 事件处理 ====================

  /**
   * 订阅事件
   * @param event 事件名称
   * @param callback 回调函数
   * @returns 取消订阅函数
   */
  on<T extends InternalEvent>(event: T, callback: EventCallback<T>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }

    this.listeners.get(event)!.add(callback);

    if (this.debugMode) {
      console.debug(`[ComponentManager] Subscribed to "${event}", total: ${this.listenerCount(event)}`);
    }

    // 返回取消订阅函数
    return () => {
      this.off(event, callback);
    };
  }

  /**
   * 订阅一次性事件（触发后自动取消订阅）
   * @param event 事件名称
   * @param callback 回调函数
   * @returns 取消订阅函数
   */
  once<T extends InternalEvent>(event: T, callback: EventCallback<T>): () => void {
    if (!this.onceListeners.has(event)) {
      this.onceListeners.set(event, new Set());
    }

    this.onceListeners.get(event)!.add(callback);

    if (this.debugMode) {
      console.debug(`[ComponentManager] Subscribed once to "${event}"`);
    }

    return () => {
      this.onceListeners.get(event)?.delete(callback);
    };
  }

  // ==================== 快捷方式处理 ====================

  /**
   * 恢复 Nimbus
   */
  restoreNimbus(): void {
    this._nimbusMinimized.value = false;
    this.emit('nimbus-restore', {});
  }

  // ==================== 统一事件系统 ====================

  /**
   * 设置压缩状态（用于状态同步，不触发实际压缩操作）
   */
  setCompressed(value: boolean): void {
    this._isCompressed.value = value;
  }

  /**
   * 设置容器引用
   * 用于 ComponentManager 直接调用容器的压缩/侧面板方法
   */
  setContainerRef(
    ref: null | {
      collapseSidePanel?: () => void;
      expandForSidePanel?: (extraWidth: number) => void;
      isCompressed?: { value: boolean };
      isSidePanelExpanded?: Ref<boolean>;
      positionAndSize?: { value: PositionAndSize };
      toggleCompression: () => void;
      updatePosition?: (x: number, y: number) => void;
      updatePositionAndSize?: (x: number, y: number, w: number, h: number) => void;
      updateSize?: (w: number, h: number) => void;
    },
  ): void {
    this.containerRef = ref;
    if (ref?.isCompressed) {
      this._isCompressed.value = ref.isCompressed.value;
    }
  }

  /**
   * 设置调试模式
   * @param enabled 是否启用调试模式
   */
  setDebugMode(enabled: boolean): void {
    this.debugMode = enabled;
  }

  /**
   * 设置拖拽/调整大小状态
   */
  setDraggingOrResizing(value: boolean): void {
    this._isDraggingOrResizing.value = value;
  }

  /**
   * 显示面板
   */
  showPanel(sessionCode?: string): void {
    this._panelVisible.value = true;
    this.emit('panel-show', { sessionCode });
  }

  /**
   * 切换压缩状态
   *
   * 如果已设置容器引用，会调用容器的实际压缩方法。
   * 否则只更新内部状态（用于状态同步）。
   */
  toggleCompression(): void {
    if (this.containerRef) {
      // 调用容器的实际压缩方法
      this.containerRef.toggleCompression();
      // 状态会通过 compression-change 事件同步回来
    } else {
      // 如果没有容器引用，只更新内部状态（用于状态同步）
      this._isCompressed.value = !this._isCompressed.value;
    }
  }

  /**
   * 切换 Nimbus 最小化状态
   */
  toggleNimbus(): void {
    if (this._nimbusMinimized.value) {
      this.restoreNimbus();
    } else {
      this.minimizeNimbus();
    }
  }

  /**
   * 切换面板显示状态
   */
  togglePanel(): void {
    if (this._panelVisible.value) {
      this.hidePanel();
    } else {
      this.showPanel();
    }
  }

  /**
   * 更新位置
   */
  updatePosition(x: number, y: number): void {
    this._positionAndSize.value = {
      ...this._positionAndSize.value,
      x,
      y,
    };
  }

  // ==================== 生命周期 ====================

  /**
   * 同时更新位置和大小
   */
  updatePositionAndSize(x: number, y: number, width: number, height: number): void {
    this._positionAndSize.value = { x, y, width, height };
  }

  /**
   * 更新大小
   */
  updateSize(width: number, height: number): void {
    this._positionAndSize.value = {
      ...this._positionAndSize.value,
      width,
      height,
    };
  }
}

/**
 * 创建组件管理器
 */
export function createComponentManager(config: ComponentManagerConfig): ComponentManager {
  return new ComponentManager(config);
}
