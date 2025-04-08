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
import { ref, onMounted, onUnmounted, nextTick } from 'vue';

export function useNimbus(
  emit: { (e: 'click'): void; (e: 'minimize', value: boolean): void },
  defaultMinimize = false,
) {
  const nimbusWidth = 48;
  const nimbusHeight = 48;
  const initNimbusTop = window.innerHeight - nimbusHeight - 40;
  const initNimbusLeft = window.innerWidth - nimbusWidth - 16;
  const nimbusLeft = ref(initNimbusLeft);
  const nimbusTop = ref(initNimbusTop);
  const diffY = ref(0);

  const isMinimize = ref(defaultMinimize);
  const isHovering = ref(false);
  const isDragging = ref(false);
  let dragStartTime = 0;

  const handleNimbusMinimize = (isMinimize: boolean) => {
    if (isMinimize) {
      nimbusLeft.value = window.innerWidth - 12;
    } else {
      nimbusLeft.value = initNimbusLeft;
    }
  };

  const handleNimbusDragging = (_x: number, y: number) => {
    nimbusTop.value = y;
    diffY.value = y - initNimbusTop;
  };

  const handleResize = () => {
    nextTick(() => {
      nimbusTop.value = window.innerHeight - nimbusHeight - 40 + diffY.value;
      if (isMinimize.value) {
        nimbusLeft.value = window.innerWidth - 12;
      } else {
        nimbusLeft.value = window.innerWidth - nimbusWidth - 16;
      }
    });
  };

  const handleClick = () => {
    if (isDragging.value) {
      isDragging.value = false;
      return;
    }

    emit('click');
  };

  const handleMinimize = () => {
    isMinimize.value = !isMinimize.value;
    emit('minimize', isMinimize.value);
    if (isMinimize.value) {
      nimbusLeft.value = window.innerWidth - 12;
    } else {
      nimbusLeft.value = window.innerWidth - 60;
    }
  };

  const handleDragging = (x: number, y: number) => {
    nimbusLeft.value = x;
    nimbusTop.value = y;
  };

  const handleMouseEnter = () => {
    isHovering.value = true;
  };

  const handleMouseLeave = () => {
    isHovering.value = false;
  };

  const handleMouseDown = () => {
    dragStartTime = Date.now();
    isDragging.value = false;
  };

  const handleMouseUp = () => {
    if (Date.now() - dragStartTime > 200) {
      isDragging.value = true;
    }
  };

  onMounted(() => {
    window.addEventListener('resize', handleResize);
    handleResize();
  });

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
  });

  return {
    nimbusWidth,
    nimbusHeight,
    nimbusLeft,
    nimbusTop,
    isMinimize,
    isHovering,
    isDragging,
    handleNimbusDragging,
    handleNimbusMinimize,
    handleClick,
    handleMinimize,
    handleDragging,
    handleMouseEnter,
    handleMouseLeave,
    handleMouseDown,
    handleMouseUp,
  };
}
