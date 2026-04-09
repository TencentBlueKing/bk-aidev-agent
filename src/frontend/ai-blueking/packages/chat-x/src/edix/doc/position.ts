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
import type { Position, PositionRange } from './types.js';

/**
 * @internal
 * 0 : same
 * 1 : A is before B (forward)
 * -1: A is after B (backward)
 */
export const compareLine = ([lineA]: Position, [lineB]: Position): -1 | 0 | 1 => {
  if (lineA === lineB) {
    return 0;
  } else {
    return lineA < lineB ? 1 : -1;
  }
};

/**
 * @internal
 * 0 : same
 * 1 : A is before B (forward)
 * -1: A is after B (backward)
 */
export const comparePosition = (posA: Position, posB: Position): -1 | 0 | 1 => {
  const line = compareLine(posA, posB);
  if (line === 0) {
    return posA[1] === posB[1] ? 0 : posA[1] < posB[1] ? 1 : -1;
  } else {
    return line;
  }
};

/**
 * @internal
 */
export const range = ([a, b]: readonly [Position, Position]): PositionRange => {
  return comparePosition(a, b) === -1 ? [b, a] : [a, b];
};
