/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
// Vue2 走 vue3-core 以避开 chat-x 预构建 CSS，但须单独引入 icon 字体（与 vue3.ts 一致，不含 chat-x/dist/index.css）
// @ts-ignore - icon 资源文件不需要类型检查
import './assets/icon/iconcool.js';
import './assets/icon/style.css';

import { ChatBot } from './components';
import { t } from './lang';
import { createVue2Wrapper } from './vue2-wrapper';
import AIBlueking from './vue3-core';

import type { ChatBotExpose } from './components/types';
import type { AIBluekingExpose } from './types';

export type * from './types';

// 导出 h 函数，用于自定义 icon 渲染
export { h } from 'vue';

// ==================== 编译时校验：exposeKeys 必须与对应 Expose 接口 key 一致 ====================
// 如果 TS 报错，说明 exposeKeys 缺少或多余了字段，需与 types.ts / components/types.ts 同步
// 正向：exposeKeys 中的每一项必须是接口的 key
// 反向：接口的每一个 key 必须出现在 exposeKeys 中
type AssertKeysMatch<TKeys extends string, TInterface> = TKeys extends keyof TInterface
  ? keyof TInterface extends TKeys
    ? true
    : never
  : never;

const aiBluekingEmitNames = [
  'close',
  'show',
  'stop',
  'shortcut-click',
  'send-message',
  'receive-start',
  'receive-end',
  'receive-text',
  'session-initialized',
  'drag-stop',
  'resize-stop',
  'dragging',
  'resizing',
  'transfer-messages',
  'share-messages',
  'confirm-share',
  'agent-action',
  'sdk-error',
  'new-chat',
  'new-chat-created',
  'history-click',
  'auto-generate-name',
  'help-click',
  'rename',
  'share',
] as const;

const aiBluekingExposeKeys = [
  'show',
  'handleShow',
  'handleClose',
  'hide',
  'sendMessage',
  'stopGeneration',
  'addNewSession',
  'switchToSession',
  'updateSessionName',
  'updatePosition',
  'updateSize',
  'updatePositionAndSize',
  'setCiteText',
  'focusInput',
  'getChatHelper',
  'selectShortcut',
  'sendShortcut',
] as const;

// 编译时断言：aiBluekingExposeKeys 与 AIBluekingExpose 的 keys 完全一致
type AiBluekingKeyCheck = AssertKeysMatch<(typeof aiBluekingExposeKeys)[number], AIBluekingExpose>;
const aiBluekingKeyGuard: AiBluekingKeyCheck = true as AiBluekingKeyCheck;
void aiBluekingKeyGuard;

/**
 * Vue2 兼容层：完整小鲸（Nimbus + 浮窗 + 拖拽）
 */
export default createVue2Wrapper(AIBlueking, {
  name: 'AIBluekingV2',
  props: {
    extCls: {
      type: String,
      default: '',
    },
    shortcuts: {
      type: Array,
      default: () => [],
    },
    enablePopup: {
      type: Boolean,
      default: true,
    },
    url: {
      type: String,
      default: '',
    },
    prompts: {
      type: Array,
      default: () => [],
    },
    teleportTo: {
      type: String,
      default: 'body',
    },
    title: {
      type: String,
      default: '',
    },
    helloText: {
      type: String,
      default: () => t('你好，我是小鲸'),
    },
    useAgentName: {
      type: Boolean,
      default: false,
    },
    requestOptions: {
      type: Object,
      default: () => ({}),
    },
    defaultMinimize: {
      type: Boolean,
      default: false,
    },
    hideHeader: {
      type: Boolean,
      default: false,
    },
    hideNimbus: {
      type: Boolean,
      default: false,
    },
    draggable: {
      type: Boolean,
      default: true,
    },
    defaultWidth: {
      type: Number,
      default: 400,
    },
    defaultHeight: {
      type: Number,
      default: undefined,
    },
    defaultLeft: {
      type: Number,
      default: undefined,
    },
    defaultTop: {
      type: Number,
      default: 0,
    },
    disabledInput: {
      type: Boolean,
      default: false,
    },
    showCompressionIcon: {
      type: Boolean,
      default: true,
    },
    showMoreIcon: {
      type: Boolean,
      default: true,
    },
    showHistoryIcon: {
      type: Boolean,
      default: true,
    },
    showNewChatIcon: {
      type: Boolean,
      default: true,
    },
    defaultChatInputPosition: {
      type: String,
      default: undefined,
    },
    maxWidth: {
      type: [Number, String],
      default: 1000,
    },
    initialSessionCode: {
      type: String,
      default: '',
    },
    autoSwitchToInitialSession: {
      type: Boolean,
      default: false,
    },
    alwaysCreateNewSession: {
      type: Boolean,
      default: false,
    },
    loadRecentSessionOnMount: {
      type: Boolean,
      default: true,
    },
    shortcutLimit: {
      type: Number,
      default: 3,
    },
    shortcutFilter: {
      type: Function,
      default: undefined,
    },
    placeholder: {
      type: String,
      default: undefined,
    },
    enableChatSession: {
      type: Boolean,
      default: true,
    },
    nimbusSize: {
      type: String,
      default: 'normal',
    },
    miniPadding: {
      type: Number,
      default: 0,
    },
    dropdownMenuConfig: {
      type: Object,
      default: () => ({
        showRename: true,
        showAutoGenerate: true,
        showShare: true,
      }),
    },
    resources: {
      type: Array,
      default: undefined,
    },
    messageTools: {
      type: Array,
      default: undefined,
    },
    updateTools: {
      type: Array,
      default: undefined,
    },
    hideDefaultTrigger: {
      type: Boolean,
      default: false,
    },
    beforeNimbusClick: {
      type: Function,
      default: undefined,
    },
    getSideRenderComponent: {
      type: Function,
      default: undefined,
    },
    getSideTabRenderComponent: {
      type: Function,
      default: undefined,
    },
    onCustomTabChange: {
      type: Function,
      default: undefined,
    },
    executionTabVisible: {
      type: Boolean,
      default: undefined,
    },
    resizeProps: {
      type: Object,
      default: undefined,
    },
    size: {
      type: String,
      default: undefined,
    },
  },
  emitNames: [...aiBluekingEmitNames],
  exposeKeys: [...aiBluekingExposeKeys],
  slots: ['codeHeader', 'headerLeft', 'message', 'welcome'],
  deepWatchProps: ['requestOptions', 'shortcuts', 'beforeNimbusClick'],
  methods: {
    show(): Promise<void> {
      console.warn('AIBluekingV2: show method not ready');
      return Promise.resolve();
    },
    handleShow(): Promise<void> {
      console.warn('AIBluekingV2: handleShow method not ready');
      return Promise.resolve();
    },
    handleClose() {
      console.warn('AIBluekingV2: handleClose method not ready');
    },
    hide() {
      console.warn('AIBluekingV2: hide method not ready');
    },
    sendMessage(): Promise<void> {
      console.warn('AIBluekingV2: sendMessage method not ready');
      return Promise.resolve();
    },
    stopGeneration() {
      console.warn('AIBluekingV2: stopGeneration method not ready');
    },
    addNewSession(): Promise<void> {
      console.warn('AIBluekingV2: addNewSession method not ready');
      return Promise.resolve();
    },
    switchToSession(): Promise<void> {
      console.warn('AIBluekingV2: switchToSession method not ready');
      return Promise.resolve();
    },
    updateSessionName(): Promise<void> {
      console.warn('AIBluekingV2: updateSessionName method not ready');
      return Promise.resolve();
    },
    updatePosition() {
      console.warn('AIBluekingV2: updatePosition method not ready');
    },
    updateSize() {
      console.warn('AIBluekingV2: updateSize method not ready');
    },
    updatePositionAndSize() {
      console.warn('AIBluekingV2: updatePositionAndSize method not ready');
    },
    setCiteText() {
      console.warn('AIBluekingV2: setCiteText method not ready');
    },
    focusInput() {
      console.warn('AIBluekingV2: focusInput method not ready');
    },
    getChatHelper(): null {
      console.warn('AIBluekingV2: getChatHelper method not ready');
      return null;
    },
    selectShortcut() {
      console.warn('AIBluekingV2: selectShortcut method not ready');
    },
    sendShortcut(): Promise<void> {
      console.warn('AIBluekingV2: sendShortcut method not ready');
      return Promise.resolve();
    },
  },
});

const chatBotEmitNames = [
  'send-message',
  'error',
  'stop',
  'receive-start',
  'receive-end',
  'receive-text',
  'shortcut-click',
  'session-switched',
  'agent-info-loaded',
  'request-share',
  'confirm-share',
  'cancel-share',
  'execution-panel-change',
  'feedback',
  'agent-action',
] as const;

const chatBotExposeKeys = [
  'sendMessage',
  'stopGeneration',
  'focusInput',
  'setCiteText',
  'switchSession',
  'selectShortcut',
  'sendShortcut',
  'enterShareMode',
  'exitShareMode',
  'getChatHelper',
  'currentSession',
  'isGenerating',
  'messages',
  'isReady',
  'whenReady',
] as const;

// 编译时断言：chatBotExposeKeys 与 ChatBotExpose 的 keys 完全一致
type ChatBotKeyCheck = AssertKeysMatch<(typeof chatBotExposeKeys)[number], ChatBotExpose>;
const chatBotKeyGuard: ChatBotKeyCheck = true as ChatBotKeyCheck;
void chatBotKeyGuard;

/**
 * Vue2 兼容层：可嵌入的 ChatBot（无 Nimbus / 无浮窗壳层）
 */
export const ChatBotV2 = createVue2Wrapper(ChatBot, {
  name: 'ChatBotV2',
  props: {
    chatHelper: {
      type: Object,
      default: undefined,
    },
    url: {
      type: String,
      default: '',
    },
    height: {
      type: [Number, String],
      default: undefined,
    },
    maxWidth: {
      type: [Number, String],
      default: undefined,
    },
    extCls: {
      type: String,
      default: '',
    },
    helloText: {
      type: String,
      default: undefined,
    },
    useAgentName: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: undefined,
    },
    shortcuts: {
      type: Array,
      default: () => [],
    },
    prompts: {
      type: Array,
      default: () => [],
    },
    resources: {
      type: Array,
      default: () => [],
    },
    requestOptions: {
      type: Object,
      default: () => ({}),
    },
    messageToolsTippyOptions: {
      type: Object,
      default: undefined,
    },
    messageTools: {
      type: Array,
      default: undefined,
    },
    updateTools: {
      type: Array,
      default: undefined,
    },
    enableSelection: {
      type: Boolean,
      default: false,
    },
    shareLoading: {
      type: Boolean,
      default: false,
    },
    autoLoad: {
      type: Boolean,
      default: true,
    },
    alwaysCreateNewSession: {
      type: Boolean,
      default: false,
    },
    sessionCode: {
      type: String,
      default: undefined,
    },
    resizeProps: {
      type: Object,
      default: undefined,
    },
    size: {
      type: String,
      default: undefined,
    },
    getSideRenderComponent: {
      type: Function,
      default: undefined,
    },
    getSideTabRenderComponent: {
      type: Function,
      default: undefined,
    },
    onCustomTabChange: {
      type: Function,
      default: undefined,
    },
    executionTabVisible: {
      type: Boolean,
      default: undefined,
    },
  },
  emitNames: [...chatBotEmitNames],
  exposeKeys: [...chatBotExposeKeys],
  slots: ['codeHeader', 'message', 'welcome'],
  deepWatchProps: ['requestOptions', 'shortcuts', 'beforeNimbusClick'],
});
