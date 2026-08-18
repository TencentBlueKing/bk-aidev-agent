/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { ComputedRef, MaybeRefOrGetter, Ref } from 'vue';

import type { ModelSelectionManager } from '../manager/business/model-selection-manager';
import type {
  GetSideRenderComponent,
  GetSideTabRenderComponent,
  IChatHelper,
  IRequestOptions,
  IShortcut,
  OnCustomTabChange,
} from '../types';
import type { IAgentInfo, ILlmItem, ISession } from '@blueking/chat-helper';
import type { RenderMode } from '@blueking/chat-x';
import type { AiSizeMode, IAiSlashMenuItem, IModelOption, ISkillListItem, IToolBtn, Message } from '@blueking/chat-x';
import type { TippyOptions } from 'vue-tippy';

/**
 * ChatBot 组件 Emits
 * 使用对象语法定义，避免 Vue 模板类型推断问题
 */
export type ChatBotEmits = {
  /** 自定义 AI 消息工具点击（非内置 cite/rebuild/delete/like/unlike） */
  'agent-action': [tool: IToolBtn, messages: Message[]];
  /** Agent 信息加载完成事件 */
  'agent-info-loaded': [chatHelper: IChatHelper];
  /** 取消分享事件 */
  'cancel-share': [];
  /**
   * 确认分享/多选事件
   * @param source 触发多选态的按钮；内置分享为 `share` 或 undefined，自定义 triggerSelection 按钮则为对应工具对象
   */
  'confirm-share': [messages: Message[], source?: IToolBtn];
  error: [error: Error];
  /** 执行情况面板展开/折叠事件 */
  'execution-panel-change': [isCollapse: boolean, resizeAsideWidth?: number];
  /** 用户反馈事件 */
  feedback: [tool: IToolBtn, message: Message, reasonList: string[], otherReason: string];
  'receive-end': [];
  'receive-start': [];
  'receive-text': [];
  /**
   * 会话名称变更（手动改名，或首条消息后 AI 自动重命名成功）
   * 第二参 sessionCode 便于业务在切会话后仍能按 id 维护自己的会话列表；旧监听只取第一参仍兼容
   */
  rename: [newName: string, sessionCode: string];
  /** 请求进入分享模式事件（来自 message-tools 的 share 按钮） */
  'request-share': [];
  'send-message': [message: string];
  'session-switched': [session: ISession | null];
  'shortcut-click': [data: { shortcut: IShortcut; source: 'main' | 'popup' }];
  stop: [];
  /** 侧栏折叠态（v-model:asideCollapsed） */
  'update:asideCollapsed': [collapsed: boolean];
};

/**
 * ChatBot 组件 Expose
 */
export interface ChatBotExpose {
  currentSession: Ref<ISession | null>;
  isGenerating: Ref<boolean>;

  /** 是否已完成初始化（独立模式：含 sessionList；集成模式：manager 已挂载） */
  isReady: boolean;

  // 状态获取（使用 ComputedRef 以支持响应式）
  messages: ComputedRef<Message[]>;
  /**
   * 当前选中模型 llm_code
   * （通过组件实例访问时经 proxyRefs 拆包，得到裸值）
   */
  selectedLlmCode: ComputedRef<string | undefined>;
  /** 进入分享选择模式（委托给 ChatContainer） */
  enterShareMode: () => void;
  /** 退出分享选择模式（委托给 ChatContainer） */
  exitShareMode: () => void;
  focusInput: () => void;
  // ChatHelper 访问
  /** 获取 chatHelper 实例，如果初始化失败则返回 null */
  getChatHelper: () => IChatHelper | null;
  /**
   * 选择快捷指令并显示表单
   * @param shortcut 快捷指令
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  selectShortcut: (shortcut: IShortcut, selectedText?: string) => void;

  // 消息操作
  sendMessage: (message: string) => Promise<void>;

  /**
   * 直接发送快捷指令（跳过表单，等价于旧版 handleShortcutClick(_, true)）
   * 从 shortcut.components 的 default 值构建 formModel，直接发送消息
   * @param shortcut 快捷指令
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  sendShortcut: (shortcut: IShortcut, selectedText?: string) => Promise<void>;
  // 其他
  setCiteText: (text: string) => void;

  stopGeneration: () => void;

  // 会话操作
  switchSession: (sessionCode: string) => Promise<void>;
  /**
   * 主动刷新 agentInfo 并更新内部状态
   * 业务方可调用此方法获取最新的 agent 信息，同时会自动更新 shortcuts 等状态
   *
   * @returns 最新的 agentInfo 数据，获取失败返回 null
   */
  updateAgentInfo: () => Promise<IAgentInfo | null>;
  /** 等待初始化完成，语义对齐 AIBlueking ensureSessionReady */
  whenReady: () => Promise<void>;
}

/**
 * ChatBot 组件 Props
 * ChatBot 支持两种使用模式：
 * 1. 独立模式：直接传入 url，组件内部创建 chatHelper
 * 2. 集成模式：传入 chatHelper 实例，复用父组件的 chatHelper
 */
export interface ChatBotProps {
  /** 是否始终创建新会话（初始化时不判断最近会话是否有内容，直接新建） */
  alwaysCreateNewSession?: boolean;
  /** 侧栏折叠态。传入后严格受控；不传时由组件内部自持（默认折叠）。侧栏固定从右侧展开。 */
  asideCollapsed?: boolean;

  /** 是否自动加载 */
  autoLoad?: boolean;
  // === 模式选择 ===
  /**
   * ChatHelper 实例（集成模式）
   * 当传入 chatHelper 时，组件将使用该实例而非内部创建
   * 优先级高于 url
   */
  chatHelper?: IChatHelper;
  /**
   * 是否启用模型选择（默认 true）
   * 为 true 时拉取 GET llms/；列表非空才展示 ModelSelector
   */
  enableModelSelect?: boolean;
  // === 功能开关 ===
  /** 是否启用消息选择 */
  enableSelection?: boolean;
  /**
   * 接口/业务错误时是否自动弹出 Message 提示（默认 true）
   * 设为 false 可自行通过 @error 事件处理；AIBlueking 内嵌时会关闭以免双弹
   */
  errorToast?: boolean;
  /** 「执行情况」Tab 是否展示，缺省 true；为 false 时从 Tab 栏隐藏（该 Tab order 固定 0 且不可关闭） */
  executionTabVisible?: boolean;
  // === 其他配置 ===
  /** 自定义 CSS 类名 */
  extCls?: string;

  /** 自定义侧栏内容区渲染 */
  getSideRenderComponent?: GetSideRenderComponent;
  /** 自定义侧栏 Tab 标签渲染 */
  getSideTabRenderComponent?: GetSideTabRenderComponent;

  // === 样式配置 ===
  /** 高度 */
  height?: number | string;

  /** 欢迎语 */
  helloText?: string;
  /** 最大宽度 */
  maxWidth?: number | string;
  /**
   * 自定义 AI 消息主工具组（copy/cite/rebuild/share 一排）
   * 以内置列表为基底，按 id 覆盖同名项、追加新项；`{ id, hidden: true }` 可隐藏内置项
   */
  messageTools?: IToolBtn[];

  /** MessageTools 的 tippy 弹窗配置（如 appendTo，用于控制弹窗挂载位置和层级） */
  messageToolsTippyOptions?: MessageToolsTippyOptions;

  /**
   * 外部传入的模型列表（有值时跳过内部拉取，优先使用）
   * 结构对齐 chat-x IModelOption / chat-helper ILlmItem
   */
  models?: ILlmItem[] | IModelOption[];

  /**
   * 外部注入的模型选择管理器（集成模式）
   * AIBlueking 传入自身实例，使外壳层的会话创建与聊天区共享同一份模型选中状态；
   * 未传时组件内部自建
   */
  modelSelectionManager?: ModelSelectionManager;

  /** 覆盖默认 Flow 节点详情拉取；未传则使用内置逻辑 */
  onCustomTabChange?: OnCustomTabChange;

  /** 输入框占位文本 */
  placeholder?: string;

  /** 预设提示词列表 */
  prompts?: string[];
  // === 渲染模式 ===
  /** 渲染模式：chat(默认)、share(分享)、test(测试) */
  renderMode?: RenderMode;
  // === 请求配置 ===
  /** 请求选项（仅独立模式有效；支持 ref/computed） */
  requestOptions?: MaybeRefOrGetter<IRequestOptions>;

  /** 资源列表（输入 @ 触发） */
  resources?: IAiSlashMenuItem[];
  // === 会话配置 ===
  /** 会话编码 */
  sessionCode?: string;

  /** 分享操作是否加载中 */
  shareLoading?: boolean;

  // === 快捷方式 ===
  /** 快捷方式列表 */
  shortcuts?: IShortcut[];

  /**
   * 字号主题档位，透传至 ChatContainer
   * - `small`（默认）：12px 基准
   * - `normal`：14px 基准
   */
  size?: AiSizeMode;

  /**
   * 消息时间展示所用的 IANA 时区名（如 Asia/Shanghai），透传至 ChatContainer
   * 未配置时按浏览器时区展示
   */
  timezone?: string;

  /** 技能列表（输入 / 触发） */
  skills?: ISkillListItem[];

  /**
   * 自定义 AI 消息反馈工具组（like/unlike/delete 一排）
   * 合并规则同 messageTools
   */
  updateTools?: IToolBtn[];

  // === 基础配置 ===
  /**
   * API 服务地址（独立模式）
   * 当未传入 chatHelper 时，使用此 url 创建内部 chatHelper
   */
  url?: string;
  /** 使用 agentName 作为欢迎标题 */
  useAgentName?: boolean;
  /** ResizeLayout 配置（执行情况 / 文件产物侧面板拖拽）；ChatBot 默认 initialDivide 560px，可覆盖 */
  resizeProps?: {
    disabled?: boolean;
    initialDivide?: number | string;
    max?: number;
    min?: number;
  };
}

export type { GetSideRenderComponent, GetSideTabRenderComponent, OnCustomTabChange };

export type { IRequestOptions } from '../types';

export type MessageToolsTippyOptions = Partial<
  Omit<TippyOptions, 'content' | 'getReferenceClientRect' | 'triggerTarget'>
>;
