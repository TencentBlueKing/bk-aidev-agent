import { defineComponent, h } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { AIFileType } from '../ag-ui/types/file';
import {
  buildArtifactId,
  useArtifactPreviewConsumer,
  useArtifactPreviewProvider,
} from './use-artifact-preview';

import type { AIFileInfo } from '../ag-ui/types/file';

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: 'file.pdf',
  outputId: 'output-1',
  previewUrl: 'https://example.com/preview.pdf',
  size: 1024,
  type: AIFileType.Pdf,
  url: 'https://example.com/download',
  ...overrides,
});

describe('use-artifact-preview', () => {
  describe('buildArtifactId', () => {
    it('应该按 messageUid#index#outputId 组合唯一 id', () => {
      expect(buildArtifactId('m1', 2, 'o3')).toBe('m1#2#o3');
    });
  });

  describe('Provider / Consumer', () => {
    // 通过父子组件建立 provide/inject，父暴露 provider api、子暴露 consumer ctx
    const setup = (onOpen = vi.fn()) => {
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
          providerApi = useArtifactPreviewProvider({ onOpen });
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
  });
});
