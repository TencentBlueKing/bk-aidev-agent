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

import { getArtifactPreviewStrategy } from './preview-strategy';

describe('preview-strategy', () => {
  it('html 应走 text_from_download 并用 iframe srcdoc 直渲染', () => {
    expect(getArtifactPreviewStrategy('html')).toEqual({
      load: 'text_from_download',
      renderer: 'html',
    });
    expect(getArtifactPreviewStrategy('htm')).toEqual({
      load: 'text_from_download',
      renderer: 'html',
    });
  });

  it('md / markdown 等价，均走 markdown 直渲染', () => {
    expect(getArtifactPreviewStrategy('md')).toEqual({
      load: 'text_from_download',
      renderer: 'markdown',
    });
    expect(getArtifactPreviewStrategy('markdown')).toEqual({
      load: 'text_from_download',
      renderer: 'markdown',
    });
  });

  it('纯文本类型走 txt 渲染器', () => {
    expect(getArtifactPreviewStrategy('txt')).toEqual({
      load: 'text_from_download',
      renderer: 'txt',
    });
    expect(getArtifactPreviewStrategy('rst')).toEqual({
      load: 'text_from_download',
      renderer: 'txt',
    });
  });

  it('源码与配置类型统一走 code 高亮渲染', () => {
    for (const type of ['py', 'ts', 'tsx', 'go', 'json', 'yaml', 'sql', 'Dockerfile', 'Makefile', '.gitignore']) {
      expect(getArtifactPreviewStrategy(type)).toEqual({
        load: 'text_from_download',
        renderer: 'code',
      });
    }
  });

  it('图片类型走 preview_url 直出 img', () => {
    for (const type of ['png', 'jpg', 'jpeg', 'svg']) {
      expect(getArtifactPreviewStrategy(type)).toEqual({
        load: 'preview_url',
        renderer: 'image',
      });
    }
  });

  it('二进制文档与未知类型统一走 preview_url iframe', () => {
    for (const type of ['pdf', 'docx', 'xlsx', 'pptx', 'csv', 'unknown-ext']) {
      expect(getArtifactPreviewStrategy(type)).toEqual({
        load: 'preview_url',
        renderer: 'urlIframe',
      });
    }
  });

  it('type 缺省时回退文件名推断', () => {
    expect(getArtifactPreviewStrategy(undefined, 'main.py')).toEqual({
      load: 'text_from_download',
      renderer: 'code',
    });
    expect(getArtifactPreviewStrategy('', '报告.PDF')).toEqual({
      load: 'preview_url',
      renderer: 'urlIframe',
    });
  });
});
