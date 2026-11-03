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
import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ReasoningEffortSlider from './reasoning-effort-slider.vue';

import type { IReasoningEffortOption, ReasoningEffort } from './types';

const SIX_EFFORTS: IReasoningEffortOption[] = [
  { desc: '不思考，直接回答', key: 'none', value: '关闭' },
  { desc: '简单思考，响应较快', key: 'low', value: '低' },
  { desc: '兼顾思考深度与响应速度', key: 'medium', value: '中' },
  { desc: '深入思考，回答更周全', key: 'high', value: '高' },
  { desc: '更深入的思考，适合复杂问题', key: 'xhigh', value: '超高' },
  { desc: '最大思考投入，耗时最长', key: 'max', value: '最高' },
];

// 轨道 0~177px、5 段、段间距 2px：第 i 档对应第 i 个分段交界，中心在 i × 179 / 5 - 1
const TRACK_RECT = new DOMRect(0, 0, 177, 12);
const clientXOf = (index: number) => (index * 179) / 5 - 1;

describe('ReasoningEffortSlider', () => {
  let wrapper: undefined | VueWrapper;

  const mountSlider = (props: { disabled?: boolean; effort?: ReasoningEffort; options?: IReasoningEffortOption[] }) => {
    wrapper = mount(ReasoningEffortSlider, {
      props: { options: SIX_EFFORTS, ...props },
    });
    const track = wrapper.find('.ai-reasoning-effort-slider-track');
    vi.spyOn(track.element, 'getBoundingClientRect').mockReturnValue(TRACK_RECT);
    return track;
  };

  const segments = () => wrapper?.findAll('.ai-reasoning-effort-slider-segment');
  const activeCount = () => segments().filter(segment => segment.classes('is-active')).length;
  const thumb = () => wrapper?.find('.ai-reasoning-effort-slider-thumb');
  const valueText = () => wrapper?.find('.ai-reasoning-effort-slider-value');
  const tip = () => wrapper?.find('.ai-reasoning-effort-slider-tip');

  afterEach(() => {
    wrapper?.unmount();
    wrapper = undefined;
  });

  describe('渲染', () => {
    it('段数 = 档位数 - 1；「关闭」时轨道全灰、滑块在最左', () => {
      mountSlider({ effort: 'none' });
      expect(segments()).toHaveLength(5);
      expect(activeCount()).toBe(0);
      expect(thumb().attributes('style')).toContain('--ai-reasoning-effort-thumb-ratio: 0');
      expect(valueText().text()).toBe('关闭');
    });

    it('选中第二档「低」时只有第一段高亮，并以 desc 作为提示', () => {
      mountSlider({ effort: 'low' });
      expect(activeCount()).toBe(1);
      expect(segments()[0].classes('is-active')).toBe(true);
      expect(valueText().text()).toBe('低');
      expect(valueText().attributes('title')).toBe('简单思考，响应较快');
      expect(thumb().attributes('aria-valuenow')).toBe('1');
      expect(thumb().attributes('aria-valuetext')).toBe('低');
    });

    it('选中最后一档时全部高亮、滑块在最右', () => {
      mountSlider({ effort: 'max' });
      expect(activeCount()).toBe(5);
      expect(thumb().attributes('style')).toContain('--ai-reasoning-effort-thumb-ratio: 1');
      expect(valueText().text()).toBe('最高');
    });

    it('档位不在选项内时不高亮、不显示当前值', () => {
      mountSlider({ effort: 'minimal' });
      expect(activeCount()).toBe(0);
      expect(valueText().text()).toBe('');
    });

    it('只有一个档位时整段高亮、滑块在最右且不可操作', async () => {
      const track = mountSlider({ effort: 'high', options: [SIX_EFFORTS[3]] });
      expect(segments()).toHaveLength(1);
      expect(activeCount()).toBe(1);
      expect(thumb().attributes('style')).toContain('--ai-reasoning-effort-thumb-ratio: 1');
      expect(thumb().attributes('tabindex')).toBe('-1');
      expect(wrapper?.classes()).toContain('is-static');

      await track.trigger('pointerdown', { button: 0, clientX: 0, pointerId: 1 });
      await track.trigger('pointerup', { clientX: 0, pointerId: 1 });
      expect(wrapper?.emitted('change')).toBeFalsy();
    });
  });

  describe('交互', () => {
    it('按下轨道后聚焦滑块，左右键才能调档', async () => {
      wrapper = mount(ReasoningEffortSlider, {
        attachTo: document.body,
        props: { effort: 'low', options: SIX_EFFORTS },
      });
      const track = wrapper.find('.ai-reasoning-effort-slider-track');
      vi.spyOn(track.element, 'getBoundingClientRect').mockReturnValue(TRACK_RECT);

      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(1), pointerId: 1 });
      expect(document.activeElement).toBe(thumb().element);
      await track.trigger('pointerup', { clientX: clientXOf(1), clientY: 6, pointerId: 1 });

      await thumb().trigger('keydown', { key: 'ArrowRight' });
      expect(wrapper.emitted('change')).toEqual([['medium']]);
      // 左右键后气泡跟着新档位，不留在按下时的位置
      expect(tip().text()).toBe('中');
      expect(tip().attributes('style')).toContain('--ai-reasoning-effort-tip-ratio: 0.4');

      await wrapper.setProps({ effort: 'medium' });
      await thumb().trigger('keydown', { key: 'ArrowLeft' });
      expect(tip().text()).toBe('低');
      expect(tip().attributes('style')).toContain('--ai-reasoning-effort-tip-ratio: 0.2');

      await thumb().trigger('blur');
      expect(tip().exists()).toBe(false);
    });

    it('点击轨道应在按下时就近吸附，并只抛出一次 change', async () => {
      const track = mountSlider({ effort: 'none' });
      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(2) + 10, pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['medium']]);
      await track.trigger('pointerup', { clientX: clientXOf(2) + 10, clientY: 6, pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['medium']]);
    });

    it('点击位置按分段交界划分：越过第一段中点即吸附到第 1 档', async () => {
      // 第一段 0~34.8，中点 17.4；x=18 更靠近第 1 个交界
      const track = mountSlider({ effort: 'none' });
      await track.trigger('pointerdown', { button: 0, clientX: 18, pointerId: 1 });
      await track.trigger('pointerup', { clientX: 18, pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['low']]);
    });

    it('拖动跨档时立即抛出 change，同一档不重复，松手不再抛出', async () => {
      const track = mountSlider({ effort: 'none' });
      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(0), pointerId: 1 });
      expect(wrapper?.emitted('dragging')).toEqual([[true]]);
      expect(wrapper?.emitted('change')).toBeFalsy();

      await track.trigger('pointermove', { clientX: clientXOf(3), pointerId: 1 });
      expect(activeCount()).toBe(3);
      expect(valueText().text()).toBe('高');
      expect(tip().text()).toBe('高');
      expect(wrapper?.emitted('change')).toEqual([['high']]);

      // 仍停在同一档时不重复抛出
      await track.trigger('pointermove', { clientX: clientXOf(3) + 2, pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['high']]);

      // 拖出轨道右侧应夹到最后一档；松手不再追加
      await track.trigger('pointermove', { clientX: 999, pointerId: 1 });
      await track.trigger('pointerup', { clientX: 999, clientY: 0, pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['high'], ['max']]);
      expect(wrapper?.emitted('dragging')).toEqual([[true], [false]]);
    });

    it('松手位置与当前档位相同时不抛 change', async () => {
      const track = mountSlider({ effort: 'low' });
      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(1), pointerId: 1 });
      await track.trigger('pointerup', { clientX: clientXOf(1), pointerId: 1 });
      expect(wrapper?.emitted('change')).toBeFalsy();
    });

    it('pointercancel 结束拖动，不撤回已抛出的档位', async () => {
      const track = mountSlider({ effort: 'low' });
      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(4), pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['xhigh']]);
      await track.trigger('pointercancel', { pointerId: 1 });
      expect(wrapper?.emitted('change')).toEqual([['xhigh']]);
      expect(wrapper?.emitted('dragging')).toEqual([[true], [false]]);
      // 父级未回写 effort 时，展示回落到 props
      expect(valueText().text()).toBe('低');
      expect(tip().exists()).toBe(false);
    });

    it('悬停轨道时显示所在档位名称，不改变选中；移出后气泡消失', async () => {
      const track = mountSlider({ effort: 'none' });
      expect(tip().exists()).toBe(false);

      await track.trigger('pointermove', { clientX: clientXOf(2) });
      expect(tip().text()).toBe('中');
      expect(tip().attributes('style')).toContain('--ai-reasoning-effort-tip-ratio: 0.4');
      expect(valueText().text()).toBe('关闭');
      expect(activeCount()).toBe(0);
      expect(wrapper?.emitted('change')).toBeFalsy();

      await track.trigger('pointerleave');
      expect(tip().exists()).toBe(false);
    });

    it('disabled 时悬停仍显示档位名称，但按下不抛 change', async () => {
      const track = mountSlider({ disabled: true, effort: 'low' });
      await track.trigger('pointermove', { clientX: clientXOf(3) });
      expect(tip().text()).toBe('高');
      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(4), pointerId: 1 });
      expect(wrapper?.emitted('change')).toBeFalsy();
    });

    it('左右方向键、Home、End 应调档，越界时不抛出', async () => {
      mountSlider({ effort: 'low' });
      await thumb().trigger('keydown', { key: 'ArrowRight' });
      await thumb().trigger('keydown', { key: 'ArrowLeft' });
      await thumb().trigger('keydown', { key: 'End' });
      await thumb().trigger('keydown', { key: 'Home' });
      // 上下方向键由模型列表的键盘导航使用，这里不响应
      await thumb().trigger('keydown', { key: 'ArrowUp' });
      expect(wrapper?.emitted('change')).toEqual([['medium'], ['none'], ['max'], ['none']]);

      await wrapper?.setProps({ effort: 'none' });
      await thumb().trigger('keydown', { key: 'ArrowLeft' });
      expect(wrapper?.emitted('change')).toHaveLength(4);
    });

    it('disabled 时不响应点击和按键', async () => {
      const track = mountSlider({ disabled: true, effort: 'low' });
      await track.trigger('pointerdown', { button: 0, clientX: clientXOf(4), pointerId: 1 });
      await track.trigger('pointerup', { clientX: clientXOf(4), pointerId: 1 });
      await thumb().trigger('keydown', { key: 'ArrowRight' });
      expect(wrapper?.emitted('change')).toBeFalsy();
      expect(wrapper?.classes()).toContain('is-disabled');
    });
  });
});
