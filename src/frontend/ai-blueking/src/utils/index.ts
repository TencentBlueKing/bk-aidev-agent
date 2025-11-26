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
 * 判断是否是json字符串
 * @param str
 * @returns
 */
export const isJSON = (str: string) => {
  try {
    JSON.parse(str);

    return true;
  } catch (e) {
    return false;
  }
};

/**
 * 节流，每隔一段时间执行
 * @param {*} fn 需要执行的函数
 * @param {*} delay 延迟时间，默认200
 * @returns
 */
export const throttle = <T>(fn: (t: T) => void, delay = 200) => {
  let valid = true;

  return function (t: T) {
    if (!valid) {
      return false;
    }
    valid = false;
    setTimeout(() => {
      fn(t);
      valid = true;
    }, delay);
  };
};

/**
 * 防抖，延迟一段时间执行
 * @param {*} fn 需要执行的函数
 * @param {*} delay 延迟时间，默认200
 * @returns
 */
export const debounce = <T, R>(fn: (P?: T) => R, delay = 200) => {
  let timer: ReturnType<typeof setTimeout>;

  return function (params?: T) {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => fn(params), delay);
  };
};

/**
 * 处理提示词模板,替换模板中的变量
 * @param prompt 提示词模板
 * @param selectedText 选中的文本
 * @returns 处理后的提示词
 */
export const processPromptTemplate = (prompt: string, selectedText: string) =>
  prompt.replace(/\{\{\s*SELECTED_TEXT\s*\}\}/g, selectedText || '');

/**
 * 格式化时间
 * @param val 时间
 * @returns 格式化后的时间
 */
export function durationFormatter(val: number) {
  const hours = Math.floor(val / 3600000);
  const minutes = Math.floor((val % 3600000) / 60000);
  const seconds = Math.floor((val % 60000) / 1000);
  const milliseconds = val % 1000;

  const parts: string[] = [];

  if (hours > 0) {
    parts.push(`${hours}h`);
  }
  if (minutes > 0) {
    parts.push(`${minutes}min`);
  }
  if (seconds > 0) {
    parts.push(`${seconds}s`);
  }
  if (milliseconds > 0) {
    parts.push(`${milliseconds.toFixed(2)}ms`);
  }

  return parts.join(' ');
}

/**
 * 滚动到页面底部
 * @param el 需要滚动的元素
 */
export const scrollToBottom = (el: HTMLElement) => {
  el.scrollTop = el.scrollHeight;
};

/**
 * 转义HTML
 * @param str
 * @returns
 */
export const escapeHtml = (str: string) =>
  str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/**
 * 生成UUID
 * @returns UUID
 */
export const uuid = () =>
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0,
      v = c == 'x' ? r : (r & 0x3) | 0x8;

    return v.toString(16);
  });

/**
 * 标准化URL，自动匹配当前页面的协议
 * @param url 原始URL
 * @returns 标准化后的URL
 */
export const normalizeUrl = (url: string): string => {
  if (!url) return url;

  try {
    // 如果URL已经是完整的协议URL，检查是否需要协议转换
    if (url.startsWith('http://') || url.startsWith('https://')) {
      const currentProtocol = window.location.protocol;
      const urlObj = new URL(url);

      // 如果当前页面是HTTPS，但API URL是HTTP，则转换为HTTPS
      if (currentProtocol === 'https:' && urlObj.protocol === 'http:') {
        urlObj.protocol = 'https:';

        return urlObj.toString();
      }

      // 如果当前页面是HTTP，但API URL是HTTPS，保持HTTPS（更安全）
      return url;
    }

    // 如果URL是相对路径或协议相对路径
    if (url.startsWith('//')) {
      // 协议相对路径，使用当前页面的协议
      return `${window.location.protocol}${url}`;
    }

    if (url.startsWith('/')) {
      // 绝对路径，使用当前页面的协议和域名
      return `${window.location.protocol}//${window.location.host}${url}`;
    }

    // 相对路径，基于当前页面构建完整URL
    const baseUrl = `${window.location.protocol}//${window.location.host}${window.location.pathname}`;

    return new URL(url, baseUrl).toString();
  } catch (error) {
    console.warn('URL normalization failed:', error);

    return url; // 如果处理失败，返回原始URL
  }
};

/**
 * 清理思考模型生成的思考片段
 * @param text 原始文本
 * @returns 清理后的文本
 */
export const removeThinkingSections = (text: string): string => {
  if (typeof text !== 'string') return text;

  // 移除思考头部和思考内容的 section 标签及其内容
  let cleaned = text.replace(/<section\s+class="think-head[^"]*"[^>]*>[\s\S]*?<\/section>/gi, '');
  cleaned = cleaned.replace(/<section\s+class="think-body"[^>]*>[\s\S]*?<\/section>/gi, '');

  // 移除多余的空白行
  cleaned = cleaned.replace(/^\s*\n\s*\n\s*\n/gm, '\n\n');

  return cleaned.trim();
};

/**
 * 复制文本到剪贴板（兼容 HTTP 环境）
 * @param text 需要复制的文本
 * @returns Promise<boolean> 是否复制成功
 */
export const copyToClipboard = async (text: string): Promise<boolean> => {
  // 优先尝试使用 navigator.clipboard API (HTTPS 环境)
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.warn('navigator.clipboard.writeText failed, trying fallback:', err);
    }
  }

  // 降级方案：使用 execCommand (兼容 HTTP 环境)
  return new Promise(resolve => {
    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;

      // 确保 textarea 不可见但存在于 DOM 中
      textArea.style.position = 'fixed';
      textArea.style.left = '-9999px';
      textArea.style.top = '0';
      textArea.style.opacity = '0';

      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);

      resolve(successful);
    } catch (err) {
      console.error('Fallback: Oops, unable to copy', err);
      resolve(false);
    }
  });
};
