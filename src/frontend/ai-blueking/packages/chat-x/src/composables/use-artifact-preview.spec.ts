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

import { defineComponent, h } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { AIFileType } from '../ag-ui/types/file';
import {
  buildArtifactId,
  useArtifactPreviewConsumer,
  useArtifactPreviewProvider,
} from './use-artifact-preview';

import type { AIFileInfo, OnArtifactClick } from '../ag-ui/types/file';

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: 'file.pdf',
  outputId: 'output-1',
  size: 1024,
  type: AIFileType.Pdf,
  ...overrides,
});

describe('use-artifact-preview', () => {
  describe('buildArtifactId', () => {
    it('应该按 messageUid#index#outputId 组合唯一 id', () => {
      expect(buildArtifactId('m1', 2, 'o3')).toBe('m1#2#o3');
    });
  });

  describe('Provider / Consumer', () => {
    const setup = (options: {
      getOnArtifactClick?: () => OnArtifactClick | undefined;
      onOpen?: ReturnType<typeof vi.fn>;
    } = {}) => {
      const onOpen = options.onOpen ?? vi.fn();
      let providerApi: ReturnType<typeof useArtifactPreviewProvider> | undefined;
      let consumerCtx: ReturnType<typeof useArtifactPreviewConsumer>;

      const Child = defineComponent({
        setup() {
          consumerCtx = useArtifactPreviewConsumer();
          return () => h('div');
        },
      });
      const Parent = defineComponent({
        setup() {
          providerApi = useArtifactPreviewProvider({
            getOnArtifactClick: options.getOnArtifactClick,
            onOpen,
          });
          return () => h(Child);
        },
      });
      const wrapper = mount(Parent);
      return { consumerCtx, onOpen, providerApi, wrapper };
    };

    it('openPreview 应命中文件并触发 onOpen', () => {
      const { consumerCtx, onOpen, providerApi } = setup();
      const file = createFile({ outputId: 'o9' });

      consumerCtx?.openPreview({ file, index: 1, messageUid: 'msg-a' });

      const expectedId = buildArtifactId('msg-a', 1, 'o9');
      expect(providerApi?.activeArtifactId.value).toBe(expectedId);
      expect(onOpen).toHaveBeenCalledWith(expectedId);
    });

    it('setActiveArtifactId 应直接更新命中态', () => {
      const { consumerCtx, providerApi } = setup();

      consumerCtx?.setActiveArtifactId('custom-id');

      expect(providerApi?.activeArtifactId.value).toBe('custom-id');
    });

    it('未传 onArtifactClick 时 canResolveArtifactUrl 应为 false', () => {
      const { consumerCtx } = setup();

      expect(consumerCtx?.canResolveArtifactUrl.value).toBe(false);
    });

    it('resolveArtifactUrls 应按 outputId 缓存结果且不重复请求', async () => {
      const onArtifactClick = vi.fn().mockResolvedValue({
        download_url: 'https://example.com/d',
        preview_url: 'https://example.com/p',
      });
      const { consumerCtx } = setup({ getOnArtifactClick: () => onArtifactClick });
      const file = createFile({ outputId: 'cache-1' });

      const first = await consumerCtx!.resolveArtifactUrls(file);
      const second = await consumerCtx!.resolveArtifactUrls(file);

      expect(first).toEqual({
        download_url: 'https://example.com/d',
        preview_url: 'https://example.com/p',
      });
      expect(second).toEqual(first);
      expect(onArtifactClick).toHaveBeenCalledTimes(1);
    });

    it('并发 resolveArtifactUrls 应复用同一进行中请求', async () => {
      let resolveClick: (value: { download_url: string }) => void = () => {};
      const onArtifactClick = vi.fn(
        () =>
          new Promise<{ download_url: string }>(resolve => {
            resolveClick = resolve;
          }),
      );
      const { consumerCtx } = setup({ getOnArtifactClick: () => onArtifactClick });
      const file = createFile({ outputId: 'inflight-1' });

      const p1 = consumerCtx!.resolveArtifactUrls(file);
      const p2 = consumerCtx!.resolveArtifactUrls(file);
      resolveClick({ download_url: 'https://example.com/d' });
      const [r1, r2] = await Promise.all([p1, p2]);

      expect(r1).toEqual({ download_url: 'https://example.com/d' });
      expect(r2).toEqual(r1);
      expect(onArtifactClick).toHaveBeenCalledTimes(1);
    });
  });
});
