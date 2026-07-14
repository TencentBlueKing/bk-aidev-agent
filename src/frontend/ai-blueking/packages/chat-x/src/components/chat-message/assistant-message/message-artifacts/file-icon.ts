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
import { cloneVNode } from 'vue';

import { AIFileType } from '../../../../ag-ui/types/file';
import { HtmlIcon, JpgIcon, JsonIcon, MarkdownIcon, PdfIcon, TxtIcon } from '../../../../icons/file';

/** 文件类型 → 图标映射；未命中类型兜底用文本图标 */
export const FILE_ICON_MAP = {
  [AIFileType.Html]: HtmlIcon,
  [AIFileType.Jpg]: JpgIcon,
  [AIFileType.Json]: JsonIcon,
  [AIFileType.Markdown]: MarkdownIcon,
  [AIFileType.Pdf]: PdfIcon,
  [AIFileType.Txt]: TxtIcon,
} as const;

/** 图标为共享 VNode，克隆后再渲染，避免同类型多处复用同一实例 */
export const getFileIcon = (type: AIFileType) => cloneVNode(FILE_ICON_MAP[type] ?? TxtIcon);
