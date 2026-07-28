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
import { onBeforeUnmount, shallowRef } from 'vue';

import { getArtifactPreviewStrategy } from './preview-strategy';

import type { AIFileInfo, ArtifactUrlResult } from '../../../../../ag-ui/types/file';
import type { ArtifactPreviewRendererKind } from './preview-strategy';

export type ArtifactPreviewPayload = {
  content: string;
  previewUrl: string;
  renderer: ArtifactPreviewRendererKind;
  status: ArtifactPreviewStatus;
};

export type ArtifactPreviewStatus = 'empty' | 'error' | 'idle' | 'loading' | 'ready';

export const useArtifactPreviewLoader = (options: {
  canResolve: () => boolean;
  getFile: () => AIFileInfo | undefined;
  resolveUrls: (file: AIFileInfo) => Promise<ArtifactUrlResult>;
}) => {
  const status = shallowRef<ArtifactPreviewStatus>('idle');
  const content = shallowRef('');
  const previewUrl = shallowRef('');
  const renderer = shallowRef<ArtifactPreviewRendererKind>('urlIframe');

  let abortController: AbortController | undefined;
  let loadSeq = 0;

  const resetPayload = () => {
    content.value = '';
    previewUrl.value = '';
  };

  const load = async () => {
    const seq = ++loadSeq;
    abortController?.abort();
    abortController = undefined;

    const file = options.getFile();
    if (!file || !options.canResolve()) {
      status.value = 'empty';
      resetPayload();
      return;
    }

    status.value = 'loading';
    resetPayload();

    const strategy = getArtifactPreviewStrategy(file.type);
    renderer.value = strategy.renderer;

    try {
      const urls = await options.resolveUrls(file);
      if (seq !== loadSeq) {
        return;
      }

      if (strategy.load === 'text_from_download') {
        if (!urls.download_url) {
          status.value = 'empty';
          return;
        }

        const controller = new AbortController();
        abortController = controller;
        const response = await fetch(urls.download_url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const text = await response.text();
        if (controller.signal.aborted || seq !== loadSeq) {
          return;
        }
        content.value = text;
        status.value = 'ready';
        return;
      }

      if (!urls.preview_url) {
        status.value = 'empty';
        return;
      }
      previewUrl.value = urls.preview_url;
      status.value = 'ready';
    } catch {
      if (seq !== loadSeq || abortController?.signal.aborted) {
        return;
      }
      status.value = 'error';
    }
  };

  const dispose = () => {
    loadSeq += 1;
    abortController?.abort();
  };

  onBeforeUnmount(dispose);

  return { content, dispose, load, previewUrl, renderer, status };
};
