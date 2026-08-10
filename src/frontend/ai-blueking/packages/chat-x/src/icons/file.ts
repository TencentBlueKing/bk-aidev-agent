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

// 文件产物侧栏 Tab 图标：单色文档轮廓，fill 走 currentColor 以继承 Tab 选中/默认色
export const ArtifactTabIcon = h(
  'svg',
  {
    ...commonSVGProps,
    class: {
      [commonSVGProps.class]: true,
      'ai-file-artifact-tab-icon': true,
    },
  },
  [
    h('path', {
      d: 'M616.768 64a32 32 0 0 1 22.656 9.408l215.168 215.168a32.192 32.192 0 0 1 9.408 22.72V928a32 32 0 0 1-32 32H192a32 32 0 0 1-32-32v-832A32 32 0 0 1 192 64h424.768z m39.232 640h-288a16 16 0 0 0-16 16v32c0 8.832 7.168 16 16 16h288a16 16 0 0 0 16-16v-32a16 16 0 0 0-16-16z m-64-128h-224a16 16 0 0 0-16 16v32c0 8.832 7.168 16 16 16h224a16 16 0 0 0 16-16v-32A16 16 0 0 0 592 576z m10.016-438.208v188.16h188.16l-188.16-188.16z',
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
