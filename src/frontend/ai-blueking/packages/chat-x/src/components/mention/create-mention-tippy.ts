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

import { EDITOR_MENU_Z_INDEX } from '../../common';
import MentionPopover from './mention-popover.vue';

import type { Instance } from 'tippy.js';

const SHOW_DELAY_MS = 300;

/**
 * 生成「类型：名称 + 描述」气泡的 v-tippy 配置。
 *
 * 用指令而不是 `<Tippy>` 组件包裹：标签渲染在 contenteditable 内部，
 * 多包一层元素会干扰编辑器对 void 节点的识别与 DOM 比对。
 * 定位、边界回推与箭头偏移交给 tippy，设计稿里靠边时的表现即来自于此。
 */
export const createMentionTippy = (payload: { description?: string; title: string }) => ({
  content: h(MentionPopover, { title: payload.title, description: payload.description }),
  appendTo: () => document.body,
  arrow: true,
  delay: [SHOW_DELAY_MS, 0] as [number, number],
  // hideOnClick 同时管着「点标签开合」与「点外部关闭」两条路径，置 true 会让再次点击标签把气泡收起，
  // 因此这里关掉它，再用 onClickOutside 单独补回外部点击关闭 —— 该钩子不受 hideOnClick 影响。
  hideOnClick: false,
  onClickOutside: (instance: Instance) => instance.hide(),
  interactive: false,
  offset: [0, 8] as [number, number],
  placement: 'top' as const,
  theme: 'light ai-mention-popover-theme',
  // 除 hover 外点击同样唤出：触屏没有 hover 态，且鼠标下点击时气泡不该消失。
  // tippy 仅在「气泡本就由点击唤出」时才把点击当作开合切换，因此 hover 已展示的气泡不会被点掉。
  trigger: 'mouseenter focus click',
  zIndex: EDITOR_MENU_Z_INDEX,
});
