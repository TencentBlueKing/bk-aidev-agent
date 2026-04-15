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

import { useImageTransform } from './use-image-transform';

describe('useImageTransform', () => {
  describe('初始状态', () => {
    it('应该返回初始样式', () => {
      const { imageStyle } = useImageTransform();

      expect(imageStyle.value).toEqual({
        transform: 'translate(0px, 0px) scale(1) rotate(0deg)',
        cursor: 'grab',
        transition: 'transform 0.3s ease',
      });
    });
  });

  describe('zoomIn', () => {
    it('应该放大图片', () => {
      const { imageStyle, zoomIn } = useImageTransform();

      zoomIn();

      expect(imageStyle.value.transform).toContain('scale(1.15)');
    });

    it('不应该超过最大缩放', () => {
      const { imageStyle, zoomIn } = useImageTransform();

      for (let i = 0; i < 100; i++) zoomIn();

      const match = imageStyle.value.transform!.toString().match(/scale\(([\d.]+)\)/);
      expect(Number(match?.[1])).toBeLessThanOrEqual(10);
    });
  });

  describe('zoomOut', () => {
    it('应该缩小图片', () => {
      const { imageStyle, zoomOut } = useImageTransform();

      zoomOut();

      const match = imageStyle.value.transform!.toString().match(/scale\(([\d.]+)\)/);
      expect(Number(match?.[1])).toBeLessThan(1);
    });

    it('不应该低于最小缩放', () => {
      const { imageStyle, zoomOut } = useImageTransform();

      for (let i = 0; i < 100; i++) zoomOut();

      const match = imageStyle.value.transform!.toString().match(/scale\(([\d.]+)\)/);
      expect(Number(match?.[1])).toBeGreaterThanOrEqual(0.1);
    });
  });

  describe('rotateCW', () => {
    it('应该顺时针旋转 90 度', () => {
      const { imageStyle, rotateCW } = useImageTransform();

      rotateCW();

      expect(imageStyle.value.transform).toContain('rotate(90deg)');
    });

    it('旋转 4 次后累计到 360 度', () => {
      const { imageStyle, rotateCW } = useImageTransform();

      rotateCW();
      rotateCW();
      rotateCW();
      rotateCW();

      expect(imageStyle.value.transform).toContain('rotate(360deg)');
    });
  });

  describe('resetTransform', () => {
    it('应该重置所有变换', () => {
      const { imageStyle, zoomIn, rotateCW, resetTransform } = useImageTransform();

      zoomIn();
      rotateCW();
      resetTransform();

      expect(imageStyle.value).toEqual({
        transform: 'translate(0px, 0px) scale(1) rotate(0deg)',
        cursor: 'grab',
        transition: 'none',
      });
    });

    it('requestAnimationFrame 回调后应恢复 transition', async () => {
      const { imageStyle, zoomIn, resetTransform } = useImageTransform();

      zoomIn();
      resetTransform();

      expect(imageStyle.value.transition).toBe('none');

      await new Promise(resolve => requestAnimationFrame(resolve));

      expect(imageStyle.value.transition).toBe('transform 0.3s ease');
    });
  });

  describe('handleWheel', () => {
    it('向上滚动应该放大', () => {
      const { imageStyle, handleWheel } = useImageTransform();

      const zoomInEvent: Partial<WheelEvent> = { deltaY: -100 };
      handleWheel(zoomInEvent as WheelEvent);

      expect(imageStyle.value.transform).toContain('scale(1.15)');
    });

    it('向下滚动应该缩小', () => {
      const { imageStyle, handleWheel } = useImageTransform();

      const zoomOutEvent: Partial<WheelEvent> = { deltaY: 100 };
      handleWheel(zoomOutEvent as WheelEvent);

      const match = imageStyle.value.transform!.toString().match(/scale\(([\d.]+)\)/);
      expect(Number(match?.[1])).toBeLessThan(1);
    });
  });
});
