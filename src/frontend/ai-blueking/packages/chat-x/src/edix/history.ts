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

const MAX_HISTORY_LENGTH = 500;
const BATCH_HISTORY_TIME = 500;

/**
 * @internal
 */
export const createHistory = <T>(initialValue: T) => {
  let index = 0;
  let prevTime = 0;
  const now = Date.now;
  const histories: T[] = [initialValue];

  const get = () => histories[index]!;

  const isUndoable = (): boolean => {
    return index > 0;
  };

  const isRedoable = (): boolean => {
    return index < histories.length - 1;
  };

  return {
    get,
    set: (history: T) => {
      histories[index] = history;
    },
    undo: (): T | undefined => {
      if (isUndoable()) {
        index--;
        return get();
      } else {
        return;
      }
    },
    redo: (): T | undefined => {
      if (isRedoable()) {
        index++;
        return get();
      } else {
        return;
      }
    },
    push: (history: T) => {
      const time = now();
      if (index !== 0 && time - prevTime < BATCH_HISTORY_TIME) {
        index--;
      }
      prevTime = time;

      histories[++index] = history;
      histories.splice(index + 1);
      if (index > MAX_HISTORY_LENGTH) {
        index--;
        histories.shift();
      }
    },
  };
};
