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

import { nextTick } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AiSkillList from './ai-skill-list.vue';

import type { ISkillListItem } from '../../../../types/editor';

// Mock composables
vi.mock('../../../../composables/use-menu-keydown', () => ({
  useMenuKeydown: () => ({
    activeIndex: { value: 0 },
  }),
}));

describe('AiSkillList', () => {
  let wrapper: VueWrapper;

  const defaultSkills: ISkillListItem[] = [
    { skill_code: 'skill1', skill_name: 'Skill 1', description: 'Description 1', icon: '' },
    { skill_code: 'skill2', skill_name: 'Skill 2', description: 'Description 2', icon: 'https://example.com/icon.png' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.find('.ai-skill-list').exists()).toBe(true);
    });

    it('应该渲染所有 skills', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect: vi.fn(),
        },
      });

      const items = wrapper.findAll('.ai-skill-list-item');
      expect(items.length).toBe(2);
    });

    it('应该正确显示 skill 名称', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect: vi.fn(),
        },
      });

      const items = wrapper.findAll('.ai-skill-list-item-name');
      expect(items[0].text()).toBe('Skill 1');
      expect(items[1].text()).toBe('Skill 2');
    });

    it('不应该显示 skill 描述', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect: vi.fn(),
        },
      });

      const descs = wrapper.findAll('.ai-skill-list-item-desc');
      expect(descs.length).toBe(0);
      expect(wrapper.text()).not.toContain('Description 1');
      expect(wrapper.text()).not.toContain('Description 2');
    });

    it('有 icon 时应该渲染 img 元素', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect: vi.fn(),
        },
      });

      const items = wrapper.findAll('.ai-skill-list-item');
      expect(items[0].find('img.ai-skill-list-item-icon').exists()).toBe(false);
      expect(items[0].find('.ai-skill-list-item-icon--fallback').exists()).toBe(true);
      expect(items[1].find('img.ai-skill-list-item-icon').exists()).toBe(true);
      expect(items[1].find('img.ai-skill-list-item-icon').attributes('src')).toBe(
        'https://example.com/icon.png',
      );
    });

    it('无 icon 时应渲染首字母 fallback 图标', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: [defaultSkills[0]],
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.find('.ai-skill-list-item-icon--fallback').exists()).toBe(true);
      expect(wrapper.find('.ai-skill-list-item-icon--fallback').text()).toBe('S');
    });

    it('icon 加载失败时应切换为首字母 fallback 图标', async () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: [defaultSkills[1]],
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.find('img.ai-skill-list-item-icon').exists()).toBe(true);

      await wrapper.find('img.ai-skill-list-item-icon').trigger('error');
      await nextTick();

      expect(wrapper.find('img.ai-skill-list-item-icon').exists()).toBe(false);
      expect(wrapper.find('.ai-skill-list-item-icon--fallback').exists()).toBe(true);
      expect(wrapper.find('.ai-skill-list-item-icon--fallback').text()).toBe('S');
    });
  });

  describe('事件测试', () => {
    it('点击 skill 应该调用 onSelect', async () => {
      const onSelect = vi.fn();

      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect,
        },
      });

      await wrapper.find('.ai-skill-list-item').trigger('click');

      expect(onSelect).toHaveBeenCalledWith(defaultSkills[0]);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 skills 数组', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: [],
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.find('.ai-skill-list').exists()).toBe(true);
      expect(wrapper.findAll('.ai-skill-list-item').length).toBe(0);
    });

    it('应该处理单个 skill', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: [defaultSkills[0]],
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.findAll('.ai-skill-list-item').length).toBe(1);
    });

    it('应该处理没有描述的 skill', () => {
      const skillsWithoutDesc: ISkillListItem[] = [
        { skill_code: 'skill1', skill_name: 'Skill 1', description: '', icon: '' },
      ];

      wrapper = mount(AiSkillList, {
        props: {
          skills: skillsWithoutDesc,
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.find('.ai-skill-list-item-desc').exists()).toBe(false);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(AiSkillList, {
        props: {
          skills: defaultSkills,
          onSelect: vi.fn(),
        },
      });

      expect(wrapper.find('.ai-skill-list').exists()).toBe(true);
      expect(wrapper.find('.ai-skill-list-item').exists()).toBe(true);
      expect(wrapper.find('.ai-skill-list-item-icon').exists()).toBe(true);
      expect(wrapper.find('.ai-skill-list-item-info').exists()).toBe(true);
      expect(wrapper.find('.ai-skill-list-item-name').exists()).toBe(true);
    });
  });
});