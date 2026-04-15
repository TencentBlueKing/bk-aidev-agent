/* eslint-disable @typescript-eslint/consistent-type-assertions */
/* eslint-disable @typescript-eslint/no-empty-object-type */
/* eslint-disable @typescript-eslint/no-explicit-any */
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

import { isTextNode } from '../doc/edit.js';
import { type DocNode, type TextNode } from '../doc/types.js';
import { docToString, stringToDoc } from '../doc/utils.js';
import { getDOMSelection, getSelectionRangeInEditor, readDom } from '../dom/index.js';
import { isCommentNode } from '../dom/parser.js';

import type { DocSchema } from './types.js';

export interface EditableVoidSerializer<T> {
  data: (node: HTMLElement) => T;
  is: (node: HTMLElement) => boolean;
  plain: (data: T) => string;
}

const emptyString = (): string => '';

export const voidNode = <const D>({
  is,
  data,
  plain = emptyString,
}: {
  data: (node: HTMLElement) => D;
  is: (node: HTMLElement) => boolean;
  plain?: (data: D) => string;
}): EditableVoidSerializer<D> => {
  return {
    is,
    data,
    plain,
  };
};

type ExtractVoidData<T> = T extends EditableVoidSerializer<infer D> ? D : never;

type ExtractVoidNode<T> = Prettify<
  {
    [K in keyof T]: {
      data: ExtractVoidData<T[K]>;
      type: K;
    };
  }[keyof T]
>;
type Prettify<T> = {
  [K in keyof T]: T[K];
} & {};

/**
 * Defines structured text schema.
 */
export const schema = <V extends Record<string, EditableVoidSerializer<any>> = {}, M extends boolean = false>({
  multiline,
  void: voids = {} as V,
}: {
  multiline?: M;
  void?: V;
}): DocSchema<
  M extends true
    ? (ExtractVoidNode<V> | { text: string; type: 'text' })[][]
    : (ExtractVoidNode<V> | { text: string; type: 'text' })[]
> => {
  type VoidNodeData = ExtractVoidData<V[keyof V]>;
  type TextNodeType = { text: string; type: 'text' };
  type VoidNodeType = ExtractVoidNode<V>;
  type RowType = (TextNodeType | VoidNodeType)[];

  const voidSerializers = Object.entries(voids);

  const textCache = new WeakMap<TextNode, TextNodeType>();
  // TODO replace VoidNodeData with VoidNode
  const voidCache = new WeakMap<VoidNodeData, VoidNodeType>();

  const serializeRow = (r: readonly DocNode[]): RowType => {
    return r.reduce((acc, t) => {
      if (isTextNode(t)) {
        let text = textCache.get(t);
        if (!text) {
          textCache.set(t, (text = { type: 'text', text: t.text }));
        }
        acc.push(text);
      } else {
        const cached = voidCache.get(t.data as VoidNodeData);
        if (cached) {
          acc.push(cached);
        } else {
          acc.push({ type: 'tag' as const, data: t.data } as VoidNodeType);
        }
      }
      return acc;
    }, [] as RowType);
  };

  const serializeVoid = (element: Element) => {
    for (const [type, s] of voidSerializers) {
      if (s.is(element as HTMLElement)) {
        const data = s.data(element as HTMLElement) as VoidNodeData;
        // TODO improve
        voidCache.set(data, {
          type,
          data: { ...data },
        } as VoidNodeType);
        return data;
      }
    }
    return;
  };

  const nodeToDocNode = (node: ExtractVoidNode<V> | { text: string; type: 'text' }): DocNode => {
    if (node.type === 'text') {
      return { text: (node as { text: string; type: 'text' }).text };
    }
    const { type, data } = node as {
      data: ExtractVoidData<V[keyof V]>;
      type: keyof V;
    };
    voidCache.set(
      data as VoidNodeData,
      {
        type,
        data,
      } as VoidNodeType,
    );
    return { data };
  };

  return {
    single: !multiline,
    js: multiline
      ? doc => {
          return doc.map(serializeRow);
        }
      : doc => {
          return serializeRow(doc[0]!) satisfies RowType as any; // TODO improve type
        },
    doc: state => {
      // TODO remove
      return multiline
        ? (state as (ExtractVoidNode<V> | { text: string; type: 'text' })[][]).map(r => r.map(nodeToDocNode))
        : [(state as (ExtractVoidNode<V> | { text: string; type: 'text' })[]).map(nodeToDocNode)];
    },
    copy: (dataTransfer, doc, element) => {
      dataTransfer.setData(
        'text/plain',
        docToString(doc, node => {
          const voidNode = voidCache.get(node.data as VoidNodeData)!;
          return voids[voidNode.type]!.plain(node.data);
        }),
      );

      const wrapper = document.createElement('div');
      const range = getSelectionRangeInEditor(getDOMSelection(element), element);
      if (range) {
        wrapper.appendChild(range.cloneContents());
      }
      dataTransfer.setData('text/html', wrapper.innerHTML);
    },
    paste: (dataTransfer, config) => {
      const html = dataTransfer.getData('text/html');
      if (html) {
        let dom: Node = new DOMParser().parseFromString(html, 'text/html').body;
        let isWindowsCopy = false;
        // https://github.com/w3c/clipboard-apis/issues/193
        for (const n of [...dom.childNodes]) {
          if (isCommentNode(n)) {
            if (n.data === 'StartFragment') {
              isWindowsCopy = true;
              dom = new DocumentFragment();
            } else if (n.data === 'EndFragment') {
              isWindowsCopy = false;
            }
          } else if (isWindowsCopy) {
            dom.appendChild(n);
          }
        }

        return readDom(dom, config, serializeVoid);
      }
      return stringToDoc(dataTransfer.getData('text/plain'));
    },
  };
};
