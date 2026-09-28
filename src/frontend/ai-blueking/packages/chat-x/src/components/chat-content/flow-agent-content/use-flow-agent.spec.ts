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
import { defineComponent, h, shallowRef } from 'vue';

import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { useFlowAgent } from './use-flow-agent';

import type { BkFlowMessageContent, BkFlowTask } from '../../../ag-ui/types/contents';

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const createTask = (overrides: Partial<BkFlowTask> = {}): BkFlowTask => ({
  nodes: {},
  statistics: {
    state_counts: { FINISHED: 1 },
    total: 1,
  },
  task_id: 1,
  task_name: '测试任务',
  task_outputs: {},
  task_state: 'FINISHED',
  ...overrides,
});

const mountComposable = (content: BkFlowMessageContent) => {
  const contentRef = shallowRef(content);
  let api: ReturnType<typeof useFlowAgent> | undefined;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useFlowAgent(contentRef);
        return () => h('div');
      },
    }),
  );
  return { api: api!, contentRef, wrapper };
};

describe('useFlowAgent', () => {
  it('任一 task_state 为 REVOKED 时应给出已终止 header', () => {
    const { api, wrapper } = mountComposable([
      createTask({ task_state: 'FINISHED' }),
      createTask({ task_id: 2, task_state: 'REVOKED' }),
    ]);

    expect(api.flowHeaderDef.value?.key).toBe('terminated');
    expect(api.flowHeaderDef.value?.label).toBe('已终止');
    wrapper.unmount();
  });

  it('仅失败任务时不应给出整体 header 覆盖', () => {
    const { api, wrapper } = mountComposable([createTask({ task_state: 'FAILED' })]);

    expect(api.flowHeaderDef.value).toBeUndefined();
    wrapper.unmount();
  });

  it('statistics 中的 REVOKED 应出现在 visibleStats', () => {
    const { api, wrapper } = mountComposable([
      createTask({
        task_state: 'REVOKED',
        statistics: {
          state_counts: { FINISHED: 1, REVOKED: 3 },
          total: 4,
        },
      }),
    ]);

    expect(api.visibleStats.value.map(stat => stat.key)).toEqual(['success', 'terminated']);
    expect(api.visibleStats.value.find(stat => stat.key === 'terminated')).toMatchObject({
      color: '#F55B0E',
      display: '3',
      dotFill: '#FEE8DD',
    });
    expect(api.flowHeaderDef.value?.key).toBe('terminated');
    wrapper.unmount();
  });
});
