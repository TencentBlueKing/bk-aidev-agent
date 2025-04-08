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

import { DEFAULT_SHORTCUTS } from './config/shortcuts';
import AiBlueking from './vue3.ts';

import type { ShortCut } from './types/index.ts';

export type * from './types/index.ts';

export default {
  name: 'AiBlueking',
  render(createElement: any) {
    return createElement('div', {
      style: { width: '100%' },
    });
  },
  props: {
    shortcuts: {
      default: () => DEFAULT_SHORTCUTS,
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
          shortcuts: that.shortcuts,
          enablePopup: that.enablePopup,
          url: that.url,
          prompts: that.prompts,
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
          ...that.$attrs,
        });
        return aiBlueking;
      },
    });
    this.unWatchStack = Object.keys(this.$props).map(k => {
      return this.$watch(
        k,
        () => {
          instance.$forceUpdate();
        },
        { deep: true },
      );
    });
    this.handleShow = () => {
      aiBlueking.component.exposed.handleShow();
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
  },
  mounted() {
    this.app?.mount(this.$el);
  },
  beforeDestroy() {
    this.unWatchStack.forEach((unWatch: Function) => unWatch?.());
    this.app?.unmount();
  },
} as any;
