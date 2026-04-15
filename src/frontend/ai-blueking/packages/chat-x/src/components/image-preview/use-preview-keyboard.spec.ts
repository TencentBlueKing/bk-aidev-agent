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
import { defineComponent, h, ref } from 'vue';

import { mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { usePreviewKeyboard } from './use-preview-keyboard';

function createTestWrapper(visible = false) {
  const onClose = vi.fn();
  const onPrev = vi.fn();
  const onNext = vi.fn();
  const visibleRef = ref(visible);

  const wrapper = mount(
    defineComponent({
      setup() {
        usePreviewKeyboard({
          visible: visibleRef,
          onClose,
          onPrev,
          onNext,
        });
        return () => h('div');
      },
    }),
  );

  return { wrapper, visibleRef, onClose, onPrev, onNext };
}

describe('usePreviewKeyboard', () => {
  afterEach(() => {
    document.body.style.overflow = '';
  });

  describe('键盘事件', () => {
    it('visible 为 true 时按 Escape 应调用 onClose', () => {
      const { wrapper, onClose } = createTestWrapper(true);

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

      expect(onClose).toHaveBeenCalled();
      wrapper.unmount();
    });

    it('visible 为 true 时按 ArrowLeft 应调用 onPrev', () => {
      const { wrapper, onPrev } = createTestWrapper(true);

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));

      expect(onPrev).toHaveBeenCalled();
      wrapper.unmount();
    });

    it('visible 为 true 时按 ArrowRight 应调用 onNext', () => {
      const { wrapper, onNext } = createTestWrapper(true);

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));

      expect(onNext).toHaveBeenCalled();
      wrapper.unmount();
    });

    it('visible 为 false 时键盘事件不应触发回调', () => {
      const { wrapper, onClose, onPrev, onNext } = createTestWrapper(false);

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));

      expect(onClose).not.toHaveBeenCalled();
      expect(onPrev).not.toHaveBeenCalled();
      expect(onNext).not.toHaveBeenCalled();
      wrapper.unmount();
    });
  });

  describe('body overflow', () => {
    it('visible 为 true 时应该设置 body overflow 为 hidden', () => {
      const { wrapper } = createTestWrapper(true);

      expect(document.body.style.overflow).toBe('hidden');
      wrapper.unmount();
    });

    it('visible 为 false 时应该恢复 body overflow', () => {
      const { wrapper } = createTestWrapper(false);

      expect(document.body.style.overflow).toBe('');
      wrapper.unmount();
    });
  });

  describe('生命周期', () => {
    it('组件卸载时应该清理键盘事件监听', () => {
      const { wrapper, onClose } = createTestWrapper(true);

      wrapper.unmount();

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      expect(onClose).not.toHaveBeenCalled();
    });

    it('组件卸载时应该恢复 body overflow', () => {
      const { wrapper } = createTestWrapper(true);

      expect(document.body.style.overflow).toBe('hidden');
      wrapper.unmount();
      expect(document.body.style.overflow).toBe('');
    });
  });
});
