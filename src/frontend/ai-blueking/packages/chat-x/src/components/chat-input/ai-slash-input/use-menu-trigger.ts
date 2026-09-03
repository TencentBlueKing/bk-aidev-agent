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

import type { MenuTrigger } from '../../../types/input-menu';

/** 光标所在文本节点的快照 */
type CaretSnapshot = {
  node: Text;
  offset: number;
  /** 光标之前的文本 */
  textBefore: string;
};

const readCaret = (): CaretSnapshot | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) {
    return null;
  }
  const range = selection.getRangeAt(0);
  const node = range.startContainer;
  if (node.nodeType !== Node.TEXT_NODE) {
    return null;
  }
  const offset = range.startOffset;
  return { node: node as Text, offset, textBefore: (node.textContent || '').slice(0, offset) };
};

/**
 * 输入框菜单的触发状态机。
 *
 * 字符触发（`@` `/` `\`）的过滤词是「触发符到光标」之间的文本，选中后连触发符一起被替换；
 * `plus` 触发没有触发符，过滤词是「唤起时的光标位置到当前光标」之间的文本，选中后只替换这段文本。
 * 两者统一暴露为 `keyword` + `consumeLength`，上层插入逻辑只有一条代码路径。
 */
export const useMenuTrigger = () => {
  const trigger = shallowRef<MenuTrigger | null>(null);
  const keyword = shallowRef('');
  // plus 触发时记录唤起瞬间的光标锚点；编辑器为空时拿不到文本节点，此时退化为「按词过滤」
  let plusAnchor: null | { node: Text; offset: number } = null;

  const close = () => {
    trigger.value = null;
    keyword.value = '';
    plusAnchor = null;
  };

  const syncCharTrigger = (char: Exclude<MenuTrigger, 'plus'>) => {
    const caret = readCaret();
    if (!caret) {
      close();
      return;
    }
    const escaped = char === '\\' ? '\\\\' : char;
    const matched = caret.textBefore.match(new RegExp(`(${escaped}[^\\s]*)$`));
    if (!matched) {
      close();
      return;
    }
    keyword.value = matched[1].slice(1);
  };

  const syncPlusTrigger = () => {
    const caret = readCaret();
    if (!caret) {
      // 编辑器还没有文本节点（空输入框刚唤起菜单），过滤词保持为空
      keyword.value = '';
      return;
    }
    if (plusAnchor) {
      if (caret.node !== plusAnchor.node || caret.offset < plusAnchor.offset) {
        close();
        return;
      }
      keyword.value = (caret.node.textContent || '').slice(plusAnchor.offset, caret.offset);
      return;
    }
    keyword.value = caret.textBefore.match(/(\S*)$/)?.[1] ?? '';
  };

  /** 内容或光标变化后重新计算过滤词，触发上下文失效时自动关闭 */
  const sync = () => {
    if (!trigger.value) {
      return;
    }
    if (trigger.value === 'plus') {
      syncPlusTrigger();
      return;
    }
    syncCharTrigger(trigger.value);
  };

  /** 用户输入了触发字符 */
  const activateChar = (char: Exclude<MenuTrigger, 'plus'>) => {
    trigger.value = char;
    keyword.value = '';
    plusAnchor = null;
  };

  /** 点击 + 号唤起聚合菜单 */
  const activatePlus = () => {
    const caret = readCaret();
    trigger.value = 'plus';
    keyword.value = '';
    plusAnchor = caret ? { node: caret.node, offset: caret.offset } : null;
  };

  /** 选中条目时需要从光标往前删除的字符数（过滤词 + 触发符） */
  const getConsumeLength = () => keyword.value.length + (trigger.value && trigger.value !== 'plus' ? 1 : 0);

  return {
    trigger,
    keyword,
    activateChar,
    activatePlus,
    close,
    sync,
    getConsumeLength,
  };
};
