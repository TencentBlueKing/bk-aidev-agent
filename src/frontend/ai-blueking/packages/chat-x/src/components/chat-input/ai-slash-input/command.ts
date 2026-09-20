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

import { Transaction } from '../../../edix/doc/edit';

import type { EditorCommand } from '../../../edix';
import type { Position } from '../../../edix/doc/types';
import type { IInputMenuItem } from '../../../types/input-menu';

export const DeleteTag: EditorCommand<[Position, Position]> = (_doc, _selection, start: Position, end: Position) => {
  return new Transaction().delete(start, end);
};

/**
 * 插入菜单选项对应的 void 标签节点。
 * value 取 item.id：序列化给后端时 skill 走 `/${value}`，因此业务方需保证 skill 的 id 为后端可识别的编码。
 */
export const InsertMenuTag: EditorCommand<[Position, IInputMenuItem]> = (
  _doc,
  _selection,
  start: Position,
  item: IInputMenuItem,
) => {
  return new Transaction().insert(start, [
    [
      {
        data: {
          label: item.name,
          value: item.id,
          type: item.type,
          // DOM 属性只能承载字符串，组件形式的图标存不下，标签内交由类型默认图标兜底
          icon: typeof item.icon === 'string' ? item.icon : '',
          description: item.description ?? '',
        },
      },
    ],
  ]);
};

export const InsertText: EditorCommand<[Position, string]> = (_doc, _selection, start: Position, text: string) => {
  return new Transaction().insert(start, [
    [
      {
        text: text,
      },
    ],
  ]);
};
