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
import { afterEach, describe, expect, it } from 'vitest';

import { useMenuTrigger } from './use-menu-trigger';

/** 在同一个文本节点上放置光标，便于 plus 锚点跨多次 sync 复用 */
const placeCaret = (text: string, offset: number) => {
  const node = document.createTextNode(text);
  document.body.appendChild(node);
  const apply = (nextOffset: number, nextText = node.textContent ?? '') => {
    node.textContent = nextText;
    const range = document.createRange();
    range.setStart(node, nextOffset);
    range.collapse(true);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  };
  apply(offset);
  return { apply, cleanup: () => node.remove() };
};

const clearSelection = () => window.getSelection()?.removeAllRanges();

describe('useMenuTrigger', () => {
  let cleanup: (() => void) | undefined;

  afterEach(() => {
    cleanup?.();
    cleanup = undefined;
    clearSelection();
  });

  it('字符触发后 keyword 取触发符到光标之间的文本，consumeLength 含触发符', () => {
    const caret = placeCaret('hello @foo', 10);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.activateChar('@');
    menu.sync();

    expect(menu.trigger.value).toBe('@');
    expect(menu.keyword.value).toBe('foo');
    expect(menu.getConsumeLength()).toBe(4);
  });

  it('触发符后出现空白时判定上下文失效并关闭', () => {
    const caret = placeCaret('hello @ foo', 11);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.activateChar('@');
    menu.sync();

    expect(menu.trigger.value).toBeNull();
    expect(menu.keyword.value).toBe('');
  });

  it('\\ 触发按字面量匹配，不被当成转义', () => {
    const caret = placeCaret('\\prompt', 7);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.activateChar('\\');
    menu.sync();

    expect(menu.trigger.value).toBe('\\');
    expect(menu.keyword.value).toBe('prompt');
    expect(menu.getConsumeLength()).toBe(7);
  });

  it('plus 触发没有触发符，consumeLength 只含过滤词', () => {
    const caret = placeCaret('hello', 5);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.activatePlus();
    caret.apply(9, 'hello foo');
    menu.sync();

    expect(menu.trigger.value).toBe('plus');
    expect(menu.keyword.value).toBe(' foo');
    expect(menu.getConsumeLength()).toBe(4);
  });

  it('plus 触发后光标退回锚点之前时关闭菜单', () => {
    const caret = placeCaret('hello world', 6);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.activatePlus();
    caret.apply(3);
    menu.sync();

    expect(menu.trigger.value).toBeNull();
  });

  it('空输入框唤起 plus 时拿不到文本节点，过滤词保持为空', () => {
    clearSelection();
    const menu = useMenuTrigger();

    menu.activatePlus();
    menu.sync();

    expect(menu.trigger.value).toBe('plus');
    expect(menu.keyword.value).toBe('');
    expect(menu.getConsumeLength()).toBe(0);
  });

  it('close 清空触发方式、过滤词与 plus 锚点', () => {
    const caret = placeCaret('@a', 2);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.activateChar('@');
    menu.sync();
    menu.close();

    expect(menu.trigger.value).toBeNull();
    expect(menu.keyword.value).toBe('');
    expect(menu.getConsumeLength()).toBe(0);
  });

  it('未激活时 sync 不改变状态', () => {
    const caret = placeCaret('@foo', 4);
    cleanup = caret.cleanup;
    const menu = useMenuTrigger();

    menu.sync();

    expect(menu.trigger.value).toBeNull();
    expect(menu.keyword.value).toBe('');
  });
});
