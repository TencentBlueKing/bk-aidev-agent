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

export const ZoomInIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-zoom-in-icon' }, [
  h('path', {
    d: 'M637.02 482.06H546.3V391.34c0-17.67-14.33-32-32-32s-32 14.33-32 32v90.72H391.58c-17.67 0-32 14.33-32 32s14.33 32 32 32h90.72v90.72c0 17.67 14.33 32 32 32s32-14.33 32-32v-90.72h90.72c17.67 0 32-14.33 32-32s-14.33-32-32-32z',
  }),
  h('path', {
    d: 'M514.3 195.78c-175.72 0-318.28 142.56-318.28 318.28S338.58 832.34 514.3 832.34s318.28-142.56 318.28-318.28-142.56-318.28-318.28-318.28z m0 572.56c-140.28 0-254.28-114-254.28-254.28s114-254.28 254.28-254.28 254.28 114 254.28 254.28-114 254.28-254.28 254.28z',
  }),
]);

export const ZoomOutIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-zoom-out-icon' }, [
  h('path', {
    d: 'M637.02 482.06H391.58c-17.67 0-32 14.33-32 32s14.33 32 32 32h245.44c17.67 0 32-14.33 32-32s-14.33-32-32-32z',
  }),
  h('path', {
    d: 'M514.3 195.78c-175.72 0-318.28 142.56-318.28 318.28S338.58 832.34 514.3 832.34s318.28-142.56 318.28-318.28-142.56-318.28-318.28-318.28z m0 572.56c-140.28 0-254.28-114-254.28-254.28s114-254.28 254.28-254.28 254.28 114 254.28 254.28-114 254.28-254.28 254.28z',
  }),
]);

export const RotateIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-rotate-icon' }, [
  h('path', {
    d: 'M817.76 328.31H402.28c-59.68 0-108.24 48.55-108.24 108.24v415.44c0 59.68 48.55 108.24 108.24 108.24h415.47c59.65 0 108.2-48.55 108.2-108.24V436.55c0-59.69-48.55-108.24-108.19-108.24z m30.39 523.68c0 16.79-13.64 30.43-30.39 30.43H402.28c-16.79 0-30.43-13.64-30.43-30.43V436.55c0-16.79 13.64-30.43 30.43-30.43h415.47c16.75 0 30.39 13.64 30.39 30.43v415.44z',
  }),
  h('path', {
    d: 'M248.91 368.43c-18.27-11.32-42.25-5.66-53.57 12.61l-18.16 29.33c-0.87-8.47-1.33-17.1-1.33-25.76 0-134 109.04-243.03 243.07-243.03 44.64 0 88.29 12.2 126.17 35.29 18.39 11.13 42.32 5.32 53.49-12.99 11.17-18.35 5.36-42.28-12.99-53.49-50.11-30.51-107.74-46.62-166.67-46.62-176.93 0-320.88 143.91-320.88 320.84 0 48.14 10.41 94.41 30.89 137.53 6.12 12.84 18.77 21.35 32.98 22.11 0.72 0.04 1.44 0.08 2.17 0.08a38.92 38.92 0 0 0 33.09-18.43L261.52 422c11.29-18.28 5.66-42.25-12.61-53.57z',
  }),
]);

export const FitScreenIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-fit-screen-icon' }, [
  h('path', {
    d: 'M160 160h240v64H224v176H160V160zM160 624h64v176h176v64H160V624zM624 160h240v240h-64V224H624V160zM800 624h64v240H624v-64h176V624z',
  }),
]);

export const DownloadIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-download-icon' }, [
  h('path', {
    d: 'M544 654.4V192h-64v462.4l-147.2-147.2-45.2 45.2L512 776.8l224.4-224.4-45.2-45.2L544 654.4zM832 832H192v64h640v-64z',
  }),
]);

export const PreviewCloseIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-close-icon' }, [
  h('path', {
    d: 'M557.3 512l214.9-214.9c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L512 466.7 297.1 251.8c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L466.7 512 251.8 726.9c-12.5 12.5-12.5 32.8 0 45.3 6.2 6.2 14.4 9.4 22.6 9.4s16.4-3.1 22.6-9.4L512 557.3l214.9 214.9c6.2 6.2 14.4 9.4 22.6 9.4s16.4-3.1 22.6-9.4c12.5-12.5 12.5-32.8 0-45.3L557.3 512z',
  }),
]);

export const ArrowLeftIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-arrow-left-icon' }, [
  h('path', {
    d: 'M672 165.2L333.2 504c-5.6 5.6-5.6 14.8 0 20.4L672 863.2',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '64',
    'stroke-linecap': 'round',
  }),
]);

export const ArrowRightPreviewIcon = h(
  'svg',
  { ...commonSVGProps, class: 'ai-common-icon ai-arrow-right-preview-icon' },
  [
    h('path', {
      d: 'M352 165.2L690.8 504c5.6 5.6 5.6 14.8 0 20.4L352 863.2',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '64',
      'stroke-linecap': 'round',
    }),
  ],
);

export const ReloadIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-reload-icon' }, [
  h('path', {
    d: 'M889.6 398.4c-16-35.2-35.2-65.6-60.8-92.8-24-27.2-52.8-48-84.8-65.6-32-17.6-67.2-28.8-102.4-35.2-35.2-6.4-72-8-108.8-3.2V108.8l-256 192 256 192V400c27.2-4.8 54.4-4.8 81.6-1.6 27.2 4.8 52.8 14.4 76.8 27.2 24 12.8 46.4 30.4 64 51.2 17.6 20.8 32 44.8 41.6 70.4 9.6 25.6 14.4 52.8 14.4 81.6s-4.8 56-14.4 81.6c-9.6 25.6-24 49.6-41.6 70.4-17.6 20.8-40 38.4-64 51.2-24 12.8-49.6 22.4-76.8 27.2-27.2 4.8-54.4 4.8-81.6 1.6-27.2-4.8-52.8-14.4-76.8-27.2-24-12.8-46.4-30.4-64-51.2-17.6-20.8-32-44.8-41.6-70.4-9.6-25.6-14.4-52.8-14.4-81.6h-64c0 38.4 6.4 75.2 19.2 110.4 12.8 35.2 30.4 67.2 52.8 96 22.4 28.8 49.6 52.8 80 72 30.4 19.2 64 33.6 99.2 43.2 35.2 9.6 72 12.8 108.8 11.2 36.8-1.6 72-9.6 105.6-22.4 33.6-12.8 64-30.4 92.8-52.8 28.8-22.4 52.8-49.6 72-80 19.2-30.4 33.6-64 43.2-99.2 9.6-35.2 12.8-72 11.2-108.8-1.6-36.8-9.6-72-22.4-105.6z',
  }),
]);

export const ImageBrokenIcon = h(
  'svg',
  { ...commonSVGProps, viewBox: '0 0 200 180', class: 'ai-common-icon ai-image-broken-icon' },
  [
    h('g', { fill: 'none' }, [
      h('rect', { x: '30', y: '20', width: '100', height: '86', rx: '4', fill: '#C4C6CC', opacity: '0.6' }),
      h('circle', { cx: '55', cy: '45', r: '8', fill: '#979BA5', opacity: '0.5' }),
      h('path', { d: 'M30 80l25-20 20 15 25-25 30 30v26H30V80z', fill: '#979BA5', opacity: '0.5' }),
      h('circle', { cx: '120', cy: '80', r: '36', fill: '#FFE8C3', stroke: '#FF9C01', 'stroke-width': '3' }),
      h(
        'text',
        {
          x: '120',
          y: '88',
          'text-anchor': 'middle',
          'font-size': '32',
          'font-weight': 'bold',
          fill: '#FF9C01',
        },
        '!',
      ),
    ]),
  ],
);

export const ImageSizeIcon = h('svg', { ...commonSVGProps, class: 'ai-common-icon ai-image-size-icon' }, [
  h('path', {
    d: 'M864 160H160c-35.2 0-64 28.8-64 64v576c0 35.2 28.8 64 64 64h704c35.2 0 64-28.8 64-64V224c0-35.2-28.8-64-64-64z m0 640H160V224h704v576z',
  }),
]);
