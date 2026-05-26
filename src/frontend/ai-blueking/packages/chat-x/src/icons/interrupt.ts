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
export const CheckCircleFillIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-check-circle-icon': true,
    },
  },
  [
    // 图标路径
    h('path', {
      d: 'M512 85.333333c235.52 0 426.666667 191.146667 426.666667 426.666667s-191.146667 426.666667-426.666667 426.666667S85.333333 747.52 85.333333 512 276.48 85.333333 512 85.333333m-42.666667 618.666667l298.666667-298.666667-60.16-60.16L469.333333 583.253333l-131.84-131.413333L277.333333 512l192 192z',
    }),
  ],
);

export const TimeIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-time-icon': true,
    },
  },
  [
    // 外圈路径
    h('path', {
      d: 'M512 70.4a441.6 441.6 0 1 0 0 883.2 441.6 441.6 0 0 0 0-883.2z m0 64a377.6 377.6 0 1 1 0 755.2 377.6 377.6 0 0 1 0-755.2z',
    }),
    // 时针与分针路径
    h('path', {
      d: 'M544 480V256a32 32 0 1 0-64 0v230.4c0 31.7952 25.8048 57.6 57.6 57.6H768a32 32 0 1 0 0-64h-224z',
    }),
  ],
);

export const CloseCircleFillIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-close-circle-icon': true,
    },
  },
  [
    // 图标路径
    h('path', {
      d: 'M85.333333 512C85.333333 276.352 276.352 85.333333 512 85.333333s426.666667 191.018667 426.666667 426.666667-191.018667 426.666667-426.666667 426.666667S85.333333 747.648 85.333333 512z m269.653334-96.661333l96.810666 96.810666-96.810666 96.810667c-16.661333 16.661333-16.384 43.84 0.277333 60.501333l0.512 0.512c16.64 16.64 42.88 16 59.541333-0.682666l96.810667-96.810667 96.832 96.810667c16.64 16.682667 42.88 17.344 59.541333 0.682666l0.512-0.512c16.64-16.64 16.938667-43.84 0.277334-60.501333l-96.810667-96.810667 96.810667-96.810666c16.661333-16.661333 16.384-43.861333-0.277334-60.522667l-0.490666-0.490667c-16.682667-16.661333-42.901333-16-59.562667 0.661334l-96.832 96.810666-96.810667-96.810666c-16.64-16.64-42.88-17.322667-59.541333-0.661334a109.44 109.44 0 0 1-0.512 0.490667c-16.64 16.661333-16.938667 43.861333-0.277333 60.522667z',
    }),
  ],
);

// 已撤销图标
export const RevokedIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-revoked-icon': true,
    },
  },
  [
    // 图标路径
    h('path', {
      d: 'M512 64a448.056889 448.056889 0 1 1-0.056889 896.056889A448.056889 448.056889 0 0 1 512 64zM448 256l-128 96.256L448.284444 448 448 384l128.113778 0.113778a128 128 0 0 1 0 255.886222h-224.142222v64h224.028444a192 192 0 1 0 0-384h-128V256z',
    }),
  ],
);
export const InfoIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-info-icon': true,
    },
  },
  [
    // 外圆环路径
    h('path', {
      d: 'M512 64C264 64 64 264 64 512s200 448 448 448 448-200 448-448S760 64 512 64zM512 896C299.2 896 128 724.8 128 512S299.2 128 512 128s384 171.2 384 384S724.8 896 512 896z',
    }),
    // "i" 的下半部分主体
    h('path', {
      d: 'M494.4 403.2c-28.8 6.4-56 20.8-76.8 41.6-24 22.4 1.6 44.8 16 27.2 9.6-12.8 24-22.4 40-28.8 11.2-1.6 17.6 1.6 19.2 9.6 1.6 14.4 0 27.2-4.8 41.6-4.8 19.2-14.4 51.2-25.6 94.4-22.4 76.8-33.6 124.8-30.4 140.8 3.2 17.6 12.8 32 28.8 41.6 17.6 8 38.4 9.6 57.6 4.8 30.4-6.4 57.6-22.4 80-44.8 25.6-25.6-3.2-43.2-17.6-28.8-9.6 12.8-24 22.4-40 25.6-14.4 3.2-22.4-3.2-25.6-16-1.6-14.4 1.6-28.8 6.4-41.6 40-136 57.6-212.8 52.8-232-3.2-14.4-12.8-27.2-25.6-33.6C532.8 398.4 512 398.4 494.4 403.2z',
    }),
    // "i" 的上半部分圆点
    h('path', { d: 'M608 304A48 48 0 0 1 560 352 48 48 0 0 1 512 304 48 48 0 0 1 608 304z' }),
  ],
);
