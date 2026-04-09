<!-- eslint-disable vue/no-v-html -->
<!-- eslint-disable vue/no-v-text-v-html-on-component -->
/* 渲染的 LaTeX 内容 字符串 已经经过安全转义，可以直接使用 v-html 渲染 */
<template>
  <component
    :is="wrapperTag"
    :class="wrapperClass"
    v-html="renderedContent"
  />
</template>

<script setup lang="ts">
  import { computed, shallowRef, watch } from 'vue';

  import katex from 'katex';
  import throttle from 'lodash/throttle';

  import type { Token } from '../../../markdown-it';

  import 'katex/dist/katex.min.css';

  const ErrorColor = '#cc0000';

  const props = defineProps<{
    token: Token[];
  }>();

  const renderedContent = shallowRef<string>('');

  // 需要两个参数的 LaTeX 命令
  const TWO_ARG_COMMANDS = ['frac', 'dfrac', 'tfrac', 'binom', 'dbinom', 'tbinom', 'cfrac', 'overset', 'underset'];

  // 需要一个参数的 LaTeX 命令
  const ONE_ARG_COMMANDS = [
    'sqrt',
    'text',
    'mathbf',
    'mathit',
    'mathrm',
    'mathcal',
    'mathbb',
    'hat',
    'bar',
    'vec',
    'dot',
    'ddot',
    'tilde',
    'widehat',
    'widetilde',
    'overline',
    'underline',
    'boxed',
    'cancel',
  ];

  // 常见的 LaTeX 环境名
  const COMMON_ENVS = [
    'aligned',
    'align',
    'equation',
    'gather',
    'matrix',
    'pmatrix',
    'bmatrix',
    'vmatrix',
    'cases',
    'array',
    'split',
    'multline',
  ];

  /**
   * 根据部分环境名猜测完整的环境名
   */
  const guessEnvironmentName = (partial: string): string => {
    for (const env of COMMON_ENVS) {
      if (env.startsWith(partial)) {
        return env;
      }
    }
    return '';
  };

  /**
   * 补全 LaTeX 内部语法，使流式输入时能正确渲染
   */
  const completeLatexContent = (content: string): string => {
    let result = content;

    // 0. 处理不完整的 \begin{ 语法（环境名未完成）
    const incompleteBeginMatch = result.match(/\\begin\{([^}]*)$/);
    if (incompleteBeginMatch) {
      const partialEnv = incompleteBeginMatch[1] || '';
      const guessedEnv = guessEnvironmentName(partialEnv);
      if (guessedEnv) {
        // 补全环境名并添加 \end
        result = result.slice(0, -incompleteBeginMatch[0].length) + `\\begin{${guessedEnv}}\\end{${guessedEnv}}`;
        return result;
      } else if (partialEnv) {
        // 有部分环境名但无法猜测，补全花括号
        result += '}';
      }
    }

    // 0.1 处理不完整的 \end{ 语法
    const incompleteEndMatch = result.match(/\\end\{([^}]*)$/);
    if (incompleteEndMatch) {
      const partialEnv = incompleteEndMatch[1] || '';
      const guessedEnv = guessEnvironmentName(partialEnv);
      if (guessedEnv) {
        result = result.slice(0, -incompleteEndMatch[0].length) + `\\end{${guessedEnv}}`;
      } else {
        result += '}';
      }
    }

    // 0.2 处理不完整的命令名（如 \begi、\fr 等）
    // 这些不完整的命令会导致 KaTeX 错误，需要移除或补全
    const incompleteCommandMatch = result.match(/\\([a-zA-Z]+)$/);
    if (incompleteCommandMatch && incompleteCommandMatch[1]) {
      const cmd = incompleteCommandMatch[1];
      // 检查是否是已知命令的前缀
      const knownCommands = [
        ...TWO_ARG_COMMANDS,
        ...ONE_ARG_COMMANDS,
        'begin',
        'end',
        'left',
        'right',
        'sin',
        'cos',
        'tan',
        'log',
        'ln',
        'exp',
        'lim',
        'sum',
        'prod',
        'int',
        'partial',
        'infty',
        'alpha',
        'beta',
        'gamma',
        'delta',
        'epsilon',
        'theta',
        'lambda',
        'mu',
        'pi',
        'sigma',
        'omega',
        'phi',
        'psi',
        'Rightarrow',
        'Leftarrow',
        'rightarrow',
        'leftarrow',
        'times',
        'div',
        'cdot',
        'pm',
        'mp',
        'leq',
        'geq',
        'neq',
        'approx',
        'equiv',
        'subset',
        'supset',
        'in',
        'notin',
        'cup',
        'cap',
        'forall',
        'exists',
        'nabla',
      ];

      // 检查是否是完整的命令
      const isCompleteCommand = knownCommands.includes(cmd);

      if (!isCompleteCommand) {
        // 尝试找到匹配的完整命令
        const matchingCommand = knownCommands.find(c => c.startsWith(cmd) && c !== cmd);
        if (matchingCommand) {
          // 如果能找到匹配的命令，但当前是不完整的，暂时移除
          // 这样可以避免渲染错误，等待更多输入
          result = result.slice(0, -incompleteCommandMatch[0].length);
        } else if (TWO_ARG_COMMANDS.includes(cmd)) {
          result += '{}{}';
        } else if (ONE_ARG_COMMANDS.includes(cmd)) {
          result += '{}';
        }
      } else {
        // 是完整的命令，检查是否需要参数
        if (TWO_ARG_COMMANDS.includes(cmd)) {
          result += '{}{}';
        } else if (ONE_ARG_COMMANDS.includes(cmd)) {
          result += '{}';
        }
      }
    }

    // 1. 补全未闭合的花括号 {}
    let braceCount = 0;
    for (const char of result) {
      if (char === '{') braceCount++;
      else if (char === '}') braceCount--;
    }
    if (braceCount > 0) {
      result += '}'.repeat(braceCount);
    }

    // 2. 补全未闭合的方括号 []
    let bracketCount = 0;
    for (const char of result) {
      if (char === '[') bracketCount++;
      else if (char === ']') bracketCount--;
    }
    if (bracketCount > 0) {
      result += ']'.repeat(bracketCount);
    }

    // 3. 处理需要两个参数的命令（确保第二个参数存在）
    for (const cmd of TWO_ARG_COMMANDS) {
      const regex = new RegExp(`\\\\${cmd}\\{`, 'g');
      let match;
      while ((match = regex.exec(result)) !== null) {
        const startPos = match.index + match[0].length;
        let depth = 1;
        let endPos = startPos;
        while (endPos < result.length && depth > 0) {
          if (result[endPos] === '{') depth++;
          else if (result[endPos] === '}') depth--;
          endPos++;
        }
        if (depth === 0 && endPos <= result.length) {
          let nextPos = endPos;
          while (nextPos < result.length && /\s/.test(result[nextPos] || '')) {
            nextPos++;
          }
          if (nextPos >= result.length || result[nextPos] !== '{') {
            result = result.slice(0, endPos) + '{}' + result.slice(endPos);
            regex.lastIndex = endPos + 2;
          }
        }
      }
    }

    // 4. 补全未闭合的 \begin{env}
    const beginMatches = result.matchAll(/\\begin\{([^}]+)\}/g);
    const endMatches = result.matchAll(/\\end\{([^}]+)\}/g);
    const beginEnvs: string[] = [];
    const endEnvs: string[] = [];

    for (const match of beginMatches) {
      if (match[1]) beginEnvs.push(match[1]);
    }
    for (const match of endMatches) {
      if (match[1]) endEnvs.push(match[1]);
    }

    const beginCounts = new Map<string, number>();
    const endCounts = new Map<string, number>();

    for (const env of beginEnvs) {
      beginCounts.set(env, (beginCounts.get(env) || 0) + 1);
    }
    for (const env of endEnvs) {
      endCounts.set(env, (endCounts.get(env) || 0) + 1);
    }

    for (const [env, beginCount] of beginCounts.entries()) {
      const endCount = endCounts.get(env) || 0;
      const missing = beginCount - endCount;
      for (let i = 0; i < missing; i++) {
        result += `\\end{${env}}`;
      }
    }

    return result;
  };

  /**
   * 尝试渲染 KaTeX
   */
  const tryRenderKatex = (content: string, displayMode: boolean, depth = 0): null | string => {
    if (depth > 5 || !content.trim()) {
      return null;
    }

    try {
      const completedContent = completeLatexContent(content);
      return katex.renderToString(completedContent, {
        output: 'html',
        throwOnError: false,
        displayMode,
        strict: 'ignore',
        errorColor: '#fff',
      });
    } catch {
      // 尝试移除末尾不完整的部分
      let retryContent = content.replace(/\\[a-zA-Z]+(\{[^{}]*\})*\s*$/, '');
      if (retryContent !== content && retryContent.trim()) {
        const result = tryRenderKatex(retryContent, displayMode, depth + 1);
        if (result) return result;
      }

      retryContent = content.replace(/\{[^{}]*$/, '');
      if (retryContent !== content && retryContent.trim()) {
        const result = tryRenderKatex(retryContent, displayMode, depth + 1);
        if (result) return result;
      }

      return null;
    }
  };

  const hasKatexError = (html: string): boolean => {
    return html.includes('katex-error') || html.includes(`color:${ErrorColor};`);
  };

  /**
   * 渲染单个 LaTeX token
   */
  const renderLatexToken = (token: Token): string => {
    const content = token.content || '';
    const displayMode =
      token.type === 'math_block' || (token.meta as undefined | { displayMode?: boolean })?.displayMode === true;

    const result = tryRenderKatex(content, displayMode);
    if (result && !hasKatexError(result)) {
      const className = displayMode ? 'block-katex' : 'inline-katex';
      return `<span class="${className}">${result}</span>`;
    }

    // 渲染失败，返回原始内容
    const escapedContent = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<span class="katex-loading" style="color: #666; font-style: italic;">${escapedContent}</span>`;
  };

  /**
   * 转义 HTML 特殊字符
   */
  const escapeHtml = (text: string): string => {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };

  /**
   * 渲染 inline token 的 children
   */
  const renderInlineChildren = (children: Token[]): string => {
    let html = '';
    for (const child of children) {
      if (child.type === 'math_inline') {
        html += renderLatexToken(child);
      } else if (child.type === 'text') {
        html += escapeHtml(child.content || '');
      } else if (child.type === 'softbreak') {
        html += '\n';
      } else if (child.type === 'hardbreak') {
        html += '<br>';
      } else if (child.type === 'code_inline') {
        html += `<code>${escapeHtml(child.content || '')}</code>`;
      } else if (child.type === 'strong_open') {
        html += '<strong>';
      } else if (child.type === 'strong_close') {
        html += '</strong>';
      } else if (child.type === 'em_open') {
        html += '<em>';
      } else if (child.type === 'em_close') {
        html += '</em>';
      } else if (child.type === 's_open') {
        html += '<s>';
      } else if (child.type === 's_close') {
        html += '</s>';
      } else if (child.type === 'link_open') {
        const href = child.attrGet?.('href') || '';
        html += `<a href="${escapeHtml(href)}">`;
      } else if (child.type === 'link_close') {
        html += '</a>';
      } else if (child.type === 'image') {
        const src = child.attrGet?.('src') || '';
        const alt = child.content || '';
        html += `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}">`;
      } else {
        // 其他未知类型，尝试渲染内容
        html += escapeHtml(child.content || '');
      }
    }
    return html;
  };

  /**
   * 渲染 token 数组
   */
  const renderTokens = (tokens: Token[]): string => {
    let html = '';

    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i];
      if (!token) continue;

      if (token.type === 'math_block') {
        html += `<div class="block-latex-wrapper">${renderLatexToken(token)}</div>`;
      } else if (token.type === 'math_inline') {
        html += renderLatexToken(token);
      } else if (token.type === 'inline' && token.children) {
        html += renderInlineChildren(token.children);
      } else if (token.type === 'paragraph_open') {
        html += '<p>';
      } else if (token.type === 'paragraph_close') {
        html += '</p>';
      } else if (token.type === 'text') {
        html += escapeHtml(token.content || '');
      } else {
        // 其他 token 类型
        html += escapeHtml(token.content || '');
      }
    }

    return html;
  };

  // 判断是否只有块级公式（用于决定包装元素）
  const isBlockOnly = computed(() => {
    // 检查是否只有一个 math_block token
    const mathBlocks = props.token.filter(t => t.type === 'math_block');
    if (mathBlocks.length === 1 && props.token.length <= 1) {
      return true;
    }
    return false;
  });

  const wrapperTag = computed(() => (isBlockOnly.value ? 'div' : 'span'));
  const wrapperClass = computed(() => (isBlockOnly.value ? 'block-latex-content' : 'inline-latex-content'));

  /**
   * 节流的 LaTeX 渲染函数
   * 流式输入时每 100ms 最多渲染一次，减少 KaTeX 渲染开销
   * KaTeX 渲染是同步且开销较大的操作，增加节流间隔可显著提升性能
   */
  const renderLatexThrottled = throttle(
    () => {
      const html = renderTokens(props.token);
      if (html && renderedContent.value !== html) {
        renderedContent.value = html;
      }
    },
    100,
    {
      leading: true,
      trailing: true,
    },
  );

  // 监听 token 变化
  watch(() => props.token, renderLatexThrottled, { deep: true, immediate: true });
</script>

<style lang="scss">
  .inline-latex-content {
    display: inline;
    vertical-align: baseline;

    p {
      display: inline;
      margin: 0;
    }
  }

  .block-latex-content {
    display: block;
    width: 100%;
    margin: 16px 0;
    overflow: auto hidden;
    text-align: center;

    .katex-display {
      margin: 0;
    }
  }

  .block-latex-wrapper {
    display: block;
    width: 100%;
    margin: 16px 0;
    text-align: center;
  }

  .inline-katex {
    display: inline;
  }

  .block-katex {
    display: block;
  }

  .katex-loading {
    display: inline;
  }
</style>
