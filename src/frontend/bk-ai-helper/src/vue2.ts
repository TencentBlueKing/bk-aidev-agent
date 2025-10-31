/* eslint-disable @typescript-eslint/no-explicit-any */
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

// @ts-nocheck
import { createApp, h } from 'vue';

import BkAiHelper from './vue3';

export default {
  beforeDestroy() {
    this.unWatchStack.forEach(unWatch => unWatch?.());
    this.app?.unmount();
  },
  created() {
    const props = this.$props;
    const emit = this.$emit.bind(this);
    let bkAiHelperInstance;
    this.app = createApp({
      render() {
        // eslint-disable-next-line @typescript-eslint/no-this-alias
        bkAiHelperInstance = this;
        return h(BkAiHelper, {
          baseUrl: this.baseUrl || props.baseUrl,
          title: this.title || props.title,
          formTitle: this.formTitle || props.formTitle,
          placeholder: this.placeholder || props.placeholder,
          prompt: this.prompt || props.prompt,
          formOptions: this.formOptions || props.formOptions,
          onSuccess() {
            emit('success', ...arguments);
          },
          onError() {
            emit('error', ...arguments);
          },
          onResponse() {
            emit('response', ...arguments);
          },
          ...this.$attrs,
        });
      },
    });
    this.unWatchStack = Object.keys(this.$props).map(k => {
      return this.$watch(k, v => {
        bkAiHelperInstance[k] = v;
        bkAiHelperInstance.$forceUpdate();
      });
    });
  },
  data() {
    return {
      app: null,
      unWatchStack: [],
    };
  },
  methods: {},
  mounted() {
    this.app?.mount(this.$el);
  },
  name: 'BkAiHelper',
  props: {
    baseUrl: {
      default: '',
      type: String,
    },
    formOptions: {
      default: () => ({}),
      type: Object,
    },
    formTitle: {
      default: '',
      type: String,
    },
    placeholder: {
      default: '',
      type: String,
    },
    prompt: {
      default: '',
      type: String,
    },
    title: {
      default: '',
      type: String,
    },
  },
  render(createElement) {
    return createElement('div');
  },
} as any;
