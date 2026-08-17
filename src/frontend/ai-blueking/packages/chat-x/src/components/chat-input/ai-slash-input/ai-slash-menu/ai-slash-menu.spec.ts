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

import { shallowRef } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AiSlashMenu from './ai-slash-menu.vue';

// Mock composables
vi.mock('../../../../composables/use-menu-keydown', () => ({
  useMenuKeydown: () => ({
    activeIndex: shallowRef(0),
  }),
}));

// Mock directives
vi.mock('../../../../directives/overflow-tips', () => ({
  default: {},
}));

// Mock types
vi.mock('../../../../types', () => ({
  resourceTypeMap: {
    tool: '工具',
    shortcut: '快捷指令',
    doc: '文档',
    mcp: 'MCP',
  },
}));

describe('AiSlashMenu', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('有 resourceList 时应该渲染组件', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool' }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-menu').exists()).toBe(true);
    });

    it('没有 resourceList 时不应该渲染组件', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-menu').exists()).toBe(false);
    });

    it('应该按类型分组渲染', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [
            { id: '1', name: 'Tool 1', type: 'tool' },
            { id: '2', name: 'Tool 2', type: 'tool' },
            { id: '3', name: 'Shortcut 1', type: 'shortcut' },
          ],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.findAll('.ai-slash-group').length).toBeGreaterThan(0);
    });
  });

  describe('分组标题测试', () => {
    it('应该显示分组标题', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool', icon: null }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-group-title').exists()).toBe(true);
    });

    it('分组标题不应显示类型色块', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool', icon: null }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.mark-tool').exists()).toBe(false);
      expect(wrapper.find('[class^="mark-"]').exists()).toBe(false);
    });

    it('应该显示分组内项目数量', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [
            { id: '1', name: 'Tool 1', type: 'tool', icon: null },
            { id: '2', name: 'Tool 2', type: 'tool', icon: null },
          ],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-group-title').text()).toContain('(2)');
    });
  });

  describe('选项图标测试', () => {
    it('无 icon 时应渲染首字母 fallback 图标', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool', icon: null }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-group-item-icon--fallback').exists()).toBe(true);
      expect(wrapper.find('.ai-slash-group-item-icon--fallback').text()).toBe('T');
    });

    it('有 icon 时应渲染 img 元素', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [
            { id: '1', name: 'Tool 1', type: 'tool', icon: 'https://example.com/icon.png' },
          ],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      const img = wrapper.find('img.ai-slash-group-item-icon');
      expect(img.exists()).toBe(true);
      expect(img.attributes('src')).toBe('https://example.com/icon.png');
    });
  });

  describe('事件测试', () => {
    it('点击项目应该调用 onSelect', async () => {
      const onSelect = vi.fn();

      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool' }],
          onSelect,
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      await wrapper.find('.ai-slash-group-item').trigger('click');

      expect(onSelect).toHaveBeenCalled();
    });

    it('点击标题图标应该切换折叠状态', async () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool' }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      // 默认展开，项目应该可见
      expect(wrapper.find('.ai-slash-group-item').exists()).toBe(true);

      // 点击折叠
      await wrapper.find('.title-icon').trigger('click');

      // 折叠后项目不可见
      expect(wrapper.find('.ai-slash-group-item').exists()).toBe(false);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理 undefined resourceList', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-menu').exists()).toBe(false);
    });

    it('应该处理单个资源', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Single Tool', type: 'tool' }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.findAll('.ai-slash-group-item').length).toBe(1);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool' }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      expect(wrapper.find('.ai-slash-menu').exists()).toBe(true);
      expect(wrapper.find('.ai-slash-group').exists()).toBe(true);
      expect(wrapper.find('.ai-slash-group-title').exists()).toBe(true);
      expect(wrapper.find('.ai-slash-group-item').exists()).toBe(true);
    });

    it('菜单项应该具有 ai-slash-group-item 类名', () => {
      wrapper = mount(AiSlashMenu, {
        props: {
          resourceList: [{ id: '1', name: 'Tool 1', type: 'tool' }],
          onSelect: vi.fn(),
        },
        global: {
          directives: {
            overflowTips: {},
          },
        },
      });

      const item = wrapper.find('.ai-slash-group-item');
      expect(item.exists()).toBe(true);
    });
  });
});
