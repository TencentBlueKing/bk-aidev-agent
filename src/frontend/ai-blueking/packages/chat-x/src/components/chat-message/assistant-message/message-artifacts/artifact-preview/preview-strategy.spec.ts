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
import { describe, expect, it } from 'vitest';

import { AIFileType } from '../../../../../ag-ui/types/file';
import { getArtifactPreviewStrategy } from './preview-strategy';

describe('preview-strategy', () => {
  it('Html/Txt/Markdown/Json 应走 text_from_download 且 renderer 对应类型', () => {
    expect(getArtifactPreviewStrategy(AIFileType.Html)).toEqual({
      load: 'text_from_download',
      renderer: 'html',
    });
    expect(getArtifactPreviewStrategy(AIFileType.Txt)).toEqual({
      load: 'text_from_download',
      renderer: 'txt',
    });
    expect(getArtifactPreviewStrategy(AIFileType.Markdown)).toEqual({
      load: 'text_from_download',
      renderer: 'markdown',
    });
    // Json 与 Txt 相同：纯文本预览
    expect(getArtifactPreviewStrategy(AIFileType.Json)).toEqual({
      load: 'text_from_download',
      renderer: 'txt',
    });
  });

  it('Pdf/Jpg 应走 preview_url_iframe', () => {
    expect(getArtifactPreviewStrategy(AIFileType.Pdf)).toEqual({
      load: 'preview_url_iframe',
      renderer: 'urlIframe',
    });
    expect(getArtifactPreviewStrategy(AIFileType.Jpg)).toEqual({
      load: 'preview_url_iframe',
      renderer: 'urlIframe',
    });
  });

  it('Md 应走 markdown 直渲染', () => {
    expect(getArtifactPreviewStrategy(AIFileType.Md)).toEqual({
      load: 'text_from_download',
      renderer: 'markdown',
    });
  });
});
