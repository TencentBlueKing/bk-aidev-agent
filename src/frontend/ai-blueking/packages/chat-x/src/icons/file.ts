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

// 文件产物侧栏 Tab 图标：设计稿节点 947-13413，保留原始 16×16 path；fill 走 currentColor 以继承 Tab 选中/默认色
export const ArtifactTabIcon = h(
  'svg',
  {
    ...commonSVGProps,
    viewBox: '0 0 16 16',
    class: {
      [commonSVGProps.class]: true,
      'ai-file-artifact-tab-icon': true,
    },
  },
  [
    h('path', {
      'fill-rule': 'evenodd',
      'clip-rule': 'evenodd',
      d: 'M3.5 14C3.22386 14 3 13.8082 3 13.5715L3 5.04938L6.71864 2L12.5 2C12.7761 2 13 2.192 13 2.42854L13 13.5715C13 13.8082 12.7761 14 12.5 14L3.5 14ZM3.90909 13.0769L12.0909 13.0769L12.0909 2.92308L7.77273 2.92308L7.77273 5.03069C7.77273 5.52292 7.32409 5.92308 6.77273 5.92308L3.90909 5.92308L3.90909 13.0769ZM4.50727 5L6.77273 5C6.81523 5 6.84568 4.98985 6.86364 4.98085L6.86363 3.06777L4.50727 5ZM5 8.5L5 7.5L11 7.5L11 8.5L5 8.5ZM7 10L7 9L11 9L11 10L7 10ZM5.5 12L5.5 11L11 11L11 12L5.5 12Z',
    }),
  ],
);

export const DownloadFileIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-file-download-icon': true,
    },
  },
  [
    h('path', {
      d: 'M192 640v192h640v-192h64v224c0 17.6-14.4 32-32 32h-704a32.064 32.064 0 0 1-32-32V640h64z m352-512v452.8l104-102.4 44.8 44.8L556.8 659.2 512 704l-44.8-44.8-136-136 44.8-44.8 104 102.4V128h64z',
    }),
  ],
);
