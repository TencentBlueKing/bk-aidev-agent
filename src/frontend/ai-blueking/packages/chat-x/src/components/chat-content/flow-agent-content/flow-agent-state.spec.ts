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
import { type VNode, isVNode } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { getConvergedState, getStateIcon } from './flow-agent-state';

vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

/** 取图标 VNode 的第一个子 VNode（svg > path） */
const getFirstChildVNode = (vnode: VNode): undefined | VNode => {
  if (!Array.isArray(vnode.children)) {
    return undefined;
  }
  return vnode.children.find(child => isVNode(child));
};

describe('flow-agent-state', () => {
  describe('getConvergedState', () => {
    it('FINISHED 应归一为 success，FAILED 应归一为 failed', () => {
      expect(getConvergedState('FINISHED')).toBe('success');
      expect(getConvergedState('FAILED')).toBe('failed');
    });
  });

  describe('getStateIcon', () => {
    it('running 无静态图标时应返回 null', () => {
      expect(getStateIcon('running')).toBeNull();
    });

    it('多次调用同一状态应返回互不共享 children / el 的独立 VNode 树', () => {
      const first = getStateIcon('failed');
      const second = getStateIcon('failed');

      expect(first).toBeTruthy();
      expect(second).toBeTruthy();
      expect(first).not.toBe(second);
      expect(first!.children).not.toBe(second!.children);

      const firstChild = getFirstChildVNode(first!);
      const secondChild = getFirstChildVNode(second!);
      expect(firstChild).toBeTruthy();
      expect(secondChild).toBeTruthy();
      expect(firstChild).not.toBe(secondChild);

      // 模拟 Vue patch 把 el 写回其中一棵树：另一份不得被污染
      first!.el = {} as Element;
      firstChild!.el = {} as Element;
      expect(second!.el).not.toBe(first!.el);
      expect(secondChild!.el).not.toBe(firstChild!.el);
    });
  });
});
