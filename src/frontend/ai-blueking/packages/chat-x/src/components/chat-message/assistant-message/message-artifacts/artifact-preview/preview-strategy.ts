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
import { type AIFileKind, resolveFileKind } from '../../../../../utils/file-type';

export type ArtifactPreviewLoadStrategy = 'preview_url' | 'text_from_download';

export type ArtifactPreviewRendererKind = 'code' | 'html' | 'image' | 'markdown' | 'txt' | 'urlIframe';

export type ArtifactPreviewStrategy = {
  load: ArtifactPreviewLoadStrategy;
  renderer: ArtifactPreviewRendererKind;
};

/** 文件分类 → 预览策略；前端可解析的走下载取文本，其余交给后端 preview_url */
const KIND_STRATEGY_MAP: Record<AIFileKind, ArtifactPreviewStrategy> = {
  binary: { load: 'preview_url', renderer: 'urlIframe' },
  code: { load: 'text_from_download', renderer: 'code' },
  html: { load: 'text_from_download', renderer: 'html' },
  image: { load: 'preview_url', renderer: 'image' },
  markdown: { load: 'text_from_download', renderer: 'markdown' },
  text: { load: 'text_from_download', renderer: 'txt' },
};

/** 按文件类型解析预览加载策略与渲染器；未登记的类型默认 preview_url iframe */
export const getArtifactPreviewStrategy = (type?: string, name?: string): ArtifactPreviewStrategy =>
  KIND_STRATEGY_MAP[resolveFileKind(type, name)];
