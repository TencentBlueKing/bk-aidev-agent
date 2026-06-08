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

export const FullScreenIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-full-screen-icon': true,
    },
  },
  [
    h('path', {
      d: 'M85.333333 938.666667V768H0v213.333333c0 23.466667 19.2 42.666667 42.666667 42.666667H256v-85.333333H85.333333zM85.333333 85.333333h170.666667V0H42.666667C19.2 0 0 19.2 0 42.666667V256h85.333333V85.333333z m853.333334 853.333334H768v85.333333h213.333333c23.466667 0 42.666667-19.2 42.666667-42.666667V768h-85.333333v170.666667z m42.666666-938.666667H768v85.333333h170.666667v170.666667h85.333333V42.666667c0-23.466667-19.2-42.666667-42.666667-42.666667z',
    }),
  ],
);

export const UnFullScreenIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-un-full-screen-icon': true,
    },
  },
  [
    h('path', {
      d: 'M170.666667 853.333333v170.666667h85.333333V810.666667c0-23.466667-19.2-42.666667-42.666667-42.666667H0v85.333333h170.666667z m0-682.666666H0v85.333333h213.333333c23.466667 0 42.666667-19.2 42.666667-42.666667V0H170.666667v170.666667z m682.666666 682.666666h170.666667V768H810.666667c-23.466667 0-42.666667 19.2-42.666667 42.666667V1024h85.333333v-170.666667z m-42.666666-597.333333H1024V170.666667h-170.666667V0H768v213.333333c0 23.466667 19.2 42.666667 42.666667 42.666667z',
    }),
  ],
);
