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

import { ref } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AIFileType } from '../../../../ag-ui/types/file';
import { ARTIFACT_PREVIEW_TOKEN } from '../../../../composables/use-artifact-preview';
import ArtifactFileCard from './artifact-file-card.vue';

import type { AIFileInfo } from '../../../../ag-ui/types/file';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock vue-tippy directive
vi.mock('vue-tippy', () => ({
  directive: {
    mounted: vi.fn(),
    unmounted: vi.fn(),
  },
}));

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: '运维操作指引文档.doc',
  outputId: 'output-1',
  previewUrl: 'https://example.com/preview',
  size: 1024,
  type: AIFileType.Pdf,
  url: 'https://example.com/download',
  ...overrides,
});

describe('ArtifactFileCard', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该渲染文件名与图标', () => {
      wrapper = mount(ArtifactFileCard, { props: { file: createFile() } });

      expect(wrapper.find('.ai-artifact-file-card').exists()).toBe(true);
      expect(wrapper.find('.ai-artifact-file-card-name').text()).toBe('运维操作指引文档.doc');
      expect(wrapper.find('.ai-artifact-file-card-icon svg').exists()).toBe(true);
    });

    it('有 url 时应该展示下载按钮', () => {
      wrapper = mount(ArtifactFileCard, { props: { file: createFile() } });

      expect(wrapper.find('.ai-artifact-file-card-download').exists()).toBe(true);
    });

    it('无 url 时应该隐藏下载按钮', () => {
      wrapper = mount(ArtifactFileCard, { props: { file: createFile({ url: '' }) } });

      expect(wrapper.find('.ai-artifact-file-card-download').exists()).toBe(false);
    });

    it('传入 onPreview 时卡片应带可点击态', () => {
      wrapper = mount(ArtifactFileCard, { props: { file: createFile(), onPreview: vi.fn() } });

      expect(wrapper.find('.ai-artifact-file-card').classes()).toContain('is-clickable');
    });

    it('无 onPreview 且无侧栏预览上下文时卡片不可点击', () => {
      wrapper = mount(ArtifactFileCard, { props: { file: createFile() } });

      expect(wrapper.find('.ai-artifact-file-card').classes()).not.toContain('is-clickable');
    });

    it('存在侧栏预览上下文时卡片应带可点击态', () => {
      const artifactPreview = { activeArtifactId: ref(''), openPreview: vi.fn(), setActiveArtifactId: vi.fn() };
      wrapper = mount(ArtifactFileCard, {
        global: { provide: { [ARTIFACT_PREVIEW_TOKEN]: artifactPreview } },
        props: { file: createFile() },
      });

      expect(wrapper.find('.ai-artifact-file-card').classes()).toContain('is-clickable');
    });

    it('variant=list 且 active 时应带 is-list 与 is-active 态', () => {
      wrapper = mount(ArtifactFileCard, {
        props: { active: true, file: createFile(), onPreview: vi.fn(), variant: 'list' },
      });

      const card = wrapper.find('.ai-artifact-file-card');
      expect(card.classes()).toContain('is-list');
      expect(card.classes()).toContain('is-active');
    });
  });

  describe('交互测试', () => {
    it('点击卡片应该调用 onPreview', async () => {
      const onPreview = vi.fn();
      const file = createFile();
      wrapper = mount(ArtifactFileCard, { props: { file, onPreview } });

      await wrapper.find('.ai-artifact-file-card').trigger('click');

      expect(onPreview).toHaveBeenCalledWith(file);
    });

    it('无 onPreview 时点击卡片应调用侧栏预览 openPreview 并透传定位信息', async () => {
      const openPreview = vi.fn();
      const artifactPreview = { activeArtifactId: ref(''), openPreview, setActiveArtifactId: vi.fn() };
      const file = createFile();
      wrapper = mount(ArtifactFileCard, {
        global: { provide: { [ARTIFACT_PREVIEW_TOKEN]: artifactPreview } },
        props: { file, index: 2, messageUid: 'msg-a' },
      });

      await wrapper.find('.ai-artifact-file-card').trigger('click');

      expect(openPreview).toHaveBeenCalledWith({ file, index: 2, messageUid: 'msg-a' });
    });

    it('传入 onDownload 时点击下载应该调用回调而非默认下载', async () => {
      const onDownload = vi.fn();
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      const file = createFile();
      wrapper = mount(ArtifactFileCard, { props: { file, onDownload } });

      await wrapper.find('.ai-artifact-file-card-download').trigger('click');

      expect(onDownload).toHaveBeenCalledWith(file);
      expect(clickSpy).not.toHaveBeenCalled();
      clickSpy.mockRestore();
    });

    it('未传 onDownload 时点击下载应该触发默认下载', async () => {
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      wrapper = mount(ArtifactFileCard, { props: { file: createFile() } });

      await wrapper.find('.ai-artifact-file-card-download').trigger('click');

      expect(clickSpy).toHaveBeenCalledTimes(1);
      clickSpy.mockRestore();
    });

    it('点击下载不应该冒泡触发 onPreview', async () => {
      const onPreview = vi.fn();
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      wrapper = mount(ArtifactFileCard, { props: { file: createFile(), onPreview } });

      await wrapper.find('.ai-artifact-file-card-download').trigger('click');

      expect(onPreview).not.toHaveBeenCalled();
      clickSpy.mockRestore();
    });
  });
});
