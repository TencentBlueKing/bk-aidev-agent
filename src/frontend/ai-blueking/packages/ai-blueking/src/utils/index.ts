/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

export * from './message-utils';

/**
 * 获取 cookie
 * @param {*} name cookie 的名称
 */
export const getCookieByName = (name: string) => {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]*)(;|$)`));

  if (match) {
    return match[2];
  }

  return '';
};

/**
 * 确保 URL 以 `/` 结尾
 * @param url 原始 URL
 * @returns 以 `/` 结尾的 URL
 */
const ensureTrailingSlash = (url: string): string => {
  return url.endsWith('/') ? url : `${url}/`;
};

/**
 * 标准化 URL，确保 URL 格式正确且以 `/` 结尾
 * 使用原生 URL API 解析，自动处理：
 * - 完整 URL (http://..., https://...)
 * - 相对路径 (/api/...)
 * - 省略协议 (//host/...)
 * - 无协议 (host:port/path)
 * 同时将协议对齐到当前页面环境，避免混合内容问题。
 * @param url 原始 URL
 * @returns 标准化后的 URL（始终以 `/` 结尾）
 */
export const normalizeUrl = (url: string): string => {
  if (!url) return url;

  try {
    const resolved = new URL(url, window.location.origin);

    // 协议对齐到当前环境，避免混合内容问题
    resolved.protocol = window.location.protocol;

    return ensureTrailingSlash(resolved.toString());
  } catch (error) {
    console.warn('Failed to normalize URL:', error);
    return ensureTrailingSlash(url);
  }
};

/**
 * 复制文本到剪贴板
 * 优先使用现代 Clipboard API，降级到传统 execCommand 方式
 * @param text 要复制的文本
 * @returns 是否复制成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 优先使用现代 Clipboard API
  if (typeof navigator !== 'undefined' && 'clipboard' in navigator) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 降级到传统方式
    }
  }

  // 传统方式
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '-9999px';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
}

/**
 * 检测当前操作系统平台
 */
export function getPlatform() {
  const userAgent = window.navigator.userAgent.toLowerCase();
  const platform = window.navigator.platform.toLowerCase();

  if (platform.includes('mac') || userAgent.includes('mac')) {
    return 'mac';
  }
  if (platform.includes('win') || userAgent.includes('win')) {
    return 'windows';
  }
  if (platform.includes('linux') || userAgent.includes('linux')) {
    return 'linux';
  }
  return 'unknown';
}

/**
 * 获取打开面板的快捷键文本
 */
export function getTogglePanelShortcut() {
  return isMac() ? 'Cmd + I' : 'Ctrl + I';
}

/**
 * 判断是否为 Mac 系统
 */
export function isMac() {
  return getPlatform() === 'mac';
}

/**
 * 检查键盘事件是否触发了打开面板的快捷键
 * @param event 键盘事件
 * @returns 是否触发快捷键
 */
export function isTogglePanelShortcut(event: KeyboardEvent): boolean {
  const isMacPlatform = isMac();
  const isModifierPressed = isMacPlatform ? event.metaKey : event.ctrlKey;
  const isIKey = event.key.toLowerCase() === 'i';

  return isModifierPressed && isIKey && !event.shiftKey && !event.altKey;
}
