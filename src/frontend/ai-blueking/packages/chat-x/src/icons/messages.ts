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

import { commonSVGProps } from '../common/icon';

/**
 * 发送消息图标
 */
export const SendMessageIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-send-message-icon': true,
    },
  },
  [
    h('path', {
      d: 'M873.6 99.2L118.4 476.8c-28.8 16-28.8 44.8-6.4 60.8l182.4 112c16 6.4 28.8 6.4 44.8-6.4L736 288 390.4 672c-6.4 6.4-6.4 16-6.4 22.4v166.4c0 16 6.4 28.8 22.4 38.4s28.8 0 38.4-6.4l89.6-89.6 182.4 121.6c28.8 16 54.4 6.4 60.8-22.4L928 147.2c6.4-38.4-19.2-60.8-54.4-48z',
    }),
  ],
);
/**
 * 加载中消息图标
 */
export const LoadingMessageIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-loading-message-icon': true,
    },
  },
  [
    h('path', {
      d: 'M512 64c247.424 0 448 200.576 448 448s-200.576 448-448 448S64 759.424 64 512 264.576 64 512 64z m0 64C299.936 128 128 299.936 128 512s171.936 384 384 384 384-171.936 384-384S724.064 128 512 128z m0 192a192 192 0 1 1 0 384 192 192 0 0 1 0-384z',
    }),
  ],
);
/**
 * 思考图标
 */
export const ThinkingIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-thinking-icon': true,
    },
  },
  [
    h('path', {
      d: 'M528 96c61.856 0 112 50.144 112 112 0 0.376-0.002 0.751-0.006 1.126C774.73 260.666 870.4 391.16 870.4 544c0 22.55-2.082 44.612-6.066 66.007C883.94 630.144 896 657.663 896 688c0 61.856-50.144 112-112 112a112.7 112.7 0 0 1-19.49-1.69C699.754 862.65 610.519 902.4 512 902.4s-187.753-39.75-252.539-104.088A112.33 112.33 0 0 1 240 800c-61.856 0-112-50.144-112-112 0-30.337 12.061-57.856 31.65-78.025A361.172 361.172 0 0 1 153.6 544c0-164.845 111.29-303.696 262.836-345.518C421.232 141.079 469.35 96 528 96z m-91.48 176.633l-4.469 1.278C315.47 308.366 230.4 416.249 230.4 544c0 10.923 0.622 21.7 1.832 32.3l1.623-0.134L240 576c61.856 0 112 50.144 112 112 0 26.132-8.95 50.173-23.95 69.226C377.36 799.817 441.67 825.6 512 825.6c70.33 0 134.639-25.783 183.99-68.412C680.95 738.173 672 714.132 672 688c0-61.856 50.144-112 112-112 2.607 0 5.194 0.09 7.757 0.264A280.989 280.989 0 0 0 793.6 544c0-119.973-75.025-222.422-180.718-262.99C592.35 304.904 561.938 320 528 320c-37.782 0-71.195-18.708-91.48-47.367z',
    }),
  ],
);
/**
 * 折叠图标
 */

export const CollapsedIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-collapsed-icon': true,
    },
  },
  [
    h('path', {
      d: 'M373.15678637 997.95124768l-104.13241023-104.1324102 381.81883749-381.81883748-381.81883749-381.81883748 104.13241023-104.1324102 485.95124773 485.95124768z',
    }),
  ],
);
export const ErrorIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-error-icon': true,
    },
  },
  [
    h('path', {
      d: 'M512 64C264 64 64 264 64 512s200 448 448 448 448-200 448-448S760 64 512 64z m0 704c-27.2 0-48-20.8-48-48s20.8-48 48-48 48 20.8 48 48-20.8 48-48 48z m48-459.2L544 608c0 17.6-14.4 32-32 32s-32-14.4-32-32l-16-299.2V304c0-27.2 20.8-48 48-48s48 20.8 48 48v4.8z',
    }),
  ],
);
export const ContentLoadingIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-content-loading-icon': true,
    },
  },
  [
    h('path', {
      fillRule: 'evenodd',
      d: 'M621.2037824 0C1168.33181568 0 1148.103769856 748.7917952 621.2037824 682.56061184 343.25692288000005 647.62276864 136.18899583999996 761.4358976 0 1024 49.3838336 341.33333376 256.45176064 0 621.2037824 0Z',
    }),
  ],
);

export const ArrowDownIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-arrow-down-icon': true,
    },
  },
  [
    h('path', {
      d: 'M810.666628 571.545259l-85.526922-83.200123-171.019311 166.469312-0.035467-554.735928H440.048409l0.0672 554.735928-171.121977-166.469312L183.466709 571.545259l313.59996 305.066494L810.666628 571.545259z',
    }),
  ],
);
