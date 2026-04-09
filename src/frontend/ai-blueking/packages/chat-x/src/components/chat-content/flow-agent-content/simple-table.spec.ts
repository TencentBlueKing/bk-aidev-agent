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
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import SimpleTable from './simple-table.vue';

import type { SimpleTableColumn } from './simple-table.vue';

describe('SimpleTable', () => {
  let wrapper: VueWrapper;

  const defaultColumns: SimpleTableColumn[] = [
    { key: 'name', label: '名称' },
    { key: 'value', label: '值' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染表格', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [{ name: 'key1', value: 'val1' }],
        },
      });

      expect(wrapper.find('.ai-simple-table').exists()).toBe(true);
    });

    it('应该渲染表头', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [],
        },
      });

      const headers = wrapper.findAll('th');
      expect(headers.length).toBe(2);
      expect(headers[0]?.text()).toBe('名称');
      expect(headers[1]?.text()).toBe('值');
    });

    it('应该渲染数据行', () => {
      const data = [
        { name: 'param1', value: 'value1' },
        { name: 'param2', value: 'value2' },
      ];

      wrapper = mount(SimpleTable, {
        props: { columns: defaultColumns, data },
      });

      const rows = wrapper.findAll('tbody tr');
      expect(rows.length).toBe(2);
    });

    it('应该正确显示单元格内容', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [{ name: '参数名', value: '参数值' }],
        },
      });

      const cells = wrapper.findAll('tbody td');
      expect(cells[0]?.text()).toBe('参数名');
      expect(cells[1]?.text()).toBe('参数值');
    });
  });

  describe('空数据测试', () => {
    it('数据为空时应该显示 -- 占位行', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [],
        },
      });

      const emptyCell = wrapper.find('.is-empty');
      expect(emptyCell.exists()).toBe(true);
      expect(emptyCell.text()).toBe('--');
    });

    it('空数据占位行 colspan 应等于列数', () => {
      const columns: SimpleTableColumn[] = [
        { key: 'a', label: 'A' },
        { key: 'b', label: 'B' },
        { key: 'c', label: 'C' },
      ];

      wrapper = mount(SimpleTable, {
        props: { columns, data: [] },
      });

      const emptyCell = wrapper.find('.is-empty');
      expect(emptyCell.attributes('colspan')).toBe('3');
    });
  });

  describe('breakAll 样式测试', () => {
    it('breakAll 为 true 的列应该有 is-break-all 类', () => {
      const columns: SimpleTableColumn[] = [
        { key: 'key', label: '参数名' },
        { breakAll: true, key: 'value', label: '参数值' },
      ];

      wrapper = mount(SimpleTable, {
        props: {
          columns,
          data: [{ key: 'test', value: 'very-long-value' }],
        },
      });

      const cells = wrapper.findAll('tbody td');
      expect(cells[0]?.classes()).not.toContain('is-break-all');
      expect(cells[1]?.classes()).toContain('is-break-all');
    });
  });

  describe('空值处理测试', () => {
    it('值为 undefined 时应显示 --', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [{ name: 'key1' }],
        },
      });

      const cells = wrapper.findAll('tbody td');
      expect(cells[1]?.text()).toBe('--');
    });

    it('值为 null 时应显示 --', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [{ name: 'key1', value: null }],
        },
      });

      const cells = wrapper.findAll('tbody td');
      expect(cells[1]?.text()).toBe('--');
    });

    it('值为 0 时应显示 0', () => {
      wrapper = mount(SimpleTable, {
        props: {
          columns: defaultColumns,
          data: [{ name: 'key1', value: 0 }],
        },
      });

      const cells = wrapper.findAll('tbody td');
      expect(cells[1]?.text()).toBe('0');
    });
  });
});
