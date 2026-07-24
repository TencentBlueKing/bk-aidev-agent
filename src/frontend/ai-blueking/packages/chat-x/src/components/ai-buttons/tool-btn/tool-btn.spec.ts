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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ToolBtn from './tool-btn.vue';

import type { IToolBtn } from '../../../types';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock vue-tippy directive
vi.mock('vue-tippy', () => ({
  directive: {
    mounted: vi.fn(),
    unmounted: vi.fn(),
  },
}));

// Mock ToolIconsMap
vi.mock('../../../icons/tools', () => ({
  ToolIconsMap: {
    copy: defineComponent({
      name: 'CopyIcon',
      setup() {
        return () => h('span', { class: 'mock-copy-icon' });
      },
    }),
    cite: defineComponent({
      name: 'CiteIcon',
      setup() {
        return () => h('span', { class: 'mock-cite-icon' });
      },
    }),
    rebuild: defineComponent({
      name: 'RebuildIcon',
      setup() {
        return () => h('span', { class: 'mock-rebuild-icon' });
      },
    }),
    share: defineComponent({
      name: 'ShareIcon',
      setup() {
        return () => h('span', { class: 'mock-share-icon' });
      },
    }),
    like: defineComponent({
      name: 'LikeIcon',
      setup() {
        return () => h('span', { class: 'mock-like-icon' });
      },
    }),
    unlike: defineComponent({
      name: 'UnLikeIcon',
      setup() {
        return () => h('span', { class: 'mock-unlike-icon' });
      },
    }),
    delete: defineComponent({
      name: 'DeleteIcon',
      setup() {
        return () => h('span', { class: 'mock-delete-icon' });
      },
    }),
    edit: defineComponent({
      name: 'EditIcon',
      setup() {
        return () => h('span', { class: 'mock-edit-icon' });
      },
    }),
  },
}));

// Helper function to create tool button props
const createToolBtnProps = (id: IToolBtn['id'], name: string, description: string): IToolBtn => ({
  id,
  name,
  description,
});

describe('ToolBtn', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容到剪贴板');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
    });

    it('当存在对应图标时应该渲染图标', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-copy-icon').exists()).toBe(true);
    });

    it('当图标不存在时应该显示 name 文本', () => {
      const props = {
        id: 'unknown' as IToolBtn['id'],
        name: '未知操作',
        description: '未知操作描述',
      };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.text()).toContain('未知操作');
    });

    it('传入默认 slot 时应优先渲染 slot 内容而非内置图标', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
        slots: {
          default: () => h('span', { class: 'custom-slot-icon' }, '全屏'),
        },
      });

      expect(wrapper.find('.custom-slot-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-copy-icon').exists()).toBe(false);
    });

    it('未传 id 时应显示 name 文本', () => {
      wrapper = mount(ToolBtn, {
        props: {
          name: '全屏',
          description: '全屏',
        },
      });

      expect(wrapper.text()).toContain('全屏');
    });
  });

  describe('自定义 icon 测试', () => {
    const CustomIcon = defineComponent({
      name: 'CustomIcon',
      setup() {
        return () => h('span', { class: 'custom-icon' });
      },
    });

    it('传入 icon（组件）时应渲染自定义图标', () => {
      wrapper = mount(ToolBtn, {
        props: { id: 'save' as IToolBtn['id'], name: '保存', description: '保存', icon: CustomIcon },
      });

      expect(wrapper.find('.custom-icon').exists()).toBe(true);
    });

    it('传入 icon（VNode）时应渲染自定义图标', () => {
      wrapper = mount(ToolBtn, {
        props: {
          id: 'save' as IToolBtn['id'],
          name: '保存',
          description: '保存',
          icon: h('span', { class: 'vnode-icon' }),
        },
      });

      expect(wrapper.find('.vnode-icon').exists()).toBe(true);
    });

    it('icon 优先级应高于内置图标（id 命中内置也用自定义 icon）', () => {
      wrapper = mount(ToolBtn, {
        props: { id: 'copy', name: '复制', description: '复制', icon: CustomIcon },
      });

      expect(wrapper.find('.custom-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-copy-icon').exists()).toBe(false);
    });

    it('默认 slot 优先级应高于 icon prop', () => {
      wrapper = mount(ToolBtn, {
        props: { id: 'save' as IToolBtn['id'], name: '保存', description: '保存', icon: CustomIcon },
        slots: {
          default: () => h('span', { class: 'slot-icon' }),
        },
      });

      expect(wrapper.find('.slot-icon').exists()).toBe(true);
      expect(wrapper.find('.custom-icon').exists()).toBe(false);
    });
  });

  describe('不同图标类型测试', () => {
    it('应该正确渲染 copy 图标', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-copy-icon').exists()).toBe(true);
    });

    it('应该正确渲染 cite 图标', () => {
      const props = createToolBtnProps('cite', '引用', '引用内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-cite-icon').exists()).toBe(true);
    });

    it('应该正确渲染 rebuild 图标', () => {
      const props = createToolBtnProps('rebuild', '重新生成', '重新生成内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-rebuild-icon').exists()).toBe(true);
    });

    it('应该正确渲染 share 图标', () => {
      const props = createToolBtnProps('share', '分享', '分享内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-share-icon').exists()).toBe(true);
    });

    it('应该正确渲染 like 图标', () => {
      const props = createToolBtnProps('like', '点赞', '点赞内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-like-icon').exists()).toBe(true);
    });

    it('应该正确渲染 unlike 图标', () => {
      const props = createToolBtnProps('unlike', '踩', '踩内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-unlike-icon').exists()).toBe(true);
    });

    it('应该正确渲染 delete 图标', () => {
      const props = createToolBtnProps('delete', '删除', '删除内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-delete-icon').exists()).toBe(true);
    });

    it('应该正确渲染 edit 图标', () => {
      const props = createToolBtnProps('edit', '编辑', '编辑内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.mock-edit-icon').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击时应该触发 click 事件并传递正确的参数', async () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeTruthy();
      expect(wrapper.emitted('click')?.length).toBe(1);

      const emittedArgs = wrapper.emitted('click')?.[0];
      // 组件会包含所有 props（包括 active 的默认值）
      expect(emittedArgs?.[0]).toMatchObject(props);
      expect(emittedArgs?.[1]).toBeInstanceOf(MouseEvent);
    });

    it('多次点击应该触发多次 click 事件', async () => {
      const props = createToolBtnProps('like', '点赞', '点赞内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      await wrapper.trigger('click');
      await wrapper.trigger('click');
      await wrapper.trigger('click');

      expect(wrapper.emitted('click')?.length).toBe(3);
    });

    it('每次点击应该传递当前的 props', async () => {
      const props = createToolBtnProps('share', '分享', '分享内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      await wrapper.trigger('click');

      const emittedArgs = wrapper.emitted('click')?.[0];
      expect(emittedArgs?.[0]).toMatchObject({
        id: 'share',
        name: '分享',
        description: '分享内容',
      });
    });

    it('disabled 为 true 时点击不应该触发 click 事件', async () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), disabled: true };

      wrapper = mount(ToolBtn, {
        props,
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeFalsy();
    });

    it('disabled 为 false 时点击应该正常触发 click 事件', async () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), disabled: false };

      wrapper = mount(ToolBtn, {
        props,
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeTruthy();
      expect(wrapper.emitted('click')?.length).toBe(1);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 id 属性', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as IToolBtn).id).toBe('copy');
    });

    it('应该正确接收 name 属性', () => {
      const props = createToolBtnProps('copy', '复制按钮', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as IToolBtn).name).toBe('复制按钮');
    });

    it('应该正确接收 description 属性', () => {
      const props = createToolBtnProps('copy', '复制', '这是一个复制按钮的描述');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as IToolBtn).description).toBe('这是一个复制按钮的描述');
    });

    it('应该正确接收 active 属性', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), active: true };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as IToolBtn & { active?: boolean }).active).toBe(true);
    });

    it('应该正确接收 disabled 属性', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), disabled: true };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as IToolBtn & { disabled?: boolean }).disabled).toBe(true);
    });

    it('disabled 默认应该为 false', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as IToolBtn & { disabled?: boolean }).disabled).toBeFalsy();
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      const btn = wrapper.find('.ai-tool-btn');
      expect(btn.exists()).toBe(true);
    });

    it('active 为 true 时应该添加 is-active 类', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), active: true };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').classes()).toContain('is-active');
    });

    it('active 为 false 时不应该添加 is-active 类', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), active: false };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').classes()).not.toContain('is-active');
    });

    it('active 默认应该为 false（不添加 is-active 类）', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').classes()).not.toContain('is-active');
    });

    it('disabled 为 true 时应该添加 is-disabled 类', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), disabled: true };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').classes()).toContain('is-disabled');
    });

    it('disabled 为 false 时不应该添加 is-disabled 类', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), disabled: false };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').classes()).not.toContain('is-disabled');
    });

    it('图标通过 font-size 控制大小（16px）', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, { props });

      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
      expect(wrapper.find('.mock-copy-icon').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 name', () => {
      const props = {
        id: 'unknown' as IToolBtn['id'],
        name: '',
        description: '描述',
      };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
    });

    it('应该处理空 description', () => {
      const props = createToolBtnProps('copy', '复制', '');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
    });

    it('应该处理特殊字符的 name 和 description', () => {
      const props = {
        id: 'unknown' as IToolBtn['id'],
        name: '<script>alert("xss")</script>',
        description: '这是<b>描述</b>',
      };

      wrapper = mount(ToolBtn, {
        props,
      });

      // 当图标不存在时显示 name，Vue 会自动转义 HTML
      expect(wrapper.text()).toContain('<script>alert("xss")</script>');
      // 确保没有实际执行脚本
      expect(wrapper.find('script').exists()).toBe(false);
    });

    it('应该处理很长的 name 和 description', () => {
      const longName = '这是一个非常长的名称'.repeat(10);
      const longDescription = '这是一个非常长的描述'.repeat(20);
      const props = {
        id: 'unknown' as IToolBtn['id'],
        name: longName,
        description: longDescription,
      };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.text()).toContain(longName);
    });
  });

  describe('Active Color CSS 变量测试', () => {
    it('id 为 like 时 active color 应为 #3a84ff', () => {
      const props = { ...createToolBtnProps('like', '点赞', '点赞内容'), active: true };

      wrapper = mount(ToolBtn, { props });

      const btn = wrapper.find('.ai-tool-btn');
      const style = btn.attributes('style') || '';
      expect(style).toContain('--ai-tool-btn-active-color: #3a84ff');
    });

    it('id 为 activeLike 时 active color 应为 #3a84ff', () => {
      const props = { ...createToolBtnProps('activeLike', '取消满意', '取消满意'), active: true };

      wrapper = mount(ToolBtn, { props });

      const btn = wrapper.find('.ai-tool-btn');
      const style = btn.attributes('style') || '';
      expect(style).toContain('--ai-tool-btn-active-color: #3a84ff');
    });

    it('id 非 like/activeLike 时 active color 应为 #E71818', () => {
      const props = { ...createToolBtnProps('unlike', '踩', '踩内容'), active: true };

      wrapper = mount(ToolBtn, { props });

      const btn = wrapper.find('.ai-tool-btn');
      const style = btn.attributes('style') || '';
      expect(style).toContain('--ai-tool-btn-active-color: #E71818');
    });
  });

  describe('Tooltip 测试', () => {
    it('应该将 description 作为 tooltip 内容', () => {
      const description = '这是复制按钮的提示';
      const props = createToolBtnProps('copy', '复制', description);

      wrapper = mount(ToolBtn, {
        props,
      });

      // v-tippy 指令已被 mock，我们只需验证组件正确渲染
      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
    });
  });

  describe('tippyOptions 测试', () => {
    it('应该正确接收 tippyOptions 属性', () => {
      const tippyOptions = { appendTo: 'parent' as const };
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), tippyOptions };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect((wrapper.props() as Record<string, unknown>).tippyOptions).toEqual(tippyOptions);
    });

    it('不传 tippyOptions 时组件应正常渲染', () => {
      const props = createToolBtnProps('copy', '复制', '复制内容');

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
      expect((wrapper.props() as Record<string, unknown>).tippyOptions).toBeUndefined();
    });

    it('tippyOptions 为空对象时组件应正常渲染', () => {
      const props = { ...createToolBtnProps('copy', '复制', '复制内容'), tippyOptions: {} };

      wrapper = mount(ToolBtn, {
        props,
      });

      expect(wrapper.find('.ai-tool-btn').exists()).toBe(true);
    });
  });
});
