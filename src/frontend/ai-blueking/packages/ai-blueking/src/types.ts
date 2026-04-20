/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

// 重导出 AG-UI SDK 类型
export type {
  IAgentCommand,
  IAgentCommandComponent,
  IAgentInfo,
  IAgentModule,
  IMessage,
  IMessageModule,
  ISession,
  ISessionModule,
  ISupportUpload,
  MessageRole,
  MessageStatus,
} from '@blueking/chat-helper';

// MessageContentType 从 chat-x 导出
export { MessageContentType } from '@blueking/chat-x';

import type { VNode } from 'vue';

import type { RenderMode } from '@blueking/chat-x';

// 从 Manager 导入类型
import type { PositionAndSize } from './manager/types';
// 导入 chat-helper 类型用于扩展
import type {
  IAgentCommand,
  IAgentCommandComponent,
  IAgentModule,
  IMessageModule,
  ISessionModule,
} from '@blueking/chat-helper';
import type { IAiSlashMenuItem } from '@blueking/chat-x';
import type { CreateSessionOptions } from './manager/business/types';

/**
 * AIBlueking 组件 Emits 类型定义
 */
export interface AIBluekingEmits {
  // 面板事件
  (e: 'show'): void;
  (e: 'close'): void;

  // 拖拽事件
  (e: 'dragging', position: PositionAndSize): void;
  (e: 'resizing', position: PositionAndSize): void;
  (e: 'drag-stop', position: PositionAndSize): void;
  (e: 'resize-stop', position: PositionAndSize): void;

  // 消息事件
  (e: 'send-message', message: string): void;
  (e: 'receive-start'): void;
  (e: 'receive-text'): void;
  (e: 'receive-end'): void;
  (e: 'stop'): void;

  // 快捷方式事件
  (e: 'shortcut-click', data: { shortcut: IShortcut; source: 'main' | 'popup' }): void;

  // 会话事件
  (e: 'session-initialized', data: { openingRemark: string; predefinedQuestions: string[] }): void;

  // 错误事件
  (e: 'sdk-error', data: { apiName: string; code: number; data: unknown; message: string }): void;

  // 消息选择事件（与 useEventBridge transformEventDataToEmitArgs 单参 payload 一致）
  (e: 'transfer-messages', data: { messageIds: string[] }): void;
  (e: 'share-messages', data: { messageIds: string[] }): void;

  // Header 相关事件
  (e: 'new-chat'): void;
  (e: 'new-chat-created', session: { sessionCode: string; sessionName?: string; createdAt?: string }): void;
  (e: 'history-click', event: Event): void;
  (e: 'auto-generate-name'): void;
  (e: 'help-click'): void;
  (e: 'rename', newName: string): void;
  (e: 'share'): void;
}

/**
 * AIBlueking 组件 Expose 类型定义
 */
export interface AIBluekingExpose {
  // 会话管理
  addNewSession: (options?: CreateSessionOptions) => Promise<void>;
  focusInput: () => void;

  /** 获取 chatHelper 实例，用于访问 agent/session/message 等底层模块 */
  getChatHelper: () => IChatHelper | null;
  /** 关闭面板（等同于用户点击关闭按钮） */
  handleClose: () => void;
  handleShow: (sessionCode?: string) => Promise<void>;

  hide: () => void;

  /**
   * 编程式触发快捷指令（显示表单）
   * 等价于旧版 window.aiBlueking.handleShortcutClick({ shortcut, source }, false)
   * 只显示表单，不会自动提交，需用户手动点击确认
   * @param shortcut 快捷指令对象（通常来自 chatHelper.agent.info.value?.conversationSettings?.commands）
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  selectShortcut: (shortcut: IShortcut, selectedText?: string) => void;

  // 会话操作
  sendMessage: (message: string) => Promise<void>;

  /**
   * 直接发送快捷指令（跳过表单，等价于旧版 handleShortcutClick(_, true)）
   * 从 shortcut.components 的 default 值构建 formModel，直接发送消息
   * @param shortcut 快捷指令对象
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  sendShortcut: (shortcut: IShortcut, selectedText?: string) => Promise<void>;

  // 其他
  setCiteText: (text: string) => void;
  // 面板控制
  show: (sessionCode?: string, options?: { isTemporary?: boolean }) => Promise<void>;
  stopGeneration: () => void;

  switchToSession: (sessionCode: string) => Promise<void>;
  // 容器控制
  updatePosition: (x: number, y: number) => void;
  updatePositionAndSize: (x: number, y: number, w: number, h: number) => void;

  updateSessionName: (sessionCode: string, newName: string) => Promise<void>;
  updateSize: (w: number, h: number) => void;
}

/**
 * AIBlueking 组件 Props 类型定义
 */
export interface AIBluekingProps {
  /** 是否自动切换到初始会话 */
  autoSwitchToInitialSession?: boolean;
  /**
   * Nimbus 悬浮球点击前的钩子函数
   * 返回 false 阻止默认的 showPanel 行为，返回 true 或不返回则继续默认行为
   * 可用于在点击后先执行自定义逻辑（如切换到固定 session）再决定是否打开面板
   */
  beforeNimbusClick?: () => boolean | Promise<boolean | void> | void;
  /** 默认聊天输入框位置 */
  defaultChatInputPosition?: 'bottom' | undefined;
  /** 默认高度 */
  defaultHeight?: number;

  /** 默认左侧位置 */
  defaultLeft?: number;
  /** 是否默认最小化 */
  defaultMinimize?: boolean;
  /** 默认顶部位置 */
  defaultTop?: number;
  // 容器配置
  /** 默认宽度 */
  defaultWidth?: number;
  /** 是否禁用输入 */
  disabledInput?: boolean;

  /** 是否可拖拽 */
  draggable?: boolean;
  /** 下拉菜单配置 */
  dropdownMenuConfig?: DropdownMenuConfig;
  /** 是否启用会话管理 */
  enableChatSession?: boolean;
  /** 是否启用选中文本弹窗 */
  enablePopup?: boolean;
  /** 自定义 CSS 类名 */
  extCls?: string;
  /** 欢迎语 */
  helloText?: string;

  /** 是否隐藏默认触发器 */
  hideDefaultTrigger?: boolean;
  /** 是否隐藏头部 */
  hideHeader?: boolean;

  // 功能开关
  /** 是否隐藏悬浮球 */
  hideNimbus?: boolean;
  /** 初始会话编码 */
  initialSessionCode?: string;
  /** 挂载时是否加载最近会话 */
  loadRecentSessionOnMount?: boolean;
  /** 最大宽度 */
  maxWidth?: number | string;

  /** 最小化时的内边距 */
  miniPadding?: number;
  // Nimbus 配置
  /** 悬浮球大小 */
  nimbusSize?: 'large' | 'normal' | 'small';
  /** 输入框占位文本 */
  placeholder?: string;
  /** 预设提示词列表 */
  prompts?: string[];
  // 其他配置
  /** 请求配置 */
  requestOptions?: IRequestOptions;
  /** 资源列表（输入 @ 触发） */
  resources?: IAiSlashMenuItem[];
  /** 快捷操作显示数量限制 */
  shortcutLimit?: number;
  // Popup 配置
  /** 快捷操作列表 */
  shortcuts?: IShortcut[];
  /** 是否显示压缩图标 */
  showCompressionIcon?: boolean;
  /** 是否显示历史记录图标 */
  showHistoryIcon?: boolean;
  /** 是否显示更多图标 */
  showMoreIcon?: boolean;
  /** 是否显示新建会话图标 */
  showNewChatIcon?: boolean;
  /** 传送门目标 */
  teleportTo?: string;
  /** 组件标题 */
  title?: string;
  // 基础配置
  /** API 服务地址 */
  url?: string;
  /** 渲染模式：chat(默认)、share(分享)、test(测试) */
  renderMode?: RenderMode;
  /** 快捷操作过滤函数 */
  shortcutFilter?: (shortcut: IShortcut, selectedText: string) => boolean;
  /** ResizeLayout 配置（执行情况侧面板拖拽） */
  resizeProps?: {
    disabled?: boolean;
    initialDivide?: number | string;
    max?: number;
    min?: number;
  };
}

/**
 * 下拉菜单配置
 */
export interface DropdownMenuConfig {
  showAutoGenerate?: boolean;
  showRename?: boolean;
  showShare?: boolean;
}

/**
 * Agent 信息的简化接口
 * 用于组件间传递 agent 相关数据
 */
export interface IAgentInfoData {
  /** Agent 名称 */
  agentName?: string;
  /** SaaS URL */
  saasUrl?: string;
  /** 聊天群组配置 */
  chatGroup?: {
    enabled: boolean;
    staff: string[];
    username: string;
  };
  /** 会话设置 */
  conversationSettings?: {
    enableChatSession?: boolean;
    openingRemark?: string;
    predefinedQuestions?: string[];
  };
}

// 重导出，方便使用
export type { PositionAndSize };

/**
 * ChatHelper 实例类型
 * 由 useChatHelper 返回的完整对象
 *
 * 关键 API:
 * - agent.chat(sessionCode): Promise<void> - 发送消息
 * - session.getSessions(): 获取会话列表
 * - session.chooseSession(sessionCode): 选择会话并加载消息
 * - session.current: 当前会话信息，包含 sessionCode
 * - session.list: 会话列表
 */
export interface IChatHelper {
  /** Agent 模块 - 管理 agent 信息和聊天 */
  agent: IAgentModule;
  /** HTTP 模块 */
  http: unknown;
  /** Message 模块 - 管理消息 */
  message: IMessageModule;
  /** Session 模块 - 管理会话 */
  session: ISessionModule;
}

/**
 * 请求配置
 */
export interface IRequestOptions {
  data?: (() => Record<string, unknown>) | Record<string, unknown>;
  headers?: (() => Record<string, string>) | Record<string, string>;
}

/**
 * 扩展 IAgentCommand 类型，添加自定义 icon 和模式支持
 */
export interface IShortcut extends IAgentCommand {
  /**
   * 用于强制重新渲染组件的唯一键值
   * 每次快捷指令更新时都会生成新的时间戳
   */
  bindKey?: string;

  /**
   * 是否启用自动回填
   * 当为 true 时，划词选择的内容会自动回填到 fill_back_component_key 指定的字段
   */
  enable_fill_back?: boolean;

  /**
   * 自动回填的目标字段 key
   * 当 enable_fill_back 为 true 时，选中的文本会回填到此字段
   */
  fill_back_component_key?: string;

  /**
   * 是否隐藏底部按钮区域，默认为 false
   */
  hideFooter?: boolean;

  /**
   * 指定指令模式：simple 简单模式，advanced 高级模式
   * 默认为 advanced 模式
   * simple模式：直接展示指令组件，没有外层 header 和 footer
   * advanced模式：展示指令组件，有外层 header 和 footer
   */
  mode?: 'advanced' | 'simple';

  /**
   * 自定义 icon 渲染函数
   * @param h - Vue 的 h 函数，用于创建 VNode
   * @returns VNode
   */
  iconRender?: (h: (type: any, props?: any, children?: any) => any) => VNode;
}

/**
 * 扩展 IAgentCommandComponent 类型，添加选中文本和模式支持
 */
export interface IShortcutComponent extends IAgentCommandComponent {
  /**
   * 控制指令组件中单个输入模块的展示模式
   * simple模式：直接展示输入组件，没有label
   * advanced模式：展示输入组件，有label
   */
  mode?: 'advanced' | 'simple';

  /**
   * 选中的文本内容
   */
  selectedText?: null | string;

  /**
   * 当前输入模块是否显示发送按钮，默认为 false
   * 如果为 true，则会在输入模块后面追加显示发送按钮
   */
  showSendButton?: boolean;
}
