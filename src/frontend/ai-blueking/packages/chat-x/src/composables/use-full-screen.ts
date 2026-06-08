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

import { type MaybeRef, onScopeDispose, readonly, shallowRef, unref } from 'vue';

/** 一次性解析得到的全屏 API 字段名，避免每次调用重复嗅探 */
interface FullscreenApi {
  /** 全屏状态变化事件名 */
  change: 'fullscreenchange' | 'webkitfullscreenchange';
  /** 当前全屏元素的 document 字段名 */
  element: 'fullscreenElement' | 'webkitFullscreenElement';
  /** 退出全屏的 document 方法名 */
  exit: 'exitFullscreen' | 'webkitExitFullscreen';
  /** 进入全屏的元素方法名 */
  request: 'requestFullscreen' | 'webkitRequestFullscreen';
}

/** 带浏览器前缀的 document 全屏相关字段 */
type FullscreenDocument = Document & {
  webkitExitFullscreen?: () => Promise<void>;
  readonly webkitFullscreenElement?: Element | null;
};

/** 带浏览器前缀的元素全屏请求方法（主要兼容旧版 WebKit/Safari） */
type FullscreenHTMLElement = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void>;
};

/**
 * 嗅探当前环境支持的 Fullscreen API（含厂商前缀）。
 * 模块加载时执行一次；SSR 或不支持时返回 null。
 */
const resolveFullscreenApi = (): FullscreenApi | null => {
  if (typeof document === 'undefined') {
    return null;
  }
  // 用 Record 嗅探，避免 TS 将标准方法视为恒存在而把 webkit 降级分支判为死代码
  const root = document.documentElement as unknown as Record<string, unknown>;
  if (typeof root.requestFullscreen === 'function') {
    return {
      request: 'requestFullscreen',
      exit: 'exitFullscreen',
      element: 'fullscreenElement',
      change: 'fullscreenchange',
    };
  }
  if (typeof root.webkitRequestFullscreen === 'function') {
    return {
      request: 'webkitRequestFullscreen',
      exit: 'webkitExitFullscreen',
      element: 'webkitFullscreenElement',
      change: 'webkitfullscreenchange',
    };
  }
  return null;
};

const fullscreenApi = resolveFullscreenApi();

/**
 * 将传入的目标元素以浏览器原生全屏方式展示。
 *
 * @param target 需要全屏的目标元素（支持 ref）；缺省时回退到 document.documentElement。
 * @returns
 * - `isSupported` 当前环境是否支持全屏
 * - `isFullScreen` 只读响应式状态，始终与真实全屏同步（含用户按 ESC 退出）
 * - `enter` / `exit` / `toggle` 控制方法
 */
export const useFullScreen = (target?: MaybeRef<HTMLElement | null>) => {
  const isSupported = !!fullscreenApi;
  const isFullScreen = shallowRef(false);

  /** 解析目标元素，未指定时回退到根元素 */
  const getTarget = (): HTMLElement | null =>
    unref(target) ?? (typeof document === 'undefined' ? null : document.documentElement);

  /** 读取浏览器当前的全屏元素 */
  const getFullscreenElement = (): Element | null =>
    fullscreenApi ? ((document as FullscreenDocument)[fullscreenApi.element] ?? null) : null;

  /**
   * 以浏览器真实状态为准同步本地响应式状态，覆盖 ESC 退出、F11 等外部行为。
   * 指定了 target 时，仅当全屏元素恰为 target 才视为已全屏。
   */
  const syncState = () => {
    const current = getFullscreenElement();
    const el = unref(target);
    isFullScreen.value = el ? current === el : !!current;
  };

  const enter = async () => {
    if (!fullscreenApi || isFullScreen.value) {
      return;
    }
    const el = getTarget() as FullscreenHTMLElement | null;
    try {
      await el?.[fullscreenApi.request]?.();
    } catch {
      // 进入全屏可能因缺少用户手势等被拒绝，忽略以避免未处理的 Promise 异常
    }
  };

  const exit = async () => {
    if (!fullscreenApi || !getFullscreenElement()) {
      return;
    }
    try {
      await (document as FullscreenDocument)[fullscreenApi.exit]?.();
    } catch {
      // 退出全屏失败时静默处理
    }
  };

  const toggle = () => (isFullScreen.value ? exit() : enter());

  if (fullscreenApi) {
    document.addEventListener(fullscreenApi.change, syncState);
    // 作用域销毁时移除监听，兼容组件卸载与 effectScope 场景
    onScopeDispose(() => {
      document.removeEventListener(fullscreenApi.change, syncState);
    });
  }

  return {
    isSupported,
    isFullScreen: readonly(isFullScreen),
    enter,
    exit,
    toggle,
  };
};
