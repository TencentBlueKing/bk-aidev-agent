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

export const CloseIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-close-icon': true,
    },
  },
  [
    h('path', {
      d: 'M757.09004048 196.21090938L512 446.01421987l-245.09004048-249.80331049-70.69905014 70.69905014 249.80331049 245.09004048-249.80331049 245.09004048 70.69905014 70.69905014 245.09004048-249.80331049 245.09004048 249.80331049 70.69905014-70.69905014-249.80331049-245.09004048 249.80331049-245.09004048z',
    }),
  ],
);

export const MoreIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-more-icon': true,
    },
  },
  [
    h('path', {
      fillRule: 'evenodd',
      d: 'M512.5492576 319.99489568C547.8894304 319.70050624 576.292128 290.79913056 575.9977312 255.44678368 575.6905376 220.0944368 546.8014496 191.7050432 511.4484768 191.99943264 476.3130976 192.29382208 448 220.87520896 448 255.99716352L448 256.54754464C448.3071936 291.88709184 477.2090816 320.2892864 512.5492576 319.99489568M511.4484768 431.9994336C476.3130976 432.2938208 448 460.8752096 448 495.9971648L448 496.5475456C448.3071936 531.8870912 477.2090816 560.2892864 512.5492576 559.994896 547.8894304 559.7005056 576.292128 530.7991296 575.9977312 495.446784 575.6905376 460.0944352 546.8014496 431.7050432 511.4484768 431.9994336M511.4484768 671.9994336C476.3130976 672.2938208 448 700.8752096 448 735.9971648L448 736.5475456C448.3071936 771.8870912 477.2090816 800.2892864 512.5492576 799.994896 547.8894304 799.7005056 576.292128 770.7991296 575.9977312 735.446784 575.6905376 700.0944352 546.8014496 671.7050432 511.4484768 671.9994336',
    }),
  ],
);
export const AgentIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-agent-icon': true,
    },
  },
  [
    h('path', {
      // 原本是固定色 #96A2B9，这里统一为 currentColor，便于主题控制
      d: 'M512 96c-16.123 0-71.894 216.944-144 287.93-72.106 70.985-272 111.597-272 128 0 16.402 195.757 35.541 272 112 76.243 76.458 127.616 304 144 304s62.134-220.233 144-304c81.866-83.768 272-95.31 272-112 0-16.69-200.746-56.427-272-128C584.746 312.356 528.123 96 512 96z',
    }),
  ],
);
export const MoreAgentIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-more-agent-icon': true,
    },
  },
  [
    h('path', {
      d: 'M176 560H416a48 48 0 0 1 48 48v240a48 48 0 0 1-48 48H176a48 48 0 0 1-48-48V608a48 48 0 0 1 48-48z m0-432H416a48 48 0 0 1 48 48V416a48 48 0 0 1-48 48H176A48 48 0 0 1 128 416V176A48 48 0 0 1 176 128zM608 560h240a48 48 0 0 1 48 48v240a48 48 0 0 1-48 48H608a48 48 0 0 1-48-48V608a48 48 0 0 1 48-48zM848 128H608a51.648 51.648 0 0 0-48 48V416a51.648 51.648 0 0 0 48 48h240A51.712 51.712 0 0 0 896 416V176a51.712 51.712 0 0 0-48-48z m0 264a22.72 22.72 0 0 1-24 24h-192a22.72 22.72 0 0 1-24-24v-192a22.72 22.72 0 0 1 24-24h192a22.72 22.72 0 0 1 24 24v192z',
    }),
  ],
);
