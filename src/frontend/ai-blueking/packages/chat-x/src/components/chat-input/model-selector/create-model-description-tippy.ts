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
import { EDITOR_MENU_Z_INDEX } from '../../../common';

import type { AITippyProps } from '../../../types';
import type { GetReferenceClientRect, Props } from 'tippy.js';

/** 移入后多久展示描述 tip。manual 触发下 tippy 的 delay 不生效，由调用方计时 */
export const MODEL_DESCRIPTION_TIP_DELAY_MS = 300;

/**
 * 模型描述 tip 的配置。
 * 面板只创建一个实例，并用 getReferenceClientRect 跟着当前选项定位，
 * 避免列表每一项各挂一个 tippy。
 * shared 只接收外层 common tippy 的 appendTo / placement / zIndex，其余字段保持描述气泡自己的行为。
 */
export const createModelDescriptionTippy = (
  getReferenceClientRect: GetReferenceClientRect,
  shared?: AITippyProps,
): Partial<Props> => ({
  allowHTML: false,
  appendTo: shared?.appendTo ?? (() => document.body),
  arrow: true,
  content: '',
  delay: [0, 0],
  getReferenceClientRect,
  interactive: false,
  offset: [0, 8],
  placement: shared?.placement ?? 'auto',
  // 定位用视口坐标，fixed 才不会被列表的 overflow 裁切，也不会算错滚动偏移
  popperOptions: { strategy: 'fixed' },
  theme: 'ai-chat-box',
  trigger: 'manual',
  zIndex: shared?.zIndex ?? EDITOR_MENU_Z_INDEX,
});
