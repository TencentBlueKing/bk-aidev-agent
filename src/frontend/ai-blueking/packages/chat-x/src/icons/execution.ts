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

import { h } from 'vue';

import { commonSVGProps } from '../common';

export const BkFlowSuccessIcon = h(
  'svg',
  {
    ...commonSVGProps,
    viewBox: '0 0 16 16',
    class: {
      [commonSVGProps.class]: true,
      'ai-bk-flow-success-icon': true,
    },
  },
  [
    h('circle', { cx: '8', cy: '8', r: '7', fill: '#18B456' }),
    h('path', {
      d: 'M4.5 8L7 10.5L11.5 6',
      fill: 'none',
      stroke: 'white',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      'stroke-width': '1.5',
    }),
  ],
);

export const BkFlowFailedIcon = h(
  'svg',
  {
    ...commonSVGProps,
    viewBox: '0 0 16 16',
    class: {
      [commonSVGProps.class]: true,
      'ai-bk-flow-failed-icon': true,
    },
  },
  [
    h('circle', { cx: '8', cy: '8', r: '7', fill: '#EA3636' }),
    h('path', {
      d: 'M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5',
      stroke: 'white',
      'stroke-linecap': 'round',
      'stroke-width': '1.5',
    }),
  ],
);

export const BkFlowSuspendedIcon = h(
  'svg',
  {
    ...commonSVGProps,
    viewBox: '0 0 16 16',
    class: {
      [commonSVGProps.class]: true,
      'ai-bk-flow-suspended-icon': true,
    },
  },
  [
    h('circle', { cx: '8', cy: '8', r: '7', fill: '#F59500' }),
    h('rect', { fill: 'white', height: '6', rx: '0.75', width: '1.5', x: '6', y: '5' }),
    h('rect', { fill: 'white', height: '6', rx: '0.75', width: '1.5', x: '8.5', y: '5' }),
  ],
);

export const BkFlowPendingIcon = h(
  'svg',
  {
    ...commonSVGProps,
    viewBox: '0 0 16 16',
    class: {
      [commonSVGProps.class]: true,
      'ai-bk-flow-pending-icon': true,
    },
  },
  [
    h('circle', { cx: '8', cy: '8', r: '7', fill: '#DCDEE5' }),
    h('rect', { fill: 'white', height: '1.5', rx: '0.75', width: '6', x: '5', y: '7.25' }),
  ],
);

export const ExecutionIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-execution-icon': true,
    },
  },
  [
    h('path', {
      'fill-rule': 'evenodd',
      d: 'M512 64A448 448 0 1 1 64 512 448 448 0 0 1 512 64Zm0 64A384 384 0 0 0 128 512 384 384 0 0 0 784 784 384 384 0 0 0 784 240 384 384 0 0 0 512 128ZM448 576V256h64V512H768v64Z',
    }),
  ],
);

export const NodeOutputIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-node-output-icon': true,
    },
  },
  [
    h('path', {
      d: 'M800 128c17.664 0 32 12.288 32 27.424v545.408L594.016 896H224c-17.664 0-32-12.288-32-27.424V155.424C192 140.288 206.336 128 224 128z m-26.176 59.072H250.176v649.856h276.384v-134.88c0-31.52 28.704-57.12 64-57.12h183.264V187.072zM735.52 704h-144.96a13.024 13.024 0 0 0-5.824 1.216v122.432L735.52 704zM704 480v64H320v-64h384z m-128-96v64h-256v-64h256z m96-128v64H320V256h352z',
    }),
  ],
);

export const NodeTabIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-node-tab-icon': true,
    },
  },
  [
    h('path', {
      d: 'M374.656 640c57.184 0 105.184 41.088 118.72 96.384 1.312-0.16 2.624-0.384 3.968-0.384h368c16.928 0 30.656 14.336 30.656 32s-13.76 32-30.656 32h-368c-1.376 0-2.656-0.256-3.936-0.384-13.568 55.296-61.568 96.384-118.72 96.384-57.184 0-105.216-41.088-118.72-96.384-1.344 0.16-2.624 0.384-3.968 0.384H190.656C173.76 800 160 785.664 160 768s13.76-32 30.656-32h61.344c1.344 0 2.624 0.256 3.936 0.384C269.472 681.088 317.504 640 374.656 640z m0 64c-33.824 0-61.312 28.704-61.312 64s27.52 64 61.312 64c33.824 0 61.344-28.704 61.344-64s-27.52-64-61.344-64z m306.688-320c57.152 0 105.184 41.088 118.72 96.384 1.28-0.16 2.56-0.384 3.936-0.384h61.344c16.928 0 30.656 14.336 30.656 32s-13.76 32-30.656 32h-61.344c-1.344 0-2.624-0.256-3.936-0.384-13.536 55.296-61.568 96.384-118.72 96.384-57.184 0-105.184-41.088-118.72-96.384-1.312 0.16-2.624 0.384-3.968 0.384h-368C173.76 544 160 529.664 160 512s13.76-32 30.656-32h368c1.376 0 2.656 0.256 3.936 0.384 13.568-55.296 61.568-96.384 118.72-96.384z m0 64c-33.824 0-61.344 28.704-61.344 64s27.52 64 61.344 64 61.312-28.704 61.312-64-27.52-64-61.312-64z m-306.688-288c57.184 0 105.184 41.088 118.72 96.384 1.312-0.16 2.624-0.384 3.968-0.384h368c16.928 0 30.656 14.336 30.656 32s-13.76 32-30.656 32h-368c-1.376 0-2.656-0.256-3.936-0.384-13.568 55.296-61.568 96.384-118.72 96.384-57.184 0-105.216-41.088-118.72-96.384-1.344 0.16-2.624 0.384-3.968 0.384H190.656C173.76 320 160 305.664 160 288s13.76-32 30.656-32h61.344c1.344 0 2.624 0.256 3.936 0.384C269.472 201.088 317.504 160 374.656 160z m0 64c-33.824 0-61.312 28.704-61.312 64s27.52 64 61.312 64c33.824 0 61.344-28.704 61.344-64s-27.52-64-61.344-64z',
    }),
  ],
);
