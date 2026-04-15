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
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Vue2 构建产物的 CSS 后处理
 *
 * 由于 Vue2 构建会将 bkui-vue 等依赖打包进产物，
 * 部分 CSS 类名可能需要调整以适配 Vue2 宿主环境中已有的样式约定。
 */

/**
 * bk-magic-vue (Vue2 版组件库) 样式兼容补丁
 *
 * 1. .bk-button-text color 覆盖问题
 *    bk-magic-vue 的 .bk-button-text { color: #63656e } 是通用规则，
 *    会覆盖 bkui-vue 中 .bk-button.bk-button-primary 等特定按钮类型设置的 color。
 *    因为 bkui-vue 的 Button 组件内部渲染了 <span class="bk-button-text"> 子元素，
 *    该子元素直接命中 bk-magic-vue 的 .bk-button-text 规则，导致颜色错误。
 *    解决：为 .bk-button-text 在各按钮主题/状态下添加 color: inherit，利用更高特异性确保覆盖。
 *
 * 2. .bk-form-content margin-left 覆盖问题
 *    bk-magic-vue 的 .bk-form .bk-form-content { margin-left: 120px } 用于 label + content 的水平布局，
 *    但 bkui-vue 的 Form 组件不一定有 label，这个 margin 会导致内容偏移。
 *    解决：在组件内重置 margin-left 为 0。
 */
const bkMagicVueCompatPatches = `
/* ===== bk-magic-vue compatibility patches ===== */
/* Fix: .bk-button-text color override by bk-magic-vue's generic rule */
.bk-button.bk-button-primary .bk-button-text{color:inherit}
.bk-button.bk-button-danger .bk-button-text{color:inherit}
.bk-button.bk-button-success .bk-button-text{color:inherit}
.bk-button.bk-button-warning .bk-button-text{color:inherit}
.bk-button.is-disabled .bk-button-text{color:inherit}
.bk-button.is-loading .bk-button-text{color:inherit}
.bk-button.bk-button-primary.is-outline .bk-button-text{color:inherit}
.bk-button.bk-button-danger.is-outline .bk-button-text{color:inherit}
.bk-button.bk-button-success.is-outline .bk-button-text{color:inherit}
.bk-button.bk-button-warning.is-outline .bk-button-text{color:inherit}
/* Fix: .bk-form-content margin-left override by bk-magic-vue's form layout */
/* bk-magic-vue 的 .bk-form .bk-form-content 特异性为 (0,2,0)，需更高特异性覆盖 */
.bk-form .bk-form-item .bk-form-content{margin-left:0}
`;

export default () => {
  const vue2StylePath = path.join(__dirname, '../dist/vue2/style.css');
  if (!fs.existsSync(vue2StylePath)) {
    return;
  }

  let css = fs.readFileSync(vue2StylePath, 'utf-8');

  // bkui-vue 的 Popover/Popper 在 Vue2 宿主中使用 bk-popper 主题类
  css = css.replaceAll('ai-blueking-popper', 'bk-popper');

  // 追加 bk-magic-vue 样式兼容补丁
  css += bkMagicVueCompatPatches;

  fs.writeFileSync(vue2StylePath, css);
};
