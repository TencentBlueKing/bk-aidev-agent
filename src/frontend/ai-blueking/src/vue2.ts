/* eslint-disable @typescript-eslint/no-this-alias */
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
import { createApp, h } from 'vue';

import type { ShortCut } from './types/index.ts';
import AiBlueking from './vue3.ts';

export type * from './types/index.ts';

export default {
  name: 'AiBlueking',
  render(createElement: any) {
    return createElement('div', {
      style: { width: '100%' },
    });
  },
  props: {
    extCls: {
      default: '',
      type: String,
    },
    shortcuts: {
      default: () => [],
      type: Array,
    },
    enablePopup: {
      default: true,
      type: Boolean,
    },
    url: {
      default: '',
      type: String,
    },
    prompts: {
      default: () => [],
      type: Array,
    },
    teleportTo: {
      default: 'body',
      type: String,
    },
    title: {
      type: String,
    },
    helloText: {
      type: String,
    },
    requestOptions: {
      default: () => ({}),
      type: Object,
    },
    defaultMinimize: {
      default: false,
      type: Boolean,
    },
    hideHeader: {
      default: false,
      type: Boolean,
    },
    hideNimbus: {
      default: false,
      type: Boolean,
    },
    draggable: {
      default: true,
      type: Boolean,
    },
    defaultWidth: {
      type: Number,
    },
    defaultHeight: {
      type: Number,
    },
    defaultLeft: {
      type: Number,
    },
    defaultTop: {
      type: Number,
    },
    disabledInput: {
      default: false,
      type: Boolean,
    },
    initialSessionCode: {
      type: String,
      default: '',
    },
    autoSwitchToInitialSession: {
      type: Boolean,
      default: false,
    },
    loadRecentSessionOnMount: {
      type: Boolean,
      default: false,
    },
    shortcutLimit: {
      type: Number,
      default: 3,
    },
    shortcutFilter: {
      type: Function,
      default: undefined,
    },
  },
  data() {
    return {
      app: null,
      unWatchStack: [],
    };
  },
  created() {
    const emit = this.$emit.bind(this);
    let instance: any = null;
    let aiBlueking: any = null;
    const that = this;

    this.app = createApp({
      render() {
        instance = this;
        aiBlueking = h(AiBlueking, {
          extCls: that.extCls,
          shortcuts: that.shortcuts,
          shortcutLimit: that.shortcutLimit,
          shortcutFilter: that.shortcutFilter,
          enablePopup: that.enablePopup,
          url: that.url,
          title: that.title,
          helloText: that.helloText,
          requestOptions: that.requestOptions,
          prompts: that.prompts,
          disabledInput: that.disabledInput,
          teleportTo: that.teleportTo,
          defaultMinimize: that.defaultMinimize,
          hideHeader: that.hideHeader,
          hideNimbus: that.hideNimbus,
          draggable: that.draggable,
          defaultWidth: that.defaultWidth,
          defaultHeight: that.defaultHeight,
          defaultLeft: that.defaultLeft,
          defaultTop: that.defaultTop,
          initialSessionCode: that.initialSessionCode,
          autoSwitchToInitialSession: that.autoSwitchToInitialSession,
          loadRecentSessionOnMount: that.loadRecentSessionOnMount,
          onClose() {
            emit('close', ...arguments);
          },
          onStop() {
            emit('stop', ...arguments);
          },
          onShortcutClick() {
            emit('shortcut-click', ...arguments);
          },
          onShow() {
            emit('show', ...arguments);
          },
          onSendMessage() {
            emit('send-message', ...arguments);
          },
          onReceiveStart() {
            emit('receive-start', ...arguments);
          },
          onReceiveEnd() {
            emit('receive-end', ...arguments);
          },
          onReceiveText() {
            emit('receive-text', ...arguments);
          },
          onSessionInitialized() {
            emit('session-initialized', ...arguments);
          },
          ...that.$attrs,
        });

        return aiBlueking;
      },
    });
    this.unWatchStack = Object.keys(this.$props).map(k =>
      this.$watch(
        k,
        () => {
          instance.$forceUpdate();
        },
        { deep: true }
      )
    );
    this.handleShow = (sessionCode?: string) => {
      aiBlueking.component.exposed.handleShow(sessionCode);
    };
    this.handleStop = () => {
      aiBlueking.component.exposed.handleStop();
    };
    this.handleShortcutClick = (shortcut: ShortCut) => {
      aiBlueking.component.exposed.handleShortcutClick(shortcut);
    };
    this.sendChat = (options: { message: string; cite: string; shortcut: ShortCut }) => {
      aiBlueking.component.exposed.sendChat(options);
    };
    this.handleClose = () => {
      aiBlueking.component.exposed.handleClose();
    };
    this.handleSendMessage = (message: string) => {
      aiBlueking.component.exposed.handleSendMessage(message);
    };
    this.handleDelete = (index: number) => {
      aiBlueking.component.exposed.handleDelete(index);
    };
    this.handleRegenerate = (index: number) => {
      aiBlueking.component.exposed.handleRegenerate(index);
    };
    this.handleResend = (index: number, value: { message: string; cite: string }) => {
      aiBlueking.component.exposed.handleResend(index, value);
    };
    this.updateRequestOptions = (options: { message: string; cite: string }) => {
      aiBlueking.component.exposed.updateRequestOptions(options);
    };
    this.addNewSession = (sessionCode?: string) => {
      return aiBlueking.component.exposed.addNewSession(sessionCode);
    };
    this.updateSessionName = (sessionCode: string, newName: string) => {
      return aiBlueking.component.exposed.updateSessionName(sessionCode, newName);
    };
    this.switchToSession = (sessionCode: string) => {
      return aiBlueking.component.exposed.switchToSession(sessionCode);
    };
    this.getSessionList = () => {
      return aiBlueking.component.exposed.getSessionList();
    };
    this.sessionList = () => {
      return aiBlueking.component.exposed.sessionList();
    };
    this.enableChatSession = () => {
      return aiBlueking.component.exposed.enableChatSession();
    };
    this.currentSessionLoading = () => {
      return aiBlueking.component.exposed.currentSessionLoading;
    };
    this.isLoadingSessionContents = () => {
      return aiBlueking.component.exposed.isLoadingSessionContents;
    };
    this.updateGreetingTextHeight = () => {
      aiBlueking.component.exposed.updateGreetingTextHeight();
    };
    this.setCurrentSession = (sessionCode: string) => {
      aiBlueking.component.exposed.setCurrentSession(sessionCode);
    };
    this.focusInput = () => {
      aiBlueking.component.exposed.focusInput();
    };

    // 添加 组件暴露属性（属性类型使用 defineProperty 添加, 以保持响应式）
    Object.defineProperty(this, 'sessionContents', {
      get: () => {
        const contents = aiBlueking.component.exposed.sessionContents;
        // 解包 Vue3 的 Ref 对象
        let result = contents && contents.__v_isRef ? contents.value : contents;

        // 如果是 Proxy 对象，转换为普通 JavaScript 数组
        if (result && typeof result === 'object') {
          try {
            // 方法1：使用 JSON 转换去掉 Proxy（如果对象是可序列化的）
            result = JSON.parse(JSON.stringify(result));
          } catch (e) {
            // 方法2：如果 JSON 转换失败，尝试手动解构
            if (Array.isArray(result)) {
              result = [...result];
            }
          }
        }

        return Array.isArray(result) ? result : [];
      },
    });
  },
  mounted() {
    this.app?.mount(this.$el);
  },
  beforeDestroy() {
    this.unWatchStack.forEach((unWatch: Function) => unWatch?.());
    this.app?.unmount();
  },
} as any;
