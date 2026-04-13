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
import { type VNode, h, Text } from 'vue';

import { ImageContent } from '../components/markdown-token';

import type { Options, Renderer, Token } from '../markdown-it';

export interface TokenToVNodeOptions {
  /**
   * 对应 markdown-it 的 highlight 选项
   * 允许 null | undefined，且参数签名包含 attrs
   */

  highlight?: ((str: string, lang: string, attrs?: any) => string) | null;
  html?: boolean;
  /**
   * 与产生 tokens 的 MarkdownIt 实例的 `options` 一致，供 `renderer.rules` 第三参使用
   * （markdown-it 的 rule 签名为 (tokens, idx, options, env, self)，并非 Renderer 上的字段）
   */
  mditOptions?: Options;
  renderer?: Renderer;
  /**
   * HTML 净化函数，用于处理 innerHTML 的内容
   */
  sanitize?: (html: string) => string;
}

// 定义栈节点的接口
interface StackNode {
  children: VNode[];
  props?: Record<string, any>;
  tag?: string;
  token?: Token;
}

type TokenAttrs = [string, string][];

/**
 * 用于跟踪同一次 tokensToVNodes 调用中相同 key 的出现次数
 * 避免重复 key 导致 Vue 警告
 */
let keyCounterMap: Map<string, number> = new Map();

/**
 * 重置 key 计数器，在每次 tokensToVNodes 调用开始时调用
 */
const resetKeyCounter = () => {
  keyCounterMap = new Map();
};

/**
 * 为 token 生成基于内容的稳定 key
 * 这样在流式渲染中，即使 token 的数组索引变化，相同内容的 token 仍会有相同的 key
 * 避免 Vue 错误地复用 DOM 节点
 *
 * 注意：不使用 index，完全基于内容生成 key，确保内容不变则 key 不变
 */
const generateTokenKey = (token: Token): string => {
  const parts: string[] = [token.type];

  if (token.tag) {
    parts.push(token.tag);
  }

  // 对于代码块，使用语言和内容来生成 key
  if (token.type === 'fence' || token.type === 'code_block') {
    parts.push(token.info || '');
    // 使用内容的 hash 而不是完整内容，避免 key 过长
    parts.push(simpleHash(token.content));
  }
  // 对于图片，使用 src 和 alt
  else if (token.type === 'image') {
    const attrs = token.attrs || [];
    const src = attrs.find(([key]: [string, string]) => key === 'src')?.[1] || '';
    parts.push(simpleHash(src));
    parts.push(simpleHash(token.content || ''));
  }
  // 对于其他有内容的 token
  else if (token.content) {
    parts.push(simpleHash(token.content));
  }

  const baseKey = parts.join('-');

  // 使用计数器处理完全相同内容的情况，避免重复 key
  const count = keyCounterMap.get(baseKey) || 0;
  keyCounterMap.set(baseKey, count + 1);

  // 只有第一次出现的相同内容不加后缀，后续出现的加序号
  return count === 0 ? baseKey : `${baseKey}-${count}`;
};

/**
 * Hash 计算结果缓存
 * 避免对相同字符串重复计算 hash，提升流式渲染性能
 */
const hashCache = new Map<string, string>();
const MAX_HASH_CACHE_SIZE = 500;

/**
 * 清理过大的 hash 缓存（简单的 LRU 策略）
 */
const cleanHashCache = () => {
  if (hashCache.size > MAX_HASH_CACHE_SIZE) {
    const keysToDelete = Array.from(hashCache.keys()).slice(0, Math.floor(MAX_HASH_CACHE_SIZE / 2));
    keysToDelete.forEach(key => hashCache.delete(key));
  }
};

/**
 * 简单的字符串 hash 函数，用于生成较短的内容标识
 * 使用缓存避免重复计算
 */
const simpleHash = (str: string): string => {
  if (!str) return '0';

  // 检查缓存
  const cached = hashCache.get(str);
  if (cached !== undefined) {
    return cached;
  }

  // 计算 hash
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  const result = hash.toString(36);

  // 缓存结果
  hashCache.set(str, result);
  cleanHashCache();

  return result;
};

/**
 * 内部递归函数，不重置 key 计数器
 */
const tokensToVNodesInternal = (tokens: Token[], options: TokenToVNodeOptions): VNode[] => {
  if (!tokens || tokens.length === 0) return [];

  const root: VNode[] = [];
  const stack: StackNode[] = [{ children: root }];

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];

    if (token.hidden) continue;

    const parent = stack[stack.length - 1]!;

    // 1. 自定义渲染规则
    const mdRenderer = options.renderer;
    if (token.nesting === 0 && !token.tag && mdRenderer) {
      const customRule = mdRenderer.rules[token.type];
      if (typeof customRule === 'function') {
        const mdOpts: Options = options.mditOptions ?? {};
        const html = customRule(tokens, i, mdOpts, {}, mdRenderer);
        const safeHtml = options.sanitize ? options.sanitize(html) : html;
        // 使用基于内容的稳定 key
        parent.children.push(
          h('span', { innerHTML: safeHtml, class: `md-custom-${token.type}`, key: generateTokenKey(token) }),
        );
        continue;
      }
    }

    // 2. Inline Tokens
    if (token.type === 'inline') {
      if (token.children && token.children.length > 0) {
        // 使用内部函数递归，不重置计数器
        const inlineVNodes = tokensToVNodesInternal(token.children, options);
        parent.children.push(...inlineVNodes);
      } else {
        // Text 节点通常不需要 key
        parent.children.push(h(Text, token.content));
      }
      continue;
    }

    // 3. 特殊 Block Tokens
    if (token.type === 'text') {
      parent.children.push(h(Text, token.content));
      continue;
    }

    if (token.type === 'fence') {
      parent.children.push(renderFence(token, options, generateTokenKey(token)));
      continue;
    }

    if (token.type === 'code_block') {
      parent.children.push(
        h('pre', attrsToStyleAndProps(token.attrs, undefined, generateTokenKey(token)), [h('code', token.content)]),
      );
      continue;
    }

    if (token.type === 'code_inline') {
      parent.children.push(
        h('code', attrsToStyleAndProps(token.attrs, undefined, generateTokenKey(token)), [token.content]),
      );
      continue;
    }

    if (token.type === 'image') {
      parent.children.push(renderImage(token, generateTokenKey(token)));
      continue;
    }

    if (token.type === 'softbreak' || token.type === 'hardbreak') {
      parent.children.push(h('br', { key: generateTokenKey(token) }));
      continue;
    }

    if (token.type === 'html_block' || token.type === 'html_inline') {
      if (options.html) {
        const tag = token.type === 'html_inline' ? 'span' : 'div';
        const safeHtml = options.sanitize ? options.sanitize(token.content) : token.content;
        parent.children.push(
          h(tag, {
            innerHTML: safeHtml,
            style: { display: token.type === 'html_inline' ? 'inline' : 'block' },
            key: generateTokenKey(token),
          }),
        );
      }
      continue;
    }

    // 4. 标准 Block/Nesting Tokens
    if (token.nesting === 1) {
      let tag = token.tag;
      // 使用基于内容的稳定 key
      const props = attrsToStyleAndProps(token.attrs, undefined, generateTokenKey(token));

      if (!tag) {
        tag = token.block ? 'div' : 'span';
        props.class = props.class ? `${props.class} md-unknown-${token.type}` : `md-unknown-${token.type}`;
      }

      const newContext: StackNode = {
        tag,
        props,
        children: [] as VNode[],
        token,
      };

      stack.push(newContext);
      continue;
    }

    if (token.nesting === -1) {
      if (stack.length > 1) {
        const current = stack.pop()!;
        const vnode = h(current.tag!, current.props, current.children);
        const parentContext = stack[stack.length - 1]!;
        parentContext.children.push(vnode);
      }
      continue;
    }

    if (token.nesting === 0) {
      const tag = token.tag || (token.block ? 'div' : 'span');
      const props = attrsToStyleAndProps(token.attrs, undefined, generateTokenKey(token));
      if (!token.tag) {
        props.class = props.class ? `${props.class} md-unknown-${token.type}` : `md-unknown-${token.type}`;
      }

      const vnode = h(tag, props);
      parent.children.push(vnode);
      continue;
    }
  }

  return root;
};

/**
 * 公共入口函数，重置 key 计数器后调用内部函数
 */
export const tokensToVNodes = (tokens: Token[], options: TokenToVNodeOptions = {}): VNode[] => {
  // 重置 key 计数器，确保每次顶层调用的 key 计数是独立的
  resetKeyCounter();
  const vnodes = tokensToVNodesInternal(tokens, options);
  if (vnodes.at(-1)?.type === 'hr') {
    vnodes.pop();
  }
  return vnodes;
};

/**
 * 将 markdown-it 的 attrs 数组转换为 Vue h 函数需要的 props 对象
 * - 支持同一属性多次出现：`class` 以空格拼接，`style` 以分号拼接（与常见 HTML 合并语义一致）
 * - 增加 key 参数，用于优化 Vue Diff 性能
 */
export const attrsToStyleAndProps = (
  attrs: null | TokenAttrs,
  extraClass?: string,
  key?: number | string,
): Record<string, any> => {
  const props: Record<string, any> = {};

  // 添加 key 以帮助 Vue 识别节点身份，提升列表更新性能
  if (key !== undefined) {
    props.key = key;
  }

  if (attrs && attrs.length > 0) {
    for (const [k, v] of attrs) {
      if (k === 'class') {
        props.class = props.class ? `${props.class} ${v}` : v;
      } else if (k === 'style') {
        props.style = props.style ? `${props.style}; ${v}` : v;
      } else {
        props[k] = v;
      }
    }
  }

  if (extraClass) {
    props.class = props.class ? `${props.class} ${extraClass}` : extraClass;
  }

  return props;
};

/**
 * 代码高亮结果缓存
 * key: `${lang}:${contentHash}`
 * value: 高亮后的 HTML 字符串
 */
const highlightCache = new Map<string, string>();

/**
 * 限制缓存大小，避免内存泄漏
 */
const MAX_HIGHLIGHT_CACHE_SIZE = 100;

/**
 * 清理过期的缓存（简单的 LRU 策略：当超过限制时，删除最早的一半）
 */
const cleanHighlightCache = () => {
  if (highlightCache.size > MAX_HIGHLIGHT_CACHE_SIZE) {
    const keysToDelete = Array.from(highlightCache.keys()).slice(0, Math.floor(MAX_HIGHLIGHT_CACHE_SIZE / 2));
    keysToDelete.forEach(key => highlightCache.delete(key));
  }
};

export const renderFence = (token: Token, options: TokenToVNodeOptions, key: string): VNode => {
  const lang = token.info ? token.info.trim() : '';
  const content = token.content;

  // 生成缓存 key
  const cacheKey = `${lang}:${simpleHash(content)}`;

  let highlightedHtml = highlightCache.get(cacheKey);
  let isHighlighted = false;

  // 如果没有缓存，执行高亮并缓存结果
  if (highlightedHtml === undefined && options.highlight) {
    try {
      const highlighted = options.highlight(content, lang, '');
      if (highlighted.includes('<pre')) {
        // 完整的 pre+code 结构
        highlightedHtml = options.sanitize ? options.sanitize(highlighted) : highlighted;
        isHighlighted = true;
      } else {
        // 只有 code 内容
        highlightedHtml = options.sanitize ? options.sanitize(highlighted) : highlighted;
        isHighlighted = true;
      }
      // 缓存结果
      highlightCache.set(cacheKey, highlightedHtml);
      cleanHighlightCache();
    } catch (_error) {
      // fallback: 不缓存错误情况
      highlightedHtml = undefined;
    }
  } else if (highlightedHtml !== undefined) {
    // 使用缓存
    isHighlighted = true;
  }

  // 如果有高亮结果且包含 <pre，直接使用 innerHTML
  if (isHighlighted && highlightedHtml?.includes('<pre')) {
    const props = attrsToStyleAndProps(token.attrs, 'hljs-wrapper', key);
    props.innerHTML = highlightedHtml;
    return h('div', props);
  }

  const codeClass = options.highlight ? 'hljs' : '';
  const langClass = lang ? `language-${lang}` : '';
  const finalCodeClass = [codeClass, langClass].filter(Boolean).join(' ');

  const preProps = attrsToStyleAndProps(token.attrs, undefined, key);

  if (isHighlighted && highlightedHtml) {
    return h('pre', preProps, [h('code', { class: finalCodeClass, innerHTML: highlightedHtml })]);
  }

  return h('pre', preProps, [h('code', { class: finalCodeClass }, [content])]);
};

export const renderImage = (token: Token, key: string): VNode => {
  const props = attrsToStyleAndProps(token.attrs, undefined, key);
  const src = props.src || '';
  const alt = token.content || '';

  // 使用 ImageContent 组件处理图片加载状态
  return h(ImageContent, {
    key,
    src,
    alt,
  });
};
